"""
Custos Setup Wizard — FastAPI application.

Routes:
  GET  /setup            Step 1: Welcome (or "already configured" interstitial)
  POST /setup/scan       Kick off WS-Discovery in the background
  GET  /setup/scan/poll  HTMX polling endpoint — returns camera cards when done
  GET  /setup/cameras    Step 2: Name cameras + enter credentials
  POST /setup/cameras    Save camera names/credentials, capture thumbnails
  GET  /setup/detect     Step 3: Detection toggles per camera
  POST /setup/detect     Save detection preferences
  GET  /setup/notify     Step 4: Notification method
  POST /setup/notify     Save notification config
  GET  /setup/remote     Step 5: Remote access (Tailscale)
  POST /setup/finalize   Write all configs, restart services
  GET  /setup/done       Success screen

State is stored in a JSON file on the container's /tmp so it survives between
requests but is reset when the container restarts.
"""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config_writer
import discover
import thumbnails

app = FastAPI(docs_url=None, redoc_url=None)

THUMB_DIR = thumbnails.THUMB_DIR
app.mount("/thumbnails", StaticFiles(directory=str(THUMB_DIR)), name="thumbnails")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
templates.env.filters["enumerate"] = enumerate

# ─── Wizard state ─────────────────────────────────────────────────────────────
# Simple JSON file on /tmp — good enough for a one-shot setup process.

STATE_FILE = Path("/tmp/custos-wizard-state.json")

_DEFAULT_STATE = {
    "scan_status": "idle",   # idle | scanning | done | error
    "discovered": [],        # list of {ip, manufacturer} from WS-Discovery
    "cameras": [],           # confirmed cameras with names + credentials
    "detection": {},         # {camera_id: {person, car, animal}}
    "notify_method": "companion",
    "tailscale_done": False,
    "finalized": False,
}


def _load() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return dict(_DEFAULT_STATE)


def _save(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state))


def _reset() -> dict:
    STATE_FILE.unlink(missing_ok=True)
    return dict(_DEFAULT_STATE)


# ─── Background scan task ─────────────────────────────────────────────────────

async def _run_scan() -> None:
    state = _load()
    state["scan_status"] = "scanning"
    state["discovered"] = []
    _save(state)

    try:
        devices = await discover.scan_network()
        state["discovered"] = [
            {"ip": d.ip, "manufacturer": d.manufacturer, "onvif_url": d.onvif_url}
            for d in devices
        ]
        state["scan_status"] = "done"
    except Exception as exc:
        state["scan_status"] = "error"
        state["scan_error"] = str(exc)

    _save(state)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/setup", response_class=HTMLResponse)
async def step1_welcome(request: Request):
    already_configured = config_writer.is_already_configured()
    state = _load()
    return templates.TemplateResponse("step1_welcome.html", {
        "request": request,
        "already_configured": already_configured,
        "state": state,
    })


@app.post("/setup/scan")
async def start_scan(background_tasks: BackgroundTasks):
    state = _load()
    if state["scan_status"] == "scanning":
        return RedirectResponse("/setup/scan/poll", status_code=303)
    state = _reset()
    state["scan_status"] = "scanning"
    _save(state)
    background_tasks.add_task(_run_scan)
    return RedirectResponse("/setup/scan/poll", status_code=303)


@app.get("/setup/scan/poll", response_class=HTMLResponse)
async def poll_scan(request: Request):
    """HTMX polling endpoint. Returns spinner or camera cards."""
    state = _load()
    status = state["scan_status"]

    if status == "scanning":
        # Return a spinner fragment; HTMX will re-poll in 2s
        return templates.TemplateResponse("_scan_polling.html", {
            "request": request,
            "status": status,
        })

    # Done or error — return the cameras step
    return templates.TemplateResponse("step2_cameras.html", {
        "request": request,
        "discovered": state.get("discovered", []),
        "error": state.get("scan_error") if status == "error" else None,
    })


@app.post("/setup/cameras")
async def save_cameras(request: Request, background_tasks: BackgroundTasks):
    """
    Receives the camera form (name, IP, username, password per camera).
    Probes credentials, captures thumbnails, then goes to step 3.
    """
    form = await request.form()

    # Collect camera entries from the flat form data.
    # Form fields are: cam_0_name, cam_0_ip, cam_0_username, cam_0_password, etc.
    cameras_raw: list[dict] = []
    idx = 0
    while f"cam_{idx}_ip" in form:
        ip = form.get(f"cam_{idx}_ip", "").strip()
        name = form.get(f"cam_{idx}_name", f"Camera {idx + 1}").strip()
        username = form.get(f"cam_{idx}_username", "admin").strip()
        password = form.get(f"cam_{idx}_password", "").strip()
        if ip:
            cameras_raw.append({
                "ip": ip,
                "display_name": name,
                "id": discover.slugify(name),
                "username": username,
                "password": password,
            })
        idx += 1

    # Also handle manually-added cameras (from "Add camera manually" button)
    manual_idx = 0
    while f"manual_{manual_idx}_ip" in form:
        ip = form.get(f"manual_{manual_idx}_ip", "").strip()
        name = form.get(f"manual_{manual_idx}_name", f"Camera").strip()
        username = form.get(f"manual_{manual_idx}_username", "admin").strip()
        password = form.get(f"manual_{manual_idx}_password", "").strip()
        if ip:
            cameras_raw.append({
                "ip": ip,
                "display_name": name,
                "id": discover.slugify(name),
                "username": username,
                "password": password,
            })
        manual_idx += 1

    # Probe credentials and resolve RTSP URLs
    enriched = []
    for cam in cameras_raw:
        device = discover.DiscoveredDevice(ip=cam["ip"])
        device = await discover.probe_credentials(device, cam["username"], cam["password"])

        enriched.append({
            **cam,
            "rtsp_sub": device.rtsp_sub,
            "rtsp_main": device.rtsp_main,
            "manufacturer": device.manufacturer,
            "authenticated": device.authenticated,
            "thumb_url": thumbnails.PLACEHOLDER,
        })

    # Capture thumbnails in background (don't block the response)
    async def _fetch_thumbs():
        state = _load()
        for cam in state["cameras"]:
            if cam.get("rtsp_sub"):
                cam["thumb_url"] = await thumbnails.capture(cam["rtsp_sub"])
        _save(state)

    state = _load()
    state["cameras"] = enriched
    _save(state)

    background_tasks.add_task(_fetch_thumbs)

    return RedirectResponse("/setup/detect", status_code=303)


@app.get("/setup/detect", response_class=HTMLResponse)
async def step3_detect(request: Request):
    state = _load()
    if not state.get("cameras"):
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse("step3_detect.html", {
        "request": request,
        "cameras": state["cameras"],
        "detection": state.get("detection", {}),
    })


@app.post("/setup/detect")
async def save_detect(request: Request):
    form = await request.form()
    state = _load()
    detection = {}
    for cam in state["cameras"]:
        cid = cam["id"]
        detection[cid] = {
            "person": form.get(f"{cid}_person") == "on",
            "car":    form.get(f"{cid}_car") == "on",
            "animal": form.get(f"{cid}_animal") == "on",
        }
    state["detection"] = detection
    # Merge detection prefs back into cameras list for config_writer
    for cam in state["cameras"]:
        prefs = detection.get(cam["id"], {})
        cam["detect_person"] = prefs.get("person", True)
        cam["detect_car"] = prefs.get("car", True)
        cam["detect_animal"] = prefs.get("animal", False)
    _save(state)
    return RedirectResponse("/setup/notify", status_code=303)


@app.get("/setup/notify", response_class=HTMLResponse)
async def step4_notify(request: Request):
    state = _load()
    if not state.get("cameras"):
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse("step4_notify.html", {
        "request": request,
        "notify_method": state.get("notify_method", "companion"),
    })


@app.post("/setup/notify")
async def save_notify(request: Request):
    form = await request.form()
    state = _load()
    state["notify_method"] = form.get("method", "companion")
    _save(state)
    return RedirectResponse("/setup/remote", status_code=303)


@app.get("/setup/remote", response_class=HTMLResponse)
async def step5_remote(request: Request):
    state = _load()
    if not state.get("cameras"):
        return RedirectResponse("/setup", status_code=303)

    tailscale_installed = _check_tailscale()
    return templates.TemplateResponse("step5_remote.html", {
        "request": request,
        "tailscale_installed": tailscale_installed,
    })


@app.post("/setup/finalize")
async def finalize(request: Request):
    """Write all configs and restart services."""
    form = await request.form()
    state = _load()

    cameras = state.get("cameras", [])
    if not cameras:
        return RedirectResponse("/setup", status_code=303)

    # Write .env password (use first camera's password as the shared credential)
    first_pw = cameras[0].get("password", "")
    if first_pw:
        config_writer.write_camera_password(first_pw)

    # Resolve any cameras that didn't get RTSP URLs (fall back to known Reolink pattern)
    for cam in cameras:
        if not cam.get("rtsp_sub"):
            cam["rtsp_sub"] = (
                f"rtsp://{cam['username']}:{cam['password']}@{cam['ip']}:554/h264Preview_01_sub"
            )
            cam["rtsp_main"] = (
                f"rtsp://{cam['username']}:{cam['password']}@{cam['ip']}:554/h264Preview_01_main"
            )

    config_writer.write_frigate_config(cameras)
    config_writer.write_ha_cameras(cameras)
    config_writer.write_mqtt_sensors(cameras)
    config_writer.write_lovelace_dashboard(cameras)
    config_writer.write_ha_automations(cameras, state.get("notify_method", "companion"))
    config_writer.restart_frigate()
    config_writer.reload_ha()

    state["finalized"] = True
    _save(state)

    return RedirectResponse("/setup/done", status_code=303)


@app.get("/setup/done", response_class=HTMLResponse)
async def done(request: Request):
    state = _load()
    cameras = state.get("cameras", [])
    return templates.TemplateResponse("done.html", {
        "request": request,
        "cameras": cameras,
    })


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _check_tailscale() -> bool:
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, timeout=3,
        )
        return result.returncode == 0
    except Exception:
        return False

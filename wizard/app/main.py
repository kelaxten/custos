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

State is stored in a JSON file on the container's /tmp — simple and sufficient
for a one-shot setup flow that resets on container restart.
"""

import asyncio
import json
from pathlib import Path
from urllib.parse import quote as urlquote

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config_writer
import discover
import thumbnails

app = FastAPI(docs_url=None, redoc_url=None)

_APP_DIR = Path(__file__).parent
THUMB_DIR = thumbnails.THUMB_DIR
THUMB_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/thumbnails", StaticFiles(directory=str(THUMB_DIR)), name="thumbnails")
app.mount("/static", StaticFiles(directory=str(_APP_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(_APP_DIR / "templates"))
templates.env.filters["enumerate"] = enumerate

# ─── Wizard state ─────────────────────────────────────────────────────────────

STATE_FILE = Path("/tmp/custos-wizard-state.json")

_DEFAULT_STATE: dict = {
    "scan_status": "idle",   # idle | scanning | done | error
    "discovered": [],
    "cameras": [],
    "detection": {},
    "notify_method": "companion",
    "tailscale_done": False,
    "finalized": False,
}


def _load() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULT_STATE)


def _save(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state))


def _reset() -> dict:
    STATE_FILE.unlink(missing_ok=True)
    return dict(_DEFAULT_STATE)


# ─── Background scan ──────────────────────────────────────────────────────────

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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _deduplicated_id(base_id: str, existing_ids: set[str]) -> str:
    """Append a numeric suffix if base_id is already taken."""
    if base_id not in existing_ids:
        return base_id
    n = 2
    while f"{base_id}_{n}" in existing_ids:
        n += 1
    return f"{base_id}_{n}"


def _safe_rtsp_url(username: str, password: str, ip: str, path: str) -> str:
    """Build an RTSP URL with URL-encoded credentials."""
    creds = f"{urlquote(username, safe='')}:{urlquote(password, safe='')}"
    return f"rtsp://{creds}@{ip}:554/{path}"


async def _check_tailscale() -> bool:
    """Non-blocking check for Tailscale being installed and connected."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "tailscale", "status", "--json",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.communicate(), timeout=3.0)
        return proc.returncode == 0
    except Exception:
        return False


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
    state = _load()
    status = state["scan_status"]

    if status == "scanning":
        return templates.TemplateResponse("_scan_polling.html", {
            "request": request,
            "status": status,
        })

    return templates.TemplateResponse("step2_cameras.html", {
        "request": request,
        "discovered": state.get("discovered", []),
        "error": state.get("scan_error") if status == "error" else None,
    })


@app.post("/setup/cameras")
async def save_cameras(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()

    cameras_raw: list[dict] = []

    def _collect(prefix: str, idx: int) -> dict | None:
        ip = form.get(f"{prefix}{idx}_ip", "").strip()
        if not ip:
            return None
        if not discover.is_routable_camera_ip(ip):
            return None  # silently skip invalid/non-private IPs
        return {
            "ip": ip,
            "display_name": form.get(f"{prefix}{idx}_name", f"Camera {idx + 1}").strip() or f"Camera {idx + 1}",
            "username": form.get(f"{prefix}{idx}_username", "admin").strip() or "admin",
            "password": form.get(f"{prefix}{idx}_password", "").strip(),
        }

    idx = 0
    while f"cam_{idx}_ip" in form:
        entry = _collect("cam_", idx)
        if entry:
            cameras_raw.append(entry)
        idx += 1

    manual_idx = 0
    while f"manual_{manual_idx}_ip" in form:
        entry = _collect("manual_", manual_idx)
        if entry:
            cameras_raw.append(entry)
        manual_idx += 1

    # Probe credentials in parallel (all cameras simultaneously)
    async def _probe(cam: dict) -> dict:
        device = discover.DiscoveredDevice(ip=cam["ip"])
        device = await discover.probe_credentials(device, cam["username"], cam["password"])
        return {
            **cam,
            "rtsp_sub": device.rtsp_sub,
            "rtsp_main": device.rtsp_main,
            "manufacturer": device.manufacturer,
            "authenticated": device.authenticated,
            "thumb_url": thumbnails.PLACEHOLDER,
        }

    enriched_list = await asyncio.gather(*[_probe(c) for c in cameras_raw])

    # Assign deduplicated slugged IDs
    used_ids: set[str] = set()
    enriched: list[dict] = []
    for cam in enriched_list:
        base_id = discover.slugify(cam["display_name"])
        cam["id"] = _deduplicated_id(base_id, used_ids)
        used_ids.add(cam["id"])
        enriched.append(cam)

    state = _load()
    state["cameras"] = enriched
    _save(state)

    # Capture thumbnails asynchronously — state is re-read inside to avoid races
    async def _fetch_thumbs() -> None:
        current = _load()
        updated = False
        for cam in current["cameras"]:
            if cam.get("rtsp_sub"):
                url = await thumbnails.capture(cam["rtsp_sub"])
                if url != cam.get("thumb_url"):
                    cam["thumb_url"] = url
                    updated = True
        if updated:
            _save(current)

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
    method = form.get("method", "companion")
    if method not in ("companion", "ntfy", "skip"):
        method = "companion"
    state["notify_method"] = method
    _save(state)
    return RedirectResponse("/setup/remote", status_code=303)


@app.get("/setup/remote", response_class=HTMLResponse)
async def step5_remote(request: Request):
    state = _load()
    if not state.get("cameras"):
        return RedirectResponse("/setup", status_code=303)

    tailscale_installed = await _check_tailscale()
    return templates.TemplateResponse("step5_remote.html", {
        "request": request,
        "tailscale_installed": tailscale_installed,
    })


@app.post("/setup/finalize")
async def finalize(request: Request):
    state = _load()
    cameras = state.get("cameras", [])
    if not cameras:
        return RedirectResponse("/setup", status_code=303)

    # Persist camera password to .env
    first_pw = cameras[0].get("password", "")
    if first_pw:
        config_writer.write_camera_password(first_pw)

    # Fill in any cameras that didn't get RTSP URLs from probing
    for cam in cameras:
        if not cam.get("rtsp_sub"):
            cam["rtsp_sub"] = _safe_rtsp_url(
                cam["username"], cam["password"], cam["ip"], "h264Preview_01_sub"
            )
            cam["rtsp_main"] = _safe_rtsp_url(
                cam["username"], cam["password"], cam["ip"], "h264Preview_01_main"
            )
        # Invalidate any stale thumbnail so the new credentials are used next time
        thumbnails.invalidate(cam["rtsp_sub"])

    config_writer.write_frigate_config(cameras)
    config_writer.write_ha_cameras(cameras)
    config_writer.write_mqtt_sensors(cameras)
    config_writer.write_lovelace_dashboard(cameras)
    config_writer.write_ha_automations(cameras, state.get("notify_method", "companion"))
    config_writer.restart_frigate()

    state["finalized"] = True
    state["cameras"] = cameras
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

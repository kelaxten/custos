"""
Writes Frigate and Home Assistant config files from wizard state.

Reads the existing Frigate config skeleton (which has detector, ffmpeg, record,
and snapshot settings already dialled in for Pi 5) and replaces only the
`cameras:` section.  All other tuning is preserved.
"""

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

FRIGATE_CONFIG = Path(os.environ.get("FRIGATE_CONFIG", "/config/frigate/config.yml"))
HA_CONFIG_DIR = Path(os.environ.get("HA_CONFIG_DIR", "/config/homeassistant"))
ENV_FILE = Path(os.environ.get("ENV_FILE", "/custos/.env"))


# ─── Frigate ──────────────────────────────────────────────────────────────────

def build_camera_block(cam: dict) -> dict:
    detect_objects = []
    if cam.get("detect_person", True):
        detect_objects.append("person")
    if cam.get("detect_car", True):
        detect_objects.append("car")
    if cam.get("detect_animal", False):
        detect_objects.append("cat")
        detect_objects.append("dog")

    block: dict[str, Any] = {
        "enabled": True,
        "ffmpeg": {
            "inputs": [
                {
                    "path": cam["rtsp_sub"],
                    "roles": ["detect"],
                    "input_args": "preset-rtsp-restream",
                },
                {
                    "path": cam["rtsp_main"],
                    "roles": ["record"],
                    "input_args": "preset-rtsp-restream",
                },
            ]
        },
        "detect": {
            "width": cam.get("detect_width", 640),
            "height": cam.get("detect_height", 480),
            "fps": cam.get("fps", 5),
        },
        "objects": {
            "track": detect_objects,
        },
        "snapshots": {"enabled": True},
        "record": {"enabled": True},
    }
    return block


def write_frigate_config(cameras: list[dict]) -> None:
    with open(FRIGATE_CONFIG) as f:
        config = yaml.safe_load(f)

    config["cameras"] = {cam["id"]: build_camera_block(cam) for cam in cameras}

    with open(FRIGATE_CONFIG, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ─── Home Assistant automations ───────────────────────────────────────────────

def _person_automation(cameras: list[dict]) -> dict:
    return {
        "id": "custos_person_detected",
        "alias": "Person Detected — Push Notification",
        "mode": "parallel",
        "max": 10,
        "trigger": [{"platform": "mqtt", "topic": "frigate/events"}],
        "condition": [{
            "condition": "template",
            "value_template": (
                "{{ trigger.payload_json.type == 'new'"
                " and trigger.payload_json.after.label == 'person'"
                " and trigger.payload_json.after.score | float >= 0.75 }}"
            ),
        }],
        "action": [
            {
                "variables": {
                    "camera": "{{ trigger.payload_json.after.camera }}",
                    "camera_pretty": "{{ trigger.payload_json.after.camera | replace('_', ' ') | title }}",
                    "event_id": "{{ trigger.payload_json.after.id }}",
                }
            },
            {
                "service": "notify.mobile_app_all_devices",
                "data": {
                    "title": "Person Detected",
                    "message": "{{ camera_pretty }}",
                    "data": {
                        "image": "http://127.0.0.1:5000/api/events/{{ event_id }}/snapshot.jpg",
                        "url": "http://custos.local/frigate/events/{{ event_id }}",
                        "channel": "custos-alerts",
                        "tag": "custos-person-{{ camera }}",
                        "importance": "high",
                        "ttl": 0,
                    },
                },
            },
        ],
    }


def _vehicle_automation(cameras: list[dict]) -> dict:
    return {
        "id": "custos_vehicle_detected",
        "alias": "Vehicle Detected — Push Notification",
        "mode": "parallel",
        "max": 10,
        "trigger": [{"platform": "mqtt", "topic": "frigate/events"}],
        "condition": [{
            "condition": "template",
            "value_template": (
                "{{ trigger.payload_json.type == 'new'"
                " and trigger.payload_json.after.label == 'car'"
                " and trigger.payload_json.after.score | float >= 0.75 }}"
            ),
        }],
        "action": [
            {
                "variables": {
                    "camera": "{{ trigger.payload_json.after.camera }}",
                    "camera_pretty": "{{ trigger.payload_json.after.camera | replace('_', ' ') | title }}",
                    "event_id": "{{ trigger.payload_json.after.id }}",
                }
            },
            {
                "service": "notify.mobile_app_all_devices",
                "data": {
                    "title": "Vehicle Detected",
                    "message": "{{ camera_pretty }}",
                    "data": {
                        "image": "http://127.0.0.1:5000/api/events/{{ event_id }}/snapshot.jpg",
                        "url": "http://custos.local/frigate/events/{{ event_id }}",
                        "channel": "custos-alerts",
                        "tag": "custos-vehicle-{{ camera }}",
                    },
                },
            },
        ],
    }


def write_ha_automations(cameras: list[dict], notify_method: str = "companion") -> None:
    automations = [_person_automation(cameras), _vehicle_automation(cameras)]
    out = HA_CONFIG_DIR / "automations.yaml"
    with open(out, "w") as f:
        yaml.dump(automations, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ─── HA camera entities (cameras.yaml) ───────────────────────────────────────

def write_ha_cameras(cameras: list[dict]) -> None:
    """Generate cameras.yaml: one generic camera entity per Frigate camera."""
    entries = []
    for cam in cameras:
        entries.append({
            "platform": "generic",
            "name": cam["display_name"],
            "unique_id": f"custos_camera_{cam['id']}",
            "still_image_url": f"http://localhost:5000/api/{cam['id']}/latest.jpg",
            "content_type": "image/jpeg",
            "framerate": 2,
            "verify_ssl": False,
        })
    out = HA_CONFIG_DIR / "cameras.yaml"
    header = (
        "# Camera entities — auto-generated by the Custos setup wizard.\n"
        "# Regenerate by visiting http://custos.local/setup → Reconfigure Cameras.\n\n"
    )
    with open(out, "w") as f:
        f.write(header)
        yaml.dump(entries, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ─── MQTT binary sensors (mqtt_sensors.yaml) ─────────────────────────────────

def write_mqtt_sensors(cameras: list[dict]) -> None:
    """Generate mqtt_sensors.yaml: person + car detection sensors per camera."""
    entries = []
    for cam in cameras:
        cid = cam["id"]
        name = cam["display_name"]
        for label in ("person", "car"):
            entries.append({
                "name": f"{name} {label.capitalize()}",
                "unique_id": f"frigate_{cid}_{label}",
                "state_topic": f"frigate/{cid}/{label}",
                "payload_on": "1",
                "payload_off": "0",
                "device_class": "motion",
                "off_delay": 30,
            })
        if cam.get("detect_animal"):
            entries.append({
                "name": f"{name} Animal",
                "unique_id": f"frigate_{cid}_animal",
                "state_topic": f"frigate/{cid}/cat",  # Frigate uses specific labels
                "payload_on": "1",
                "payload_off": "0",
                "device_class": "motion",
                "off_delay": 30,
            })
    out = HA_CONFIG_DIR / "mqtt_sensors.yaml"
    header = (
        "# MQTT binary sensors — auto-generated by the Custos setup wizard.\n"
        "# Mirrors Frigate per-camera object topics to HA binary sensors.\n\n"
    )
    with open(out, "w") as f:
        f.write(header)
        yaml.dump(entries, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ─── Lovelace dashboard (ui-lovelace.yaml) ───────────────────────────────────

def write_lovelace_dashboard(cameras: list[dict]) -> None:
    """Generate ui-lovelace.yaml from the configured camera list."""

    def _camera_glance_entity(cam: dict, label: str, icon: str) -> dict:
        cid = cam["id"]
        return {"entity": f"binary_sensor.{cid}_{label}", "name": cam["display_name"], "icon": icon}

    def _picture_glance_card(cam: dict) -> dict:
        cid = cam["id"]
        entities = [{"entity": f"binary_sensor.{cid}_person", "icon": "mdi:walk"}]
        if cam.get("detect_car", True):
            entities.append({"entity": f"binary_sensor.{cid}_car", "icon": "mdi:car"})
        if cam.get("detect_animal"):
            entities.append({"entity": f"binary_sensor.{cid}_animal", "icon": "mdi:paw"})
        return {
            "type": "picture-glance",
            "title": cam["display_name"],
            "camera_image": f"camera.{cid}",
            "entities": entities,
            "tap_action": {"action": "url", "url_path": f"/frigate/cameras/{cid}"},
        }

    def _recording_control_entities(cam: dict) -> list:
        cid = cam["id"]
        name = cam["display_name"]
        return [
            {"entity": f"switch.frigate_{cid}_recordings", "name": f"{name} · Recording"},
            {"entity": f"switch.frigate_{cid}_detect", "name": f"{name} · Detection"},
        ]

    # Build views
    all_detection_entities = []
    for cam in cameras:
        cid = cam["id"]
        all_detection_entities.append(f"binary_sensor.{cid}_person")
        if cam.get("detect_car", True):
            all_detection_entities.append(f"binary_sensor.{cid}_car")

    glance_entities = []
    for cam in cameras:
        cid = cam["id"]
        glance_entities.append({"entity": f"binary_sensor.{cid}_person", "name": cam["display_name"], "icon": "mdi:walk"})
        if cam.get("detect_car", True):
            glance_entities.append({"entity": f"binary_sensor.{cid}_car", "name": cam["display_name"], "icon": "mdi:car"})

    fps_entities = [{"entity": "sensor.frigate_detection_fps", "name": "Detection FPS", "icon": "mdi:speedometer"}]
    for cam in cameras:
        fps_entities.append({"entity": f"sensor.frigate_{cam['id']}_camera_fps", "name": f"{cam['display_name']} FPS"})
    fps_entities.append({"type": "weblink", "name": "Open Frigate UI", "url": "/frigate", "icon": "mdi:open-in-new"})

    recording_entities: list = []
    for cam in cameras:
        recording_entities.extend(_recording_control_entities(cam))

    dashboard = {
        "title": "Custos",
        "views": [
            {
                "title": "Cameras",
                "path": "cameras",
                "icon": "mdi:cctv",
                "type": "masonry",
                "badges": [],
                "cards": [
                    {"type": "glance", "show_name": True, "show_icon": True, "show_state": True, "entities": glance_entities},
                    {"type": "grid", "columns": 2, "square": False, "cards": [_picture_glance_card(c) for c in cameras]},
                ],
            },
            {
                "title": "Activity",
                "path": "activity",
                "icon": "mdi:bell-ring",
                "type": "masonry",
                "badges": [],
                "cards": [
                    {"type": "logbook", "title": "Detections — Last 24 Hours", "hours_to_show": 24, "entities": all_detection_entities},
                    {"type": "button", "name": "Browse Event Clips", "icon": "mdi:video-box", "show_name": True,
                     "tap_action": {"action": "url", "url_path": "/frigate/events"}},
                ],
            },
            {
                "title": "System",
                "path": "system",
                "icon": "mdi:server-outline",
                "type": "masonry",
                "badges": [],
                "cards": [
                    {"type": "entities", "title": "Detection Engine", "entities": fps_entities},
                    {"type": "entities", "title": "Recording Controls", "entities": recording_entities},
                ],
            },
        ],
    }

    out = HA_CONFIG_DIR / "ui-lovelace.yaml"
    header = (
        "# Custos Lovelace dashboard — auto-generated by the setup wizard.\n"
        "# Regenerate by visiting http://custos.local/setup → Reconfigure Cameras.\n\n"
    )
    with open(out, "w") as f:
        f.write(header)
        yaml.dump(dashboard, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ─── .env password sync ───────────────────────────────────────────────────────

def write_camera_password(password: str) -> None:
    """Update FRIGATE_RTSP_PASSWORD in the .env file."""
    if not ENV_FILE.exists():
        ENV_FILE.write_text(f"FRIGATE_RTSP_PASSWORD={password}\n")
        return

    lines = ENV_FILE.read_text().splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("FRIGATE_RTSP_PASSWORD="):
            new_lines.append(f"FRIGATE_RTSP_PASSWORD={password}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"FRIGATE_RTSP_PASSWORD={password}")
    ENV_FILE.write_text("\n".join(new_lines) + "\n")


# ─── Service restart ──────────────────────────────────────────────────────────

def is_already_configured() -> bool:
    """Return True if Frigate config already has at least one camera defined."""
    try:
        with open(FRIGATE_CONFIG) as f:
            config = yaml.safe_load(f) or {}
        cameras = config.get("cameras", {})
        return bool(cameras)
    except Exception:
        return False


def restart_frigate() -> None:
    """Signal Frigate to reload its config via its HTTP API."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "http://frigate:5000/api/config/save",
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # Frigate will pick up the new config on its next health cycle


def reload_ha() -> None:
    """Ask Home Assistant to reload automations."""
    import urllib.request, json
    try:
        data = json.dumps({}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8123/api/services/automation/reload",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

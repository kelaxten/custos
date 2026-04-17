"""
Integration tests for the FastAPI wizard routes.

Uses FastAPI's TestClient (sync) and patches out all I/O — no real cameras,
no real files outside tmp_path, no network calls.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── App setup ────────────────────────────────────────────────────────────────
# Import app only after patching environment-level side effects in thumbnails.py

@pytest.fixture(autouse=True)
def _patch_thumb_dir(tmp_path, monkeypatch):
    """Redirect thumbnail directory to tmp_path before app is imported."""
    monkeypatch.setenv("THUMB_DIR", str(tmp_path / "thumbs"))


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "wizard-state.json"
    import main as main_mod
    monkeypatch.setattr(main_mod, "STATE_FILE", path)
    return path


def _fake_template_response(name: str, context: dict, status_code: int = 200):
    """Return a plain HTML response stub instead of rendering real Jinja2 templates.

    Avoids Jinja2/Starlette version mismatches in the test environment while
    still exercising all route logic.  The body contains JSON-encoded context
    so assertions can inspect what the route passed to the template.
    """
    from fastapi.responses import HTMLResponse
    import json as _json
    safe_ctx = {k: str(v) for k, v in context.items() if k != "request"}
    body = f"<!-- template:{name} --><pre>{_json.dumps(safe_ctx)}</pre>"
    return HTMLResponse(content=body, status_code=status_code)


@pytest.fixture
def client(state_file, monkeypatch):
    import main as main_mod
    monkeypatch.setattr(main_mod.templates, "TemplateResponse", _fake_template_response)
    from main import app
    return TestClient(app, raise_server_exceptions=True)


# ─── GET /setup ───────────────────────────────────────────────────────────────

class TestStep1Welcome:
    def test_renders_welcome_page(self, client):
        with patch("config_writer.is_already_configured", return_value=False):
            resp = client.get("/setup")
        assert resp.status_code == 200
        assert "step1_welcome" in resp.text

    def test_passes_configured_false_to_template(self, client):
        with patch("config_writer.is_already_configured", return_value=False):
            resp = client.get("/setup")
        assert "False" in resp.text

    def test_passes_configured_true_to_template(self, client):
        with patch("config_writer.is_already_configured", return_value=True):
            resp = client.get("/setup")
        assert "True" in resp.text


# ─── POST /setup/scan → GET /setup/scan/poll ──────────────────────────────────

class TestScan:
    def test_post_scan_redirects_to_poll(self, client):
        resp = client.post("/setup/scan", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/setup/scan/poll"

    def test_poll_returns_200_while_scanning(self, client, state_file):
        state_file.write_text(json.dumps({"scan_status": "scanning"}))
        resp = client.get("/setup/scan/poll")
        assert resp.status_code == 200
        assert "_scan_polling" in resp.text   # polling fragment template

    def test_poll_shows_camera_data_when_done(self, client, state_file):
        state_file.write_text(json.dumps({
            "scan_status": "done",
            "discovered": [{"ip": "192.168.1.101", "manufacturer": "Reolink", "onvif_url": ""}],
        }))
        resp = client.get("/setup/scan/poll")
        assert resp.status_code == 200
        # Template context includes discovered list — serialised in stub body
        assert "192.168.1.101" in resp.text

    def test_poll_passes_error_to_template(self, client, state_file):
        state_file.write_text(json.dumps({
            "scan_status": "error",
            "scan_error": "socket timeout",
            "discovered": [],
        }))
        resp = client.get("/setup/scan/poll")
        assert resp.status_code == 200
        assert "socket timeout" in resp.text


# ─── POST /setup/cameras ──────────────────────────────────────────────────────

class TestSaveCameras:
    def _mock_probe_unauthenticated(self, cam):
        from discover import DiscoveredDevice
        d = DiscoveredDevice(ip=cam["ip"])
        d.authenticated = False
        return d

    def test_valid_camera_saved_to_state(self, client, state_file):
        async def _fake_probe(device, username, password):
            device.rtsp_sub = f"rtsp://admin:pw@{device.ip}:554/sub"
            device.rtsp_main = f"rtsp://admin:pw@{device.ip}:554/main"
            device.authenticated = True
            device.manufacturer = "Reolink"
            return device

        async def _fake_thumb(url):
            return "/static/camera-placeholder.svg"

        with patch("discover.probe_credentials", side_effect=_fake_probe), \
             patch("thumbnails.capture", side_effect=_fake_thumb):
            resp = client.post("/setup/cameras", data={
                "cam_0_ip": "192.168.1.101",
                "cam_0_name": "Front Door",
                "cam_0_username": "admin",
                "cam_0_password": "secret",
            }, follow_redirects=False)

        assert resp.status_code == 303
        state = json.loads(state_file.read_text())
        assert len(state["cameras"]) == 1
        assert state["cameras"][0]["id"] == "front_door"

    def test_invalid_ip_is_rejected(self, client, state_file):
        resp = client.post("/setup/cameras", data={
            "cam_0_ip": "8.8.8.8",  # public IP — should be blocked
            "cam_0_name": "Bad Camera",
            "cam_0_username": "admin",
            "cam_0_password": "pw",
        }, follow_redirects=False)

        assert resp.status_code == 303
        if state_file.exists():
            state = json.loads(state_file.read_text())
            assert len(state.get("cameras", [])) == 0

    def test_loopback_ip_is_rejected(self, client, state_file):
        resp = client.post("/setup/cameras", data={
            "cam_0_ip": "127.0.0.1",
            "cam_0_name": "Local",
            "cam_0_username": "admin",
            "cam_0_password": "pw",
        }, follow_redirects=False)

        assert resp.status_code == 303
        if state_file.exists():
            state = json.loads(state_file.read_text())
            assert len(state.get("cameras", [])) == 0

    def test_duplicate_names_get_unique_ids(self, client, state_file):
        async def _fake_probe(device, username, password):
            return device  # unauthenticated, no RTSP URLs

        with patch("discover.probe_credentials", side_effect=_fake_probe):
            resp = client.post("/setup/cameras", data={
                "cam_0_ip": "192.168.1.101",
                "cam_0_name": "Camera",
                "cam_0_username": "admin",
                "cam_0_password": "pw",
                "cam_1_ip": "192.168.1.102",
                "cam_1_name": "Camera",
                "cam_1_username": "admin",
                "cam_1_password": "pw",
            }, follow_redirects=False)

        assert resp.status_code == 303
        state = json.loads(state_file.read_text())
        ids = [c["id"] for c in state["cameras"]]
        assert len(ids) == len(set(ids)), "Camera IDs must be unique"


# ─── POST /setup/detect ───────────────────────────────────────────────────────

class TestSaveDetect:
    def test_detection_prefs_saved(self, client, state_file):
        state_file.write_text(json.dumps({
            **{"scan_status": "done", "discovered": [], "detection": {},
               "notify_method": "companion", "tailscale_done": False, "finalized": False},
            "cameras": [{"id": "front_door", "display_name": "Front Door"}],
        }))
        resp = client.post("/setup/detect", data={
            "front_door_person": "on",
            "front_door_car": "on",
        }, follow_redirects=False)
        assert resp.status_code == 303
        state = json.loads(state_file.read_text())
        assert state["detection"]["front_door"]["person"] is True
        assert state["detection"]["front_door"]["animal"] is False

    def test_redirects_to_setup_when_no_cameras(self, client, state_file):
        resp = client.get("/setup/detect", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/setup"


# ─── POST /setup/notify ───────────────────────────────────────────────────────

class TestSaveNotify:
    def _with_cameras(self, state_file):
        state_file.write_text(json.dumps({
            "scan_status": "done", "discovered": [], "detection": {},
            "notify_method": "companion", "tailscale_done": False, "finalized": False,
            "cameras": [{"id": "c1", "display_name": "C1"}],
        }))

    def test_companion_saved(self, client, state_file):
        self._with_cameras(state_file)
        resp = client.post("/setup/notify", data={"method": "companion"}, follow_redirects=False)
        assert resp.status_code == 303
        assert json.loads(state_file.read_text())["notify_method"] == "companion"

    def test_invalid_method_defaults_to_companion(self, client, state_file):
        self._with_cameras(state_file)
        resp = client.post("/setup/notify", data={"method": "evil_method"}, follow_redirects=False)
        assert resp.status_code == 303
        assert json.loads(state_file.read_text())["notify_method"] == "companion"


# ─── POST /setup/finalize ─────────────────────────────────────────────────────

class TestFinalize:
    def _full_state(self, state_file):
        state_file.write_text(json.dumps({
            "scan_status": "done", "discovered": [], "detection": {},
            "notify_method": "companion", "tailscale_done": False, "finalized": False,
            "cameras": [{
                "id": "front_door",
                "display_name": "Front Door",
                "ip": "192.168.1.101",
                "username": "admin",
                "password": "secret",
                "rtsp_sub": "rtsp://admin:secret@192.168.1.101:554/sub",
                "rtsp_main": "rtsp://admin:secret@192.168.1.101:554/main",
                "detect_person": True,
                "detect_car": True,
                "detect_animal": False,
            }],
        }))

    def test_finalize_calls_all_writers(self, client, state_file, tmp_path, monkeypatch):
        self._full_state(state_file)
        import config_writer as cw
        frigate_cfg = tmp_path / "frigate" / "config.yml"
        frigate_cfg.parent.mkdir()
        frigate_cfg.write_text("")
        ha_dir = tmp_path / "ha"
        ha_dir.mkdir()
        monkeypatch.setattr(cw, "FRIGATE_CONFIG", frigate_cfg)
        monkeypatch.setattr(cw, "HA_CONFIG_DIR", ha_dir)

        with patch("config_writer.restart_frigate"):
            with patch("config_writer.write_camera_password"):
                resp = client.post("/setup/finalize", follow_redirects=False)

        assert resp.status_code == 303
        assert (ha_dir / "cameras.yaml").exists()
        assert (ha_dir / "mqtt_sensors.yaml").exists()
        assert (ha_dir / "ui-lovelace.yaml").exists()
        assert (ha_dir / "automations.yaml").exists()

    def test_finalize_builds_encoded_rtsp_url_when_missing(self, client, state_file, tmp_path, monkeypatch):
        """Cameras without probed RTSP URLs get URL-encoded fallback URLs."""
        state_file.write_text(json.dumps({
            "scan_status": "done", "discovered": [], "detection": {},
            "notify_method": "companion", "tailscale_done": False, "finalized": False,
            "cameras": [{
                "id": "cam1",
                "display_name": "Cam 1",
                "ip": "192.168.1.101",
                "username": "admin",
                "password": "p@ss:word",  # special chars that need URL encoding
                "rtsp_sub": "",
                "rtsp_main": "",
                "detect_person": True,
                "detect_car": True,
                "detect_animal": False,
            }],
        }))
        import config_writer as cw
        frigate_cfg = tmp_path / "frigate.yml"
        frigate_cfg.write_text("")
        ha_dir = tmp_path / "ha"
        ha_dir.mkdir()
        monkeypatch.setattr(cw, "FRIGATE_CONFIG", frigate_cfg)
        monkeypatch.setattr(cw, "HA_CONFIG_DIR", ha_dir)

        with patch("config_writer.restart_frigate"):
            with patch("config_writer.write_camera_password"):
                client.post("/setup/finalize", follow_redirects=False)

        state = json.loads(state_file.read_text())
        rtsp_url = state["cameras"][0]["rtsp_sub"]
        # Special chars must be percent-encoded, not raw
        assert "@" not in rtsp_url.split("@")[0].split("://")[1]
        assert "p%40ss%3Aword" in rtsp_url

    def test_finalize_redirects_to_setup_when_no_cameras(self, client, state_file):
        resp = client.post("/setup/finalize", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/setup"

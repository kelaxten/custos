"""Tests for config generation (Frigate YAML, HA cameras/sensors/dashboard)."""

import textwrap
from pathlib import Path

import pytest
import yaml

from config_writer import (
    build_camera_block,
    is_already_configured,
    write_frigate_config,
    write_ha_cameras,
    write_lovelace_dashboard,
    write_mqtt_sensors,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect all config_writer path constants to tmp_path."""
    import config_writer as cw
    frigate_cfg = tmp_path / "frigate" / "config.yml"
    frigate_cfg.parent.mkdir()
    ha_dir = tmp_path / "homeassistant"
    ha_dir.mkdir()
    monkeypatch.setattr(cw, "FRIGATE_CONFIG", frigate_cfg)
    monkeypatch.setattr(cw, "HA_CONFIG_DIR", ha_dir)
    return tmp_path


@pytest.fixture
def minimal_frigate_config(tmp_config_dir):
    """Write the minimum Frigate config skeleton (no cameras section)."""
    import config_writer as cw
    cw.FRIGATE_CONFIG.write_text(textwrap.dedent("""\
        mqtt:
          enabled: true
          host: 127.0.0.1
        detectors:
          cpu:
            type: cpu
    """))
    return cw.FRIGATE_CONFIG


@pytest.fixture
def two_cameras():
    return [
        {
            "id": "front_door",
            "display_name": "Front Door",
            "ip": "192.168.1.101",
            "username": "admin",
            "password": "secret",
            "rtsp_sub": "rtsp://admin:secret@192.168.1.101:554/h264Preview_01_sub",
            "rtsp_main": "rtsp://admin:secret@192.168.1.101:554/h264Preview_01_main",
            "detect_person": True,
            "detect_car": True,
            "detect_animal": False,
        },
        {
            "id": "driveway",
            "display_name": "Driveway",
            "ip": "192.168.1.102",
            "username": "admin",
            "password": "secret2",
            "rtsp_sub": "rtsp://admin:secret2@192.168.1.102:554/h264Preview_01_sub",
            "rtsp_main": "rtsp://admin:secret2@192.168.1.102:554/h264Preview_01_main",
            "detect_person": True,
            "detect_car": False,
            "detect_animal": True,
        },
    ]


# ─── build_camera_block ───────────────────────────────────────────────────────

class TestBuildCameraBlock:
    def test_person_and_car_tracked_by_default(self, two_cameras):
        block = build_camera_block(two_cameras[0])
        assert "person" in block["objects"]["track"]
        assert "car" in block["objects"]["track"]

    def test_car_excluded_when_disabled(self, two_cameras):
        cam = {**two_cameras[0], "detect_car": False}
        block = build_camera_block(cam)
        assert "car" not in block["objects"]["track"]

    def test_animal_labels_added_when_enabled(self, two_cameras):
        block = build_camera_block(two_cameras[1])  # detect_animal=True
        assert "cat" in block["objects"]["track"]
        assert "dog" in block["objects"]["track"]

    def test_rtsp_paths_present(self, two_cameras):
        block = build_camera_block(two_cameras[0])
        inputs = block["ffmpeg"]["inputs"]
        roles = {inp["roles"][0]: inp["path"] for inp in inputs}
        assert "detect" in roles
        assert "record" in roles
        assert "192.168.1.101" in roles["detect"]

    def test_detect_dimensions_default(self, two_cameras):
        block = build_camera_block(two_cameras[0])
        assert block["detect"]["width"] == 640
        assert block["detect"]["height"] == 480
        assert block["detect"]["fps"] == 5


# ─── write_frigate_config ─────────────────────────────────────────────────────

class TestWriteFrigateConfig:
    def test_writes_cameras_section(self, minimal_frigate_config, two_cameras):
        write_frigate_config(two_cameras)
        result = yaml.safe_load(minimal_frigate_config.read_text())
        assert "front_door" in result["cameras"]
        assert "driveway" in result["cameras"]

    def test_preserves_existing_sections(self, minimal_frigate_config, two_cameras):
        write_frigate_config(two_cameras)
        result = yaml.safe_load(minimal_frigate_config.read_text())
        assert "detectors" in result
        assert result["detectors"]["cpu"]["type"] == "cpu"

    def test_handles_empty_config_file(self, tmp_config_dir, two_cameras):
        import config_writer as cw
        cw.FRIGATE_CONFIG.write_text("")
        write_frigate_config(two_cameras)  # must not crash
        result = yaml.safe_load(cw.FRIGATE_CONFIG.read_text())
        assert "cameras" in result

    def test_handles_missing_config_file(self, tmp_config_dir, two_cameras):
        import config_writer as cw
        # File does not exist at all
        assert not cw.FRIGATE_CONFIG.exists()
        write_frigate_config(two_cameras)  # must not crash
        result = yaml.safe_load(cw.FRIGATE_CONFIG.read_text())
        assert "cameras" in result


# ─── is_already_configured ────────────────────────────────────────────────────

class TestIsAlreadyConfigured:
    def test_false_when_no_cameras(self, tmp_config_dir):
        import config_writer as cw
        cw.FRIGATE_CONFIG.write_text("detectors:\n  cpu:\n    type: cpu\n")
        assert is_already_configured() is False

    def test_true_when_cameras_present(self, tmp_config_dir, two_cameras):
        import config_writer as cw
        cw.FRIGATE_CONFIG.write_text("")
        write_frigate_config(two_cameras)
        assert is_already_configured() is True

    def test_false_when_file_missing(self, tmp_config_dir):
        assert is_already_configured() is False


# ─── write_ha_cameras ─────────────────────────────────────────────────────────

class TestWriteHaCameras:
    def test_creates_cameras_yaml(self, tmp_config_dir, two_cameras):
        write_ha_cameras(two_cameras)
        import config_writer as cw
        out = cw.HA_CONFIG_DIR / "cameras.yaml"
        assert out.exists()
        entries = yaml.safe_load(out.read_text())
        assert len(entries) == 2

    def test_entity_uses_frigate_snapshot_url(self, tmp_config_dir, two_cameras):
        write_ha_cameras(two_cameras)
        import config_writer as cw
        entries = yaml.safe_load((cw.HA_CONFIG_DIR / "cameras.yaml").read_text())
        urls = [e["still_image_url"] for e in entries]
        assert any("front_door" in u for u in urls)
        assert all("localhost:5000" in u for u in urls)

    def test_unique_ids_are_stable(self, tmp_config_dir, two_cameras):
        write_ha_cameras(two_cameras)
        import config_writer as cw
        entries = yaml.safe_load((cw.HA_CONFIG_DIR / "cameras.yaml").read_text())
        ids = [e["unique_id"] for e in entries]
        assert len(ids) == len(set(ids))


# ─── write_mqtt_sensors ───────────────────────────────────────────────────────

class TestWriteMqttSensors:
    def test_creates_sensor_per_label(self, tmp_config_dir, two_cameras):
        write_mqtt_sensors(two_cameras)
        import config_writer as cw
        entries = yaml.safe_load((cw.HA_CONFIG_DIR / "mqtt_sensors.yaml").read_text())
        topics = [e["state_topic"] for e in entries]
        assert "frigate/front_door/person" in topics
        assert "frigate/front_door/car" in topics
        assert "frigate/driveway/person" in topics

    def test_animal_sensor_added_when_enabled(self, tmp_config_dir, two_cameras):
        write_mqtt_sensors(two_cameras)
        import config_writer as cw
        entries = yaml.safe_load((cw.HA_CONFIG_DIR / "mqtt_sensors.yaml").read_text())
        topics = [e["state_topic"] for e in entries]
        assert "frigate/driveway/cat" in topics  # driveway has detect_animal=True

    def test_animal_sensor_absent_when_disabled(self, tmp_config_dir, two_cameras):
        write_mqtt_sensors(two_cameras)
        import config_writer as cw
        entries = yaml.safe_load((cw.HA_CONFIG_DIR / "mqtt_sensors.yaml").read_text())
        topics = [e["state_topic"] for e in entries]
        assert "frigate/front_door/cat" not in topics  # front_door has detect_animal=False

    def test_unique_ids_are_stable(self, tmp_config_dir, two_cameras):
        write_mqtt_sensors(two_cameras)
        import config_writer as cw
        entries = yaml.safe_load((cw.HA_CONFIG_DIR / "mqtt_sensors.yaml").read_text())
        ids = [e["unique_id"] for e in entries]
        assert len(ids) == len(set(ids))


# ─── write_lovelace_dashboard ─────────────────────────────────────────────────

class TestWriteLovelaceDashboard:
    def test_creates_lovelace_yaml(self, tmp_config_dir, two_cameras):
        write_lovelace_dashboard(two_cameras)
        import config_writer as cw
        assert (cw.HA_CONFIG_DIR / "ui-lovelace.yaml").exists()

    def test_has_three_views(self, tmp_config_dir, two_cameras):
        write_lovelace_dashboard(two_cameras)
        import config_writer as cw
        dash = yaml.safe_load((cw.HA_CONFIG_DIR / "ui-lovelace.yaml").read_text())
        assert len(dash["views"]) == 3

    def test_camera_ids_appear_in_cameras_view(self, tmp_config_dir, two_cameras):
        write_lovelace_dashboard(two_cameras)
        import config_writer as cw
        raw = (cw.HA_CONFIG_DIR / "ui-lovelace.yaml").read_text()
        assert "front_door" in raw
        assert "driveway" in raw

    def test_detection_entities_in_activity_view(self, tmp_config_dir, two_cameras):
        write_lovelace_dashboard(two_cameras)
        import config_writer as cw
        raw = (cw.HA_CONFIG_DIR / "ui-lovelace.yaml").read_text()
        assert "binary_sensor.front_door_person" in raw
        assert "binary_sensor.driveway_person" in raw

    def test_single_camera_works(self, tmp_config_dir):
        cam = [{
            "id": "garage",
            "display_name": "Garage",
            "ip": "192.168.1.103",
            "detect_person": True,
            "detect_car": True,
            "detect_animal": False,
        }]
        write_lovelace_dashboard(cam)
        import config_writer as cw
        dash = yaml.safe_load((cw.HA_CONFIG_DIR / "ui-lovelace.yaml").read_text())
        assert dash["title"] == "Custos"

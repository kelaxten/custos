"""
Custos Energy — MQTT publisher.

A tiny daemon that, every PUBLISH_INTERVAL seconds:
  1. Computes the current tariff snapshot (custos_energy.tariff.snapshot).
  2. Publishes it (retained) to the state topic as JSON.

On startup it also publishes Home Assistant MQTT-discovery configs so HA
auto-creates the entities below with no manual YAML for the sensors:

  sensor.custos_current_tariff     -> off_peak | mid_peak | peak
  sensor.custos_current_rate       -> $/kWh  (use as Energy dashboard price entity)
  sensor.custos_next_tariff_change -> timestamp of next period change
  sensor.custos_next_rate          -> $/kWh after the next change

Run as a Docker service alongside Mosquitto (see docker-compose.snippet.yml)
or via the provided systemd unit.
"""

from __future__ import annotations

import json
import logging
import signal
import time as _time
from datetime import datetime

import paho.mqtt.client as mqtt

from . import config
from .tariff import snapshot

log = logging.getLogger("custos.energy")

_DEVICE = {
    "identifiers": ["custos_energy"],
    "name": "Custos Energy",
    "manufacturer": "Custos",
    "model": "TOU Tariff Engine",
}

# (object_id, friendly name, value_template, unit, device_class, state_class, icon)
_SENSORS = [
    ("custos_current_tariff", "Current Tariff",
     "{{ value_json.period }}", None, None, None, "mdi:transmission-tower"),
    ("custos_current_rate", "Current Electricity Rate",
     "{{ value_json.rate }}", "USD/kWh", "monetary", "measurement", "mdi:cash"),
    ("custos_next_tariff_change", "Next Tariff Change",
     "{{ value_json.next_change }}", None, "timestamp", None, "mdi:clock-start"),
    ("custos_next_rate", "Next Electricity Rate",
     "{{ value_json.next_rate }}", "USD/kWh", "monetary", "measurement", "mdi:cash-clock"),
]


def _discovery_payloads():
    for obj_id, name, tmpl, unit, dev_class, state_class, icon in _SENSORS:
        topic = f"{config.DISCOVERY_PREFIX}/sensor/{obj_id}/config"
        cfg = {
            "name": name,
            "unique_id": obj_id,
            "state_topic": config.STATE_TOPIC,
            "value_template": tmpl,
            "json_attributes_topic": config.STATE_TOPIC,
            "device": _DEVICE,
            "icon": icon,
        }
        if unit:
            cfg["unit_of_measurement"] = unit
        if dev_class:
            cfg["device_class"] = dev_class
        if state_class:
            cfg["state_class"] = state_class
        yield topic, cfg


def _publish_discovery(client: mqtt.Client) -> None:
    for topic, cfg in _discovery_payloads():
        client.publish(topic, json.dumps(cfg), qos=1, retain=True)
    log.info("Published %d HA discovery configs", len(_SENSORS))


def _publish_state(client: mqtt.Client) -> dict:
    payload = snapshot(datetime.now(), rates=config.RATES, observed=config.OBSERVED)
    client.publish(config.STATE_TOPIC, json.dumps(payload), qos=1, retain=True)
    return payload


def _make_client() -> mqtt.Client:
    client = mqtt.Client(client_id="custos-energy")
    if config.MQTT_USERNAME:
        client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    # Last-will so HA can see the engine go offline.
    client.will_set(f"{config.STATE_TOPIC}/availability", "offline",
                    qos=1, retain=True)
    return client


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    client = _make_client()
    client.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)
    client.loop_start()
    client.publish(f"{config.STATE_TOPIC}/availability", "online",
                   qos=1, retain=True)
    _publish_discovery(client)

    running = True

    def _stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    log.info("Custos Energy publisher started (interval=%ss, tz=%s)",
             config.PUBLISH_INTERVAL, config.TZ)
    last_period = None
    while running:
        payload = _publish_state(client)
        if payload["period"] != last_period:
            log.info("Tariff = %s ($%.4f/kWh) | next: %s at %s",
                     payload["period"], payload["rate"],
                     payload["next_period"], payload["next_change"])
            last_period = payload["period"]
        for _ in range(config.PUBLISH_INTERVAL):
            if not running:
                break
            _time.sleep(1)

    client.publish(f"{config.STATE_TOPIC}/availability", "offline",
                   qos=1, retain=True)
    client.loop_stop()
    client.disconnect()
    log.info("Custos Energy publisher stopped")


if __name__ == "__main__":
    main()

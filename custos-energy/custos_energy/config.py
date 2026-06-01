"""
Custos Energy — runtime configuration.

All values are overridable via environment variables so rate changes never
require a code edit. Defaults match the rate schedule on file.
"""

from __future__ import annotations

import os

from .tariff import (
    OFF_PEAK, MID_PEAK, PEAK,
    DEFAULT_RATES, DEFAULT_BASE_CHARGE_PER_DAY,
)


def _f(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val not in (None, "") else default


def _b(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# Rates ($/kWh)
RATES = {
    OFF_PEAK: _f("CUSTOS_RATE_OFF_PEAK", DEFAULT_RATES[OFF_PEAK]),
    MID_PEAK: _f("CUSTOS_RATE_MID_PEAK", DEFAULT_RATES[MID_PEAK]),
    PEAK:     _f("CUSTOS_RATE_PEAK", DEFAULT_RATES[PEAK]),
}
BASE_CHARGE_PER_DAY = _f("CUSTOS_BASE_CHARGE_PER_DAY", DEFAULT_BASE_CHARGE_PER_DAY)

# Treat federally-observed dates as holidays for fixed-date holidays that
# fall on a weekend. Verify your utility's policy before enabling.
OBSERVED = _b("CUSTOS_OBSERVED_HOLIDAYS", False)

# MQTT
MQTT_HOST = os.getenv("CUSTOS_MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("CUSTOS_MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("CUSTOS_MQTT_USERNAME") or None
MQTT_PASSWORD = os.getenv("CUSTOS_MQTT_PASSWORD") or None

# Topic layout. State is published retained so HA recovers it on restart.
STATE_TOPIC = os.getenv("CUSTOS_MQTT_STATE_TOPIC", "custos/energy/tariff")
# Home Assistant MQTT discovery prefix (default HA value).
DISCOVERY_PREFIX = os.getenv("CUSTOS_HA_DISCOVERY_PREFIX", "homeassistant")

# How often to recompute and publish (seconds). 60s is plenty; period
# boundaries land on whole minutes.
PUBLISH_INTERVAL = int(os.getenv("CUSTOS_PUBLISH_INTERVAL", "60"))

# Timezone for tariff evaluation. Leave unset to use the container/host local
# time (set TZ in docker-compose). Tariffs are wall-clock, so the timezone
# MUST match your billing locale (America/Los_Angeles for LFP).
TZ = os.getenv("TZ", "America/Los_Angeles")

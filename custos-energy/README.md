# Custos Energy

**Time-of-Use billing optimization for the Custos platform.**

A self-contained module that adds electricity-cost awareness and automated load
shifting to a Custos / Home Assistant deployment on a Raspberry Pi 5. The
billing logic lives in a small, fully-tested Python service; Home Assistant
handles device control and cost accounting. It reuses the Mosquitto MQTT bus
Custos already runs — no new infrastructure.

```
                 ┌──────────────────────┐
   wall clock ──▶│  custos-energy        │   computes current TOU period
                 │  (Python publisher)   │   + $/kWh rate every 60s
                 └──────────┬────────────┘
                            │ MQTT (retained + HA discovery)
                            ▼
                 ┌──────────────────────┐
                 │  Mosquitto (MQTT)     │   existing Custos bus
                 └──────────┬────────────┘
                            ▼
                 ┌──────────────────────┐
                 │  Home Assistant       │   sensors, utility_meter,
   ZBT-2 ───────▶│  + Custos Energy pkg  │   load-shift + thermostat
   (Zigbee/      └──────────┬────────────┘   automations, cost dashboard
    Thread)                 │
                            ▼
              smart outlets · temp sensors · thermostat
```

## Why a Python service instead of pure HA templates

The holiday rules (last-Monday-of-May, fourth-Thursday-of-November, etc.) and
the observed-vs-literal-date question are awkward and error-prone in Jinja. A
~200-line Python module computes them correctly, ships with a 21-case test
suite, and is auditable in the repo — which matches the rest of Custos's
config-generator philosophy. HA then just consumes a clean tariff signal.

## Rate schedule (defaults)

| Period   | Window (Mon–Sat)         | Window (Sun & holidays) | $/kWh    |
|----------|--------------------------|-------------------------|----------|
| Off-Peak | 12am–6am                 | 12am–6am                | 0.0882   |
| Mid-Peak | 6am–5pm, 9pm–12am        | 6am–12am                | 0.1543   |
| Peak     | 5pm–9pm                  | *(none)*                | 0.1763   |

Base service charge: **$0.4262 / day** (≈ $12.79–13.21 / month).
Holidays: New Year's, Memorial, Independence, Labor, Thanksgiving, Christmas.

All rates are environment-overridable — see the Custos Energy section of
`.env.example` (or `docker-compose.snippet.yml` for a standalone deploy).

## Layout

```
custos-energy/
├── custos_energy/
│   ├── tariff.py        # the auditable core: period + rate from a datetime
│   ├── config.py        # env-driven rates / MQTT / holiday settings
│   └── publisher.py     # MQTT daemon + HA discovery
├── tests/test_tariff.py # 21 boundary/holiday/next-change tests
├── homeassistant/packages/
│   ├── custos_energy.yaml             # helpers, meter, cost/savings sensors
│   └── custos_energy_automations.yaml # load shifting + thermostat
├── Dockerfile · docker-compose.snippet.yml · custos-energy.service
└── requirements.txt
```

## Install

This module is already wired into the main Custos repo: the `custos-energy`
service is defined in the root `docker-compose.yml`, the HA packages ship in
`config/homeassistant/packages/`, and `configuration.yaml` already enables
`packages: !include_dir_named packages`. The steps below are what that wiring
does — useful for a standalone deploy or to understand the moving parts.

### 1. Run the publisher

**Docker (recommended, fits the Custos stack):** it's part of the stack —
`docker compose up -d custos-energy` brings it up alongside Mosquitto. Set the
rate/timezone overrides in `.env` (see `.env.example`). The standalone service
definition lives in `docker-compose.snippet.yml` for reference.

**Bare metal:** `pip install -r requirements.txt`, copy to `/opt/custos-energy`,
install `custos-energy.service`, `systemctl enable --now custos-energy`.

> **Timezone matters.** Tariffs are wall-clock. Set `CUSTOS_ENERGY_TZ` in `.env`
> (e.g. `America/Los_Angeles` for Lake Forest Park) or the engine will switch
> periods at the wrong hour.

Once running, four entities appear in HA automatically via MQTT discovery:
`sensor.custos_current_tariff`, `sensor.custos_current_rate`,
`sensor.custos_next_tariff_change`, `sensor.custos_next_rate`.

### 2. The HA package

The packages are already in `config/homeassistant/packages/` and loaded via the
`packages: !include_dir_named packages` line in `configuration.yaml`. For a
standalone HA install, ensure `configuration.yaml` has:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Copy both files from `homeassistant/packages/` into your HA `packages/` dir,
edit the `# <-- EDIT` entity IDs to match your devices, and restart HA.

### 3. Define the deferrable-loads group (optional helper)

In `groups.yaml`:

```yaml
custos_deferrable_loads:
  name: Custos Deferrable Loads
  entities:
    - switch.water_heater
    - switch.ev_charger
    - switch.dehumidifier
```

### 4. Wire up cost (the important part)

The cleanest TOU cost tracking is Home Assistant's built-in **Energy dashboard**:

1. Settings → Dashboards → Energy → add your grid consumption source.
2. For cost, choose **"Use an entity with current price"** and select
   `sensor.custos_current_rate`. HA multiplies each consumption increment by the
   live rate, so cost is automatically correct across all three periods.
3. The base service charge isn't per-kWh, so it's tracked separately by
   `sensor.custos_base_charge_mtd` in the package. Add it to a dashboard card.

The package's `utility_meter` additionally splits kWh into off/mid/peak buckets
(`sensor.custos_energy_meter_*`) so you can *see* where your usage lands and
judge what's worth shifting.

## Hardware notes

- **Whole-home metering:** the `utility_meter` source (`sensor.home_energy_total`)
  needs a real whole-home kWh figure — a CT-clamp energy monitor is ideal. If
  you only have smart plugs with energy reporting, point the meter at the sum of
  those plugs (a template sensor) or create per-device meters instead.
- **Smart outlets:** for load shifting, pick Zigbee/Matter plugs that report
  power (W) and energy (kWh), not just on/off — Custos's ZBT-2 handles the
  Zigbee side, and power reporting lets the savings sensor mean something.
- **Thermostat:** any HA `climate` entity works. The automations read its
  `hvac_action`/mode to decide whether to pre-cool or pre-heat.

## Operating notes

- Master switch: `input_boolean.custos_energy_optimize`. Per-load toggles let
  you exempt anything (e.g. don't defer the water heater during a cold snap).
- Pre-conditioning fires at 16:00 only on days with a peak; Sundays/holidays are
  skipped because the tariff never enters `peak` on those days.
- **Holiday observance:** `2026-07-04` falls on a Saturday. By default the engine
  treats the literal date as a holiday (drops peak that day). If your utility
  instead bills the observed weekday, set `CUSTOS_OBSERVED_HOLIDAYS=true` and
  confirm the policy with the utility — it affects which days lose the peak window.
- If rates change, edit them in `.env` (engine) **and** in the rate constants
  inside `custos_energy.yaml`'s cost templates (HA side).

## Tests

```bash
cd custos-energy
python -m unittest discover -s tests -v   # 21 tests
```

Covers every period boundary to the minute, Saturday-vs-Sunday peak handling,
all six holidays incl. floating-date computation, the observed-date flag, and
next-change transitions across day boundaries.

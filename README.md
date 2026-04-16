# Custos

**Open-source home security. No subscriptions. No cloud. No compromises.**

Replace Ring and Reolink cloud apps with something you control end to end —
person/vehicle detection, push notifications to your phone, and local recordings,
all running on a Raspberry Pi sitting in your house.

> *Latin: custos — guardian, protector, keeper*

---

## What You Get

- **Live camera feeds** — all cameras in one place, on your phone or browser
- **AI detection alerts** — person and vehicle notifications with a snapshot image, sent to the Home Assistant Companion app
- **Local recordings** — 7-day continuous recording, searchable event history with clips
- **No subscription** — runs on your hardware, data never leaves your network

Built on [Frigate](https://frigate.video) · [Home Assistant](https://www.home-assistant.io) · [Mosquitto](https://mosquitto.org) · [Caddy](https://caddyserver.com)

---

## Hardware

| What | Spec |
|------|------|
| Hub | Raspberry Pi 5 (4GB or 8GB) |
| Cameras | Any Reolink PoE or WiFi camera with RTSP enabled |
| Optional | Coral USB TPU Accelerator (~$60) for faster detection |

---

## Quick Start

### 1. Flash and boot Raspberry Pi OS Lite (64-bit) on your Pi 5

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Set hostname to `custos`, enable SSH.

### 2. SSH in and clone this repo

```bash
ssh pi@custos.local
git clone https://github.com/kelaxten/custos.git
cd custos
```

### 3. Run setup

```bash
bash scripts/setup.sh
```

### 4. Configure your cameras

Edit `config/frigate/config.yml` — update camera IPs and names.
Edit `.env` — set your Reolink camera password.

See [docs/reolink-cameras.md](docs/reolink-cameras.md) for model-specific RTSP URLs.

### 5. Start

```bash
docker compose up -d
```

### 6. Open the dashboard

**http://custos.local** — create your Home Assistant account (local, no external account needed).

### 7. Install the HA Companion app on your phones

Sign in to `custos.local`. Person and vehicle alerts start arriving automatically.

---

## Full Setup Guide

See **[docs/raspberry-pi-setup.md](docs/raspberry-pi-setup.md)** for detailed step-by-step
instructions including troubleshooting, Coral TPU setup, and remote access via Tailscale.

---

## Project Roadmap

See **[ROADMAP.md](ROADMAP.md)** for the full vision and phased development plan.
Current status: **Phase 1 — Make It Work** (MLP on Pi 5 with Reolink cameras).

---

## License

Apache 2.0

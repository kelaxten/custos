# Custos

**Open-source home security. No subscriptions. No cloud. No compromises.**

Replace Ring and Reolink cloud apps with something you control end to end —
person/vehicle detection, push notifications to your phone, and local recordings,
all running on a Raspberry Pi sitting in your house.

> *Latin: custos — guardian, protector, keeper*

---

## What You Get

- **5-screen setup wizard** — open a browser, follow prompts, done. No YAML editing, no terminal.
- **Auto-discovers cameras** — scans your network for ONVIF cameras, shows live thumbnails
- **AI detection alerts** — person and vehicle notifications with a snapshot image
- **Local recordings** — 7-day continuous recording, searchable event history
- **No subscription** — runs on your hardware, data never leaves your network

Built on [Frigate](https://frigate.video) · [Home Assistant](https://www.home-assistant.io) · [Mosquitto](https://mosquitto.org) · [Caddy](https://caddyserver.com)

---

## Hardware

| What | Spec |
|------|------|
| Hub | Raspberry Pi 5 (4GB or 8GB) |
| Cameras | Any ONVIF-compatible PoE or WiFi camera with RTSP |
| Optional | Coral USB TPU Accelerator (~$60) for faster detection |

See **[docs/hardware.md](docs/hardware.md)** for specific tested models with purchase links.

---

## Quick Start (15 Minutes, No Terminal Required)

### 1. Flash the SD card

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
- Choose **Raspberry Pi OS Lite (64-bit)**
- Set hostname to `custos`
- Enable SSH (optional — you won't need it for setup)
- Flash and insert into your Pi 5

### 2. Boot and run setup

Power on the Pi. From any computer on the same network, open a terminal and run:

```bash
ssh pi@custos.local
curl -fsSL https://raw.githubusercontent.com/kelaxten/custos/main/scripts/setup.sh | bash
```

That's it. Setup takes about 3 minutes. When it finishes you'll see:

```
✓ Custos is running. Open http://custos.local in your browser to complete setup.
```

### 3. Open the setup wizard

Navigate to **http://custos.local** in any browser on your local network.

The wizard walks you through 5 screens:

1. **Find cameras** — scan your network, see live thumbnails
2. **Name cameras** — type "Front Door", "Driveway", etc.
3. **Detection** — toggle: People, Vehicles, Animals (sensible defaults pre-checked)
4. **Notifications** — install the free HA Companion app for push notifications with snapshots
5. **Remote access** — optional Tailscale setup (no port forwarding required)

**Done.** Your dashboard appears with live camera feeds. AI detection starts immediately.

---

## Daily Use

Open **http://custos.local** — or the HA Companion app on your phone.

- Live camera grid, tap to fullscreen
- Timeline of recent AI detections with thumbnails
- Tap any event to see the clip
- Home / Away / Sleep mode toggle

Advanced users can access Frigate directly at **http://custos.local:5000** and Home Assistant at **http://custos.local:8123**.

---

## Troubleshooting

**`custos.local` doesn't load:** Wait 60 seconds after setup completes, then try again. If your router doesn't support mDNS, use the Pi's IP address instead (check your router's admin page).

**Camera not found by scan:** Make sure your camera is on the same network subnet. Check that ONVIF is enabled in the camera's settings. See [docs/reolink-cameras.md](docs/reolink-cameras.md) for Reolink-specific instructions.

**No AI detections:** Detection runs on CPU by default and may be slow on Pi 4. A [Coral USB TPU](docs/hardware.md#ai-accelerator) dramatically improves speed and accuracy.

More: **[docs/raspberry-pi-setup.md](docs/raspberry-pi-setup.md)**

---

## Project Roadmap

See **[ROADMAP.md](ROADMAP.md)** for the full vision and phased development plan.
Current status: **Phase 1 — Make It Work** (MLP on Raspberry Pi 5).

---

## Contributing

Issues and PRs welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

---

## License

Apache 2.0

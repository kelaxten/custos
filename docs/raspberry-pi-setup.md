# Custos on Raspberry Pi 5 — Setup Guide

From a fresh Raspberry Pi 5 to a working home security system with AI detection
and push notifications on your phone. Target time: under 30 minutes.

No YAML editing required. The browser-based setup wizard handles everything.

---

## What You'll Need

| Item | Notes |
|------|-------|
| Raspberry Pi 5 (4GB or 8GB) | 8GB recommended for 4+ cameras |
| microSD card ≥ 64GB (A2-rated) | Or a fast USB SSD (recommended for long-term use) |
| Power supply (27W USB-C) | Official Pi 5 PSU — underpowered supply = instability |
| Ethernet cable | Wired connection = stable streams = fewer false alerts |
| ONVIF/RTSP cameras on your LAN | Any brand — see [docs/hardware.md](hardware.md) for tested models |

**Optional but recommended:**
- [Coral USB TPU Accelerator](hardware.md#ai-accelerator) (~$60) — 10x faster AI detection
- USB SSD — microSD cards wear out with continuous recording writes

---

## Step 1 — Flash the SD Card

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Choose **Raspberry Pi OS Lite (64-bit)** — no desktop needed
3. Click the **gear icon ⚙** before flashing and configure:
   - Hostname: `custos`
   - Enable SSH *(optional after this — wizard doesn't need it)*
   - Username: `pi`, choose a password
   - Configure WiFi if you can't run Ethernet
4. Flash to your microSD card and insert it into the Pi

---

## Step 2 — First Boot and Install

Power on the Pi. From any computer on the same network, open a terminal:

```bash
ssh pi@custos.local
```

Then run the one-command installer:

```bash
curl -fsSL https://raw.githubusercontent.com/kelaxten/custos/main/scripts/setup.sh | bash
```

This takes about 3 minutes. It:
- Installs Docker and Docker Compose
- Pulls all container images (Frigate, Home Assistant, Mosquitto, Caddy)
- Enables Pi 5 hardware video decoding
- Generates MQTT credentials
- Starts the Custos stack
- Broadcasts `custos.local` via mDNS

When it finishes you'll see:
```
✓ Custos is running. Open http://custos.local in your browser to complete setup.
```

---

## Step 3 — Run the Setup Wizard

Open **http://custos.local** in any browser on your local network.

The wizard walks you through 5 screens in about 10 minutes:

**Screen 1 — Find Cameras**
Click "Scan My Network." Custos finds all ONVIF cameras on your network and shows
live thumbnails. Cameras requiring credentials show a lock icon — enter your camera's
username and password (usually `admin` / your password from the camera sticker).

**Screen 2 — Name Your Cameras**
Type friendly names: "Front Door", "Driveway", "Backyard". These become your
camera names everywhere in the system.

**Screen 3 — Detection**
Toggle what each camera should watch for: People, Vehicles, Animals.
Sensible defaults are pre-checked — you can change them later.

**Screen 4 — Notifications**
Choose how you want alerts:
- **HA Companion App** (recommended) — rich push notifications with snapshots on your phone
- **ntfy** — open source push notification service
- **Skip** — check the dashboard manually

**Screen 5 — Remote Access**
Optional: follow the Tailscale instructions to check your cameras from anywhere
without port forwarding.

The wizard writes all config files and restarts Frigate. **Done.**

---

## Step 4 — Set Up Phone Notifications (HA Companion)

If you chose HA Companion in Screen 4:

1. Install **[Home Assistant Companion](https://companion.home-assistant.io/)** on your phone (iOS or Android)
2. Open the app → tap "Log in"
3. Your phone auto-discovers `custos.local` — tap it
4. Sign in with the HA account you created during wizard setup

Person and vehicle detections now send push notifications to your phone with a snapshot image.

For multiple phones: repeat on each phone. Notifications automatically go to every enrolled device.

---

## Daily Use

Open **http://custos.local** or the HA Companion app.

- **Cameras tab** — live feeds from all cameras, tap to fullscreen
- **Activity tab** — timeline of AI detections, tap any card to play the 10-second clip
- **System tab** — detection FPS, recording status, per-camera controls

Advanced access:
- Frigate NVR: `http://custos.local/frigate`
- Home Assistant: `http://custos.local:8123`

---

## Optional: Coral USB TPU (Faster Detection)

The Coral USB Accelerator offloads AI inference from the CPU, giving 10x faster
detection with lower CPU usage and heat.

1. Plug the Coral USB TPU into the Pi's **USB 3.0 port** (blue port)
2. Edit `config/frigate/config.yml` and update the `detectors:` section:

```yaml
detectors:
  coral:
    type: edgetpu
    device: usb
```

3. In `docker-compose.yml`, uncomment the USB device line:

```yaml
      # - /dev/bus/usb:/dev/bus/usb
```

4. Restart: `docker compose down && docker compose up -d`

Detection speed goes from ~200ms to ~15ms per frame.

---

## Optional: External USB Storage

microSD cards wear out with continuous video writes. For long-term reliability,
use a USB SSD:

1. Mount the drive:
   ```bash
   sudo mkdir -p /mnt/custos
   sudo mount /dev/sda1 /mnt/custos
   ```
2. Add to `/etc/fstab` for auto-mount on boot:
   ```
   /dev/sda1  /mnt/custos  ext4  defaults  0  2
   ```
3. Update `.env`:
   ```
   CUSTOS_STORAGE_PATH=/mnt/custos
   ```
4. Restart: `docker compose down && docker compose up -d`

---

## Optional: Remote Access via Tailscale

The setup wizard's Screen 5 guides you through this, but if you skipped it:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Install the Tailscale app on your phone, sign in to the same account, and you can
reach `custos.local` from anywhere with no port forwarding or dynamic DNS.

---

## Troubleshooting

**`custos.local` doesn't load:**
- Wait 60 seconds after setup — mDNS takes a moment to broadcast
- Use the Pi's IP directly: `http://192.168.1.x`
- Check mDNS: `systemctl status avahi-daemon`

**Camera not found by the wizard scan:**
- Confirm ONVIF is enabled in your camera's settings (usually under Network → Advanced)
- Make sure camera is on the same network subnet as the Pi
- See [docs/reolink-cameras.md](reolink-cameras.md) for Reolink-specific settings

**No video / black screen:**
- Check camera credentials — wrong password is the #1 cause
- Verify RTSP stream works: `vlc rtsp://admin:password@192.168.1.x:554/h264Preview_01_sub`
- Check Frigate logs: `docker compose logs frigate`

**High CPU usage:**
- Confirm hardware decode is active: `docker compose logs frigate | grep hwaccel`
- Add a Coral USB TPU (biggest single upgrade you can make)
- Reduce detection FPS in Frigate config from 5 to 3

**Notifications not arriving:**
- Confirm Mosquitto is running: `docker compose logs mosquitto`
- Check HA automations: Home Assistant → Settings → Automations
- In HA Companion app: Settings → Notifications → make sure they're enabled
- Check phone notification settings for the HA Companion app

**Re-run the wizard:**
- Visit `http://custos.local/setup` at any time to reconfigure cameras or change settings

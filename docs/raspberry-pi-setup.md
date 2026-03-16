# Custos on Raspberry Pi 5 — Setup Guide

This guide takes you from a fresh Pi 5 to a working home security system with
push notifications on your phone. Target time: under an hour.

---

## What You'll Need

| Item | Notes |
|------|-------|
| Raspberry Pi 5 (4GB or 8GB) | 8GB recommended if you have 4+ cameras |
| microSD card ≥ 64GB (A2-rated) | Or a fast USB SSD for better performance |
| Power supply (27W USB-C) | The official Pi 5 PSU — underpowered supply = instability |
| Ethernet cable | Run wired if at all possible — stable stream = fewer false alerts |
| Your Reolink cameras on your LAN | See [reolink-cameras.md](reolink-cameras.md) for connection details |

**Optional but recommended:**
- Coral USB TPU Accelerator (~$60) — 10x faster AI detection, much lower CPU/heat
- USB SSD or USB hard drive for storage — microSD cards wear out with continuous writes

---

## Step 1 — Flash Raspberry Pi OS

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Choose **Raspberry Pi OS Lite (64-bit)** — no desktop needed
3. Click the gear icon ⚙ before flashing and configure:
   - Set hostname: `custos`
   - Enable SSH
   - Set username/password
   - Configure WiFi if needed (wired is better)
4. Flash to your microSD card

---

## Step 2 — First Boot

SSH into the Pi:
```bash
ssh pi@custos.local
# or: ssh pi@<pi-ip-address>
```

Update the system:
```bash
sudo apt-get update && sudo apt-get upgrade -y
```

---

## Step 3 — Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
sudo apt-get install -y docker-compose-plugin
```

Verify:
```bash
docker --version
docker compose version
```

---

## Step 4 — Clone and Configure Custos

```bash
cd ~
git clone https://github.com/kelaxten/custos.git
cd custos
```

Run the setup script (one-time):
```bash
bash scripts/setup.sh
```

This will:
- Create storage directories at `/opt/custos/storage`
- Enable the Pi 5 V4L2 hardware video decoder
- Set up `custos.local` mDNS broadcasting
- Pull all Docker images

---

## Step 5 — Configure Your Cameras

Open the Frigate config:
```bash
nano config/frigate/config.yml
```

For each camera, update:
1. The IP address (replace `192.168.1.101`, `192.168.1.102`, etc.)
2. Verify your camera's sub-stream resolution in the `detect` section

Then set your camera password:
```bash
nano .env
# Set FRIGATE_RTSP_PASSWORD=your_password_here
```

See [reolink-cameras.md](reolink-cameras.md) for exact RTSP URLs for your Reolink model.

---

## Step 6 — Set Your Timezone

Edit `config/homeassistant/configuration.yaml` and update the timezone:
```yaml
homeassistant:
  time_zone: America/New_York   # Change this to your timezone
```

Full timezone list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

---

## Step 7 — Start Custos

```bash
docker compose up -d
```

Watch the logs to confirm everything starts:
```bash
docker compose logs -f
```

You should see:
- Mosquitto: `Opening ipv4 listen socket on port 1883`
- Frigate: cameras connecting and detection starting
- Home Assistant: `Starting Home Assistant`

---

## Step 8 — Open the Dashboard

Open a browser and go to: **http://custos.local**

You'll see the Home Assistant onboarding wizard. Create your HA account (this is local
— no Nabu Casa account required).

---

## Step 9 — Set Up Phone Notifications

1. Install the **Home Assistant Companion** app on your phone (iOS or Android)
2. Open the app and tap "Log in"
3. Your phone should auto-discover `custos.local` — tap it
4. Sign in with the account you created in Step 8

That's it. Person and vehicle detections from your Reolink cameras will now trigger
push notifications on your phone with a snapshot image.

**Both phones (you and your spouse):** Repeat Step 9 on each phone. The automations
in `config/homeassistant/automations.yaml` use `notify.mobile_app_all_devices`, which
automatically sends to every enrolled device.

---

## Step 10 — View Camera Footage

- **Live cameras:** `http://custos.local` → Home Assistant dashboard
- **Frigate NVR (recordings + events):** `http://custos.local/frigate`

In the Frigate UI you'll find the event timeline, recorded clips, and detection history.

---

## Optional: Coral USB TPU (Faster Detection)

The Coral USB Accelerator dramatically improves detection speed and reduces CPU load.

1. Plug the Coral USB TPU into the Pi's USB 3.0 port (blue port)
2. Edit `config/frigate/config.yml` and replace the `detectors` section:

```yaml
detectors:
  coral:
    type: edgetpu
    device: usb
```

3. In `docker-compose.yml`, uncomment:
```yaml
      # - /dev/bus/usb:/dev/bus/usb
```

4. Restart: `docker compose down && docker compose up -d`

---

## Optional: External Storage

For reliable long-term storage, use a USB SSD instead of the microSD card:

1. Mount the drive: `sudo mount /dev/sda1 /mnt/custos-storage`
2. Add to `/etc/fstab` for auto-mount on boot
3. Update `.env`: `CUSTOS_STORAGE_PATH=/mnt/custos-storage`
4. Restart: `docker compose down && docker compose up -d`

---

## Optional: Remote Access via Tailscale

To check your cameras when away from home — no port forwarding needed:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Install the Tailscale app on your phone and sign in to the same account.
Your Pi will get a stable Tailscale IP you can reach from anywhere.

---

## Troubleshooting

**custos.local doesn't resolve:**
- Give it 30 seconds after boot for mDNS to broadcast
- Use the Pi's IP address directly: `http://192.168.1.x:8123`
- Confirm avahi is running: `systemctl status avahi-daemon`

**No video from cameras:**
- Verify the RTSP URL works: `vlc rtsp://admin:password@192.168.1.x:554/h264Preview_01_sub`
- Check Frigate logs: `docker compose logs frigate`
- See [reolink-cameras.md](reolink-cameras.md) for model-specific troubleshooting

**High CPU on Pi:**
- Confirm hardware decode is working: `docker compose logs frigate | grep hwaccel`
- Lower `fps` in Frigate config from 5 to 3
- Add a Coral USB TPU for AI detection offload

**Notifications not arriving:**
- Confirm MQTT is running: `docker compose logs mosquitto`
- Check HA automations: Home Assistant → Settings → Automations
- Verify the Companion app is logged in and notifications are enabled in phone settings

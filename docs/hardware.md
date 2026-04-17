# Custos Hardware Guide

Everything you need to run Custos. One recommended build that we test against,
plus alternatives at different price points.

**Target system cost: under $300 for hub + 2 cameras.**
That's roughly the cost of one year of a typical cloud camera subscription —
and Custos runs for a decade with no ongoing fees.

---

## The Hub (Raspberry Pi 5)

The brains of Custos. Runs all AI detection, recording, and automation locally.

### Recommended: Raspberry Pi 5 (8GB)

| What | Where to Buy | Cost |
|------|-------------|------|
| Raspberry Pi 5 8GB | [raspberrypi.com](https://www.raspberrypi.com/products/raspberry-pi-5/) · Amazon · Adafruit · PiShop | $80 |
| Official Pi 5 27W USB-C PSU | Bundled with Pi or sold separately | $12 |
| microSD card (64GB A2-rated) | Samsung Pro Endurance, SanDisk Max Endurance | $12–15 |

> **Get the 8GB** if you plan to run 3+ cameras. The 4GB works fine for 1–2 cameras.

### Better Storage: USB SSD (Recommended for Long-Term Use)

microSD cards wear out with continuous video writes. For 24/7 recording, use a USB SSD:

| What | Example Model | Cost |
|------|--------------|------|
| USB SSD (250GB+) | Samsung T7 · Crucial X6 · WD My Passport SSD | $35–50 |

Plug into the blue USB 3.0 port. Custos will store recordings there automatically
when you set `CUSTOS_STORAGE_PATH` in `.env`.

### Case (Optional)

Any Pi 5-compatible case works. Look for one with active cooling (fan) if you're
running 3+ cameras — the Pi 5 runs warm under sustained AI workloads.

---

## AI Accelerator (Strong Recommendation)

Without an accelerator, detection runs on the Pi's CPU: ~150–200ms per frame,
high CPU usage, warm temperatures. With a Coral USB TPU: ~15ms per frame, low CPU.

### Coral USB TPU

| What | Where to Buy | Cost |
|------|-------------|------|
| Google Coral USB Accelerator | [coral.ai](https://coral.ai/products/accelerator/) · Amazon · Mouser | $35–60 |

Plug into the Pi's USB 3.0 port (blue). See [raspberry-pi-setup.md](raspberry-pi-setup.md#optional-coral-usb-tpu-faster-detection)
for the two config lines needed to enable it.

> **Why is this "strong recommendation"?** The Pi 5 can handle 1–2 cameras on
> CPU-only at 5 FPS. At 3+ cameras or if you want fast response times, detection
> starts dropping frames. The Coral makes the whole system feel instant.

---

## Cameras

Custos works with any camera that supports **ONVIF** and **RTSP**. These are
industry-standard protocols supported by hundreds of camera models.

### What to Look For

- **ONVIF support** — enables auto-discovery by the setup wizard
- **RTSP stream** — required for video ingestion
- **H.264 encoding** — avoid cameras that only output H.265 (limited Pi 5 hardware decode support)
- **PoE (Power over Ethernet)** — highly recommended over WiFi for stability

### Recommended Camera Models

These have been tested with Custos and work out of the box with auto-discovery.

#### Outdoor / Driveway — 4K PoE

| Model | Resolution | Form Factor | Cost | RTSP URL |
|-------|-----------|-------------|------|----------|
| Reolink RLC-810A | 4K (8MP) | Bullet | $55–65 | `rtsp://admin:PASS@IP:554/h264Preview_01_sub` |
| Reolink RLC-823A | 4K + spotlight | Bullet | $65–75 | Same pattern |
| Amcrest IP8M-2493EW | 4K | Bullet | $60–70 | `rtsp://admin:PASS@IP:554/cam/realmonitor?channel=1&subtype=1` |

#### Outdoor / Porch — 5MP PoE Dome

| Model | Resolution | Form Factor | Cost | RTSP URL |
|-------|-----------|-------------|------|----------|
| Reolink RLC-520A | 5MP | Dome | $40–50 | `rtsp://admin:PASS@IP:554/h264Preview_01_sub` |
| Hikvision DS-2CD2143G2-I | 4MP | Dome | $55–70 | `rtsp://admin:PASS@IP:554/Streaming/Channels/102` |

#### Front Door — Wide Angle

| Model | Resolution | Form Factor | Cost | RTSP URL |
|-------|-----------|-------------|------|----------|
| Reolink RLC-823A | 4K + spotlight | Bullet | $65–75 | `rtsp://admin:PASS@IP:554/h264Preview_01_sub` |
| Reolink E1 Outdoor PoE | 5MP | Turret | $45–55 | Same pattern |

#### Indoor / Baby Monitor — WiFi Pan/Tilt

| Model | Resolution | Form Factor | Cost | Notes |
|-------|-----------|-------------|------|-------|
| Reolink E1 Pro | 5MP | Pan/tilt | $35–45 | Enable ONVIF in camera settings |
| TP-Link Tapo C210 | 3MP | Pan/tilt | $25–35 | RTSP enabled via Tapo app settings |

> **Reolink RTSP password note:** By default Reolink cameras have no password and
> RTSP is disabled. Enable RTSP and set a password in the Reolink app before running
> the Custos setup wizard. See [reolink-cameras.md](reolink-cameras.md) for step-by-step.

### PoE Switch (Required for PoE Cameras)

PoE cameras get power through the Ethernet cable — no separate power adapter needed.
You need a PoE switch to provide that power.

| What | Example | Cost |
|------|---------|------|
| 4-port PoE switch (65W) | TP-Link TL-SG1005P | $30–35 |
| 8-port PoE switch (65W) | TP-Link TL-SG1008P | $45–55 |

Get a 4-port for 2–3 cameras, 8-port for 4–7 cameras.

---

## Complete Starter System: ~$285

| Item | Cost |
|------|------|
| Raspberry Pi 5 8GB | $80 |
| Official 27W PSU | $12 |
| microSD 64GB A2 | $13 |
| Coral USB TPU | $45 |
| TP-Link 4-port PoE switch | $32 |
| Reolink RLC-810A × 2 | $110 |
| Cat6 patch cables × 2 | $10 |
| **Total** | **~$302** |

This system: 2 outdoor 4K cameras, real-time AI detection, 7-day recordings,
push notifications. Zero monthly fees.

---

## Compatibility Notes

### Cameras That Need Manual Config

Some cameras aren't discovered automatically by ONVIF but work fine with manual IP entry in the wizard. The wizard always offers a "Add camera manually" option.

**Dahua cameras:** Use subtype=1 in the RTSP URL for sub-stream.
`rtsp://admin:PASS@IP:554/cam/realmonitor?channel=1&subtype=1`

**Hikvision cameras:** Use channel 102 for sub-stream.
`rtsp://admin:PASS@IP:554/Streaming/Channels/102`

**Generic/no-name cameras:** Try these patterns in order:
1. `rtsp://admin:PASS@IP:554/h264/ch1/sub/av_stream`
2. `rtsp://admin:PASS@IP:554/live/ch00_1`
3. `rtsp://admin:PASS@IP:554/cam/realmonitor?channel=1&subtype=1`

### Cameras Known NOT to Work

- **Ring cameras** — proprietary protocol, no RTSP
- **Nest/Google cameras** — requires Google account, no local RTSP without workarounds
- **Arlo cameras** — cloud-dependent, no local RTSP
- **Eufy cameras** — some models have local RTSP disabled by default (can be re-enabled)

### Resolution Recommendations

The setup wizard defaults detection to 640×480 at 5 FPS on the sub-stream.
This is intentional: AI detection doesn't need 4K, and lower resolution means
lower CPU load and less bandwidth. Recording always uses the full-resolution main stream.

For cameras with different sub-stream resolutions, you can adjust in Frigate's
config after initial setup.

---

## Questions?

Open an issue: https://github.com/kelaxten/custos/issues

Include your camera model, Pi hardware, and the output of:
```bash
docker compose logs frigate 2>&1 | tail -50
```

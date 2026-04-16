# Reolink Camera Configuration

Reolink cameras work well with Frigate and Custos. This guide covers the RTSP URLs,
known quirks, and settings to change in the Reolink app for reliable operation.

---

## RTSP URL Format

Most Reolink cameras use this pattern:

| Stream | URL | Use |
|--------|-----|-----|
| Main stream (1080p/4K) | `rtsp://admin:PASSWORD@IP:554/h264Preview_01_main` | Recording |
| Sub stream (640×480) | `rtsp://admin:PASSWORD@IP:554/h264Preview_01_sub` | AI detection |

`PASSWORD` comes from your `.env` file (`FRIGATE_RTSP_PASSWORD`).
`IP` is the camera's static IP on your LAN.

---

## Reolink App Settings (Do This First)

Before adding cameras to Custos, configure each camera in the Reolink app:

### 1. Enable RTSP

Reolink App → Camera → Settings → Network → Advanced → **Enable RTSP**

Some cameras have RTSP enabled by default; others require this to be turned on.

### 2. Assign a Static IP

Reolink App → Camera → Settings → Network → **IP address** → set to static

Use addresses outside your router's DHCP range (e.g., if your router hands out .100–.200,
use .10–.50 for cameras). Example: `192.168.1.101`, `192.168.1.102`, etc.

> If you don't set static IPs, the camera's IP can change after a router reboot,
> breaking Frigate until you update the config.

### 3. Set Sub-stream Resolution

Reolink App → Camera → Settings → Video → **Sub stream** → set to 640×480

Frigate uses the sub-stream for AI detection. Lower resolution = faster detection,
less CPU. 640×480 is the sweet spot.

### 4. Disable Cloud Upload (Optional but Recommended)

Reolink App → Camera → Settings → Push notifications → **disable cloud recording**

This keeps all your footage local. You don't need the Reolink cloud once Custos is
running — local recordings in Frigate are better in every way.

---

## Known Reolink Models

### RLC-810A / RLC-820A (4K PoE, most popular)

```yaml
ffmpeg:
  inputs:
    - path: rtsp://admin:{FRIGATE_RTSP_PASSWORD}@192.168.1.101:554/h264Preview_01_sub
      roles: [detect]
      input_args: preset-rtsp-restream
    - path: rtsp://admin:{FRIGATE_RTSP_PASSWORD}@192.168.1.101:554/h264Preview_01_main
      roles: [record]
      input_args: preset-rtsp-restream
detect:
  width: 640
  height: 480
  fps: 5
```

### RLC-510A / RLC-520A (5MP PoE)

Same URL format as above. Sub-stream defaults to 640×480.

### E1 Outdoor (WiFi)

```yaml
ffmpeg:
  inputs:
    - path: rtsp://admin:{FRIGATE_RTSP_PASSWORD}@192.168.1.101:554/h264Preview_01_sub
      roles: [detect]
      input_args: preset-rtsp-restream
    - path: rtsp://admin:{FRIGATE_RTSP_PASSWORD}@192.168.1.101:554/h264Preview_01_main
      roles: [record]
      input_args: preset-rtsp-restream
detect:
  width: 640
  height: 480
  fps: 5
```

Note: WiFi cameras drop streams more often than PoE. If you see frequent disconnects,
try adding `reconnect_on_signal_loss: true` or reduce fps to 3.

### Doorbell cameras (Reolink Video Doorbell PoE / WiFi)

Doorbell cameras have a different port for the sub-stream on some firmware versions.
Try port 554 first; if that fails, try port 8554.

```yaml
ffmpeg:
  inputs:
    - path: rtsp://admin:{FRIGATE_RTSP_PASSWORD}@192.168.1.101:554/h264Preview_01_sub
      roles: [detect]
      input_args: preset-rtsp-restream
    - path: rtsp://admin:{FRIGATE_RTSP_PASSWORD}@192.168.1.101:554/h264Preview_01_main
      roles: [record]
      input_args: preset-rtsp-restream
```

---

## Adding a New Camera to Custos

1. Set a static IP for the camera in the Reolink app
2. Enable RTSP
3. Add a new entry in `config/frigate/config.yml` (copy an existing camera block)
4. Update the IP address in the RTSP URLs
5. Restart Frigate: `docker compose restart frigate`
6. Check it's working: `http://custos.local/frigate` → Cameras

---

## Verifying RTSP Before Adding to Frigate

Test the stream from your laptop before adding it to Frigate:

```bash
# Using VLC (macOS/Windows/Linux)
vlc rtsp://admin:PASSWORD@192.168.1.101:554/h264Preview_01_sub

# Using ffplay (if you have ffmpeg installed)
ffplay -rtsp_transport tcp rtsp://admin:PASSWORD@192.168.1.101:554/h264Preview_01_sub
```

If the stream plays, it will work in Frigate.

---

## Troubleshooting

**Stream keeps disconnecting:**
- Use PoE cameras over WiFi cameras whenever possible
- Check the camera's network connection (cable or WiFi signal strength)
- In `config/frigate/config.yml`, add under the camera's `ffmpeg.inputs`:
  ```yaml
  input_args: -rtsp_transport tcp -timeout 5000000
  ```

**No sub-stream / wrong resolution:**
- Some older Reolink firmware doesn't expose the sub-stream via RTSP
- Update camera firmware in the Reolink app → Camera Settings → System → Firmware Update
- If sub-stream still doesn't work, use the main stream for detection (uses more CPU):
  ```yaml
  - path: rtsp://admin:{FRIGATE_RTSP_PASSWORD}@192.168.1.101:554/h264Preview_01_main
    roles: [detect, record]
  ```

**H.265 (HEVC) cameras:**
Some newer 4K Reolink cameras default to H.265. If you see decode errors in Frigate:
- Switch camera to H.264 in Reolink app → Video Settings → Encoding → **H.264**
- H.264 is more compatible and has lower latency for detection

**"Connection refused" or no stream:**
- Confirm RTSP is enabled in the Reolink app
- Verify the IP address with: `ping 192.168.1.101`
- Confirm port 554 is reachable: `nc -zv 192.168.1.101 554`

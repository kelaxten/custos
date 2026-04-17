# Alpha Launch Announcement

**For posting in:** r/selfhosted, r/homeautomation, r/homeassistant, r/privacy, r/homeimprovement

---

## Title

I built an open-source home security system that replaces Ring/Arlo with a Raspberry Pi — and the setup wizard means your parents can actually install it

---

## Post Body

**TL;DR:** Custos is a self-hosted home security platform built on Frigate + Home Assistant. It auto-discovers your ONVIF cameras, walks you through a 5-screen browser wizard, and generates all config automatically. No YAML, no terminal after initial setup. Alpha release today — looking for testers.

---

### The problem

I had Ring cameras for two years. Then:
- Subscription went from $10/month to $20/month
- They handed video to police without my consent [three separate incidents that made the news]
- My cameras died after their server-side "sunset" — hardware I paid for, bricked remotely

The alternative (Frigate + Home Assistant) is genuinely excellent but the setup is... not for my parents. Not even close. I spent a weekend getting it working and I do this for a living.

### What I built

**Custos** (Latin: guardian) is a thin UX layer on top of Frigate + Home Assistant that handles all the hard parts:

**5-screen browser setup wizard:**
1. Scans your network for cameras (ONVIF auto-discovery), shows live thumbnails
2. Name your cameras — "Front Door", "Driveway"
3. Toggle detection: People / Vehicles / Animals (sensible defaults)
4. Choose notifications: HA Companion app push notifications, or skip
5. Tailscale setup for remote access — scan a QR code, done

The wizard writes all the Frigate YAML, HA cameras config, MQTT sensors, and Lovelace dashboard for you.

**What you get after the wizard:**
- Live camera grid (HA dashboard)
- **Event timeline** — tap any detection to play the 10-second clip inline
- Push notifications to your phone with a snapshot image
- 7-day continuous recording to local storage
- Remote access via Tailscale (no port forwarding)

**What you need:**
- Raspberry Pi 5 (~$80)
- Any ONVIF/RTSP cameras — we have a [hardware guide](https://github.com/kelaxten/custos/blob/main/docs/hardware.md) with tested models around $50–70 each
- Optional but recommended: Coral USB TPU (~$45) for fast AI detection

Total cost: ~$280–320 for a 2-camera system. Runs forever. No subscription.

### The honest state of alpha

This is functional but rough:
- Tested on Pi 5 with Reolink cameras (RLC-810A, RLC-520A)
- Frigate's object detection works great; the wrapper is new
- The wizard auto-discovers cameras reliably on flat networks; VLANs/complex topologies may need manual IP entry
- No update mechanism yet (Phase 2)
- Requires basic comfort with SSH for the one-time install command

### How to try it

```bash
# Flash Raspberry Pi OS Lite (64-bit) to a Pi 5
# SSH in, then:
curl -fsSL https://raw.githubusercontent.com/kelaxten/custos/main/scripts/setup.sh | bash
# Open http://custos.local — setup wizard starts
```

Full instructions: [docs/raspberry-pi-setup.md](https://github.com/kelaxten/custos/blob/main/docs/raspberry-pi-setup.md)

### What I'm looking for from alpha testers

- Does the camera scan find your cameras? (ONVIF brand/model would help)
- Does the wizard complete without needing to touch YAML?
- Are push notifications arriving correctly?
- What breaks? What's confusing?

File issues at: https://github.com/kelaxten/custos/issues

Or comment below — I'll respond to everything.

### The commitment

This is open source under Apache 2.0 and stays free forever. No subscriptions. No cloud dependency. No data leaves your house. If the project ever sells anything, it's pre-built hardware (convenience, not capability). Full pledge in the repo's ROADMAP.md.

---

GitHub: https://github.com/kelaxten/custos

---

*If this isn't quite ready for your setup, keep an eye on the repo. Phase 2 (error recovery, zone editor, PWA mobile app) is starting now.*

---

## Companion Posts / Variants

### For r/privacy (shorter, different angle)

**Title:** I replaced Ring with a self-hosted system where it's actually impossible for police to request my camera footage (because there's no server to subpoena)

Major cloud camera vendors have handed video to law enforcement thousands of times, often without owner consent. With Custos, there's nothing to subpoena — video lives on a hard drive in your house, no cloud relay.

Open source, runs on a Raspberry Pi. Setup wizard means no YAML editing. Built on Frigate + Home Assistant.

[Same link + setup instructions]

### For r/homeimprovement (longer, practical angle)

**Title:** I ditched my $20/month Ring subscription for a one-time $300 setup that I own forever

[Cost comparison table from README, then same technical content, more emphasis on setup simplicity]

---

## Key Talking Points for Responses

**"Why not just use Frigate directly?"**
You can, and it's great. Custos is for people who don't want to write YAML. The wizard generates identical config to what you'd write manually — there's no lock-in, no extra layer, just a setup UI.

**"Does it work with [camera brand]?"**
Any ONVIF/RTSP camera. The [hardware guide](https://github.com/kelaxten/custos/blob/main/docs/hardware.md) lists tested models. For untested cameras, manual IP entry always works.

**"What about motion zones?"**
Phase 2 (coming next). For now you get full-frame detection with Frigate's built-in object tracking. Zone editors come in the visual editor sprint.

**"Doesn't Home Assistant already do all this?"**
Partially — HA + Frigate + MQTT + Lovelace setup takes a weekend. Custos does it in 15 minutes. Advanced users can still access HA directly for anything Custos doesn't expose.

**"I had X problem"**
File an issue with camera model + `docker compose logs frigate 2>&1 | tail -50`. We'll fix it.

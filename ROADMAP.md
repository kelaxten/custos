# CUSTOS

**Open Source Home Security Platform**

*Latin: custos — guardian, protector, keeper*

> So easy your mom can set it up. So good you'll never go back.

Built on Frigate · Home Assistant · Coral TPU · Tailscale

---

## The Custos Pledge

```
No subscriptions. No cloud lock-in. No ads. No data harvesting.
Every feature works offline. Every feature is free. Forever.
If we sell anything, it's only to make setup easier for people who don't want to DIY.
```

---

## Table of Contents

- [Design Principles](#design-principles)
- [What We're Replacing](#what-were-replacing)
- [The User Experience](#the-user-experience)
- [Technology Stack](#technology-stack)
- [Hardware Guide](#hardware-guide)
- [Product Roadmap](#product-roadmap)
  - [Phase 1: Make It Work (Weeks 1–6)](#phase-1-make-it-work-weeks-16)
  - [Phase 2: Make It Easy (Weeks 7–14)](#phase-2-make-it-easy-weeks-714)
  - [Phase 3: Make It Best-in-Class (Weeks 15–30)](#phase-3-make-it-best-in-class-weeks-1530)
  - [Phase 4: Make It Accessible to Everyone (Weeks 31–52)](#phase-4-make-it-accessible-to-everyone-weeks-3152)
- [What We Will Never Do](#what-we-will-never-do)
- [Revenue & Sustainability](#how-this-gets-funded-without-selling-out)
- [Community & Growth](#community--growth-plan)
- [Risks & Mitigations](#risks--mitigations)
- [Success Metrics](#success-metrics)
- [Immediate Next Steps](#immediate-next-steps-this-week)

---

## Design Principles

Every decision in this project is filtered through five non-negotiable principles. If a feature or business decision conflicts with any of these, it doesn't ship.

### The Mom Test

The north star for every UX decision: could a 65-year-old non-technical parent set this up with nothing but a web browser and the instructions on screen? If the answer is no, the feature isn't done yet.

- No terminal. No SSH. No YAML editing. Not even for initial setup.
- Every screen has exactly one clear next step. No branching decisions that require expertise.
- Error messages say what went wrong AND what to do about it, in plain English.
- The setup wizard assumes the user has never heard of RTSP, ONVIF, MQTT, or Docker. These words never appear in the UI.
- If something can be auto-detected or auto-configured, it must be. The user should only make choices that actually require human judgment ("which camera points at your driveway?").

### The Anti-Enshittification Pledge

This isn't a VC-funded startup that will degrade the free product to push subscriptions. This is a community project with a specific philosophy:

- **Zero subscription fees, ever.** There is no "free tier" and "premium tier." There is one product and it is free.
- **No cloud dependency.** Everything works on your local network with no internet connection. Period.
- **No data leaves your house.** We don't run servers that touch your video. We don't have analytics. We don't know you exist unless you tell us.
- **No feature gating.** Face recognition, license plate reading, package detection, automations — all free, all local, all included.
- **If we sell anything, it's convenience, not capability.** A pre-built box for people who don't want to buy parts. That's it. The software is identical.

### Cost Target

A complete Custos system (hub + 2 cameras) should cost less than 2 years of a typical cloud camera subscription. Target: under $300 all-in for a 2-camera setup that runs for a decade with zero ongoing cost.

### Speed to Value

The user should see their first live camera feed within 10 minutes of powering on the hardware. They should get their first useful "person detected" notification within 30 minutes. If it takes longer than that, we've failed.

### Radical Simplicity

Every feature we add makes the product harder to maintain and harder to learn. We ship the minimum surface area that solves the problem. Advanced users can always add complexity through Home Assistant — but Custos's own UI stays simple.

---

## What We're Replacing

### The Problem With Cloud Camera Systems

The dominant cloud-based home security platforms follow a predictable pattern: lure you in with cheap hardware, then extract value through mandatory subscriptions, privacy violations, and planned obsolescence.

- **Cost:** Typical cloud camera subscriptions run $100–200/year. A video doorbell + 2 cameras + subscription = $700 in the first year, $200/year after that. Over 5 years: $1,500.
- **Privacy:** Major cloud camera vendors have handed video to law enforcement without owner consent thousands of times. Employees at these companies have been caught viewing customer feeds. Your private moments live on someone else's servers.
- **Reliability:** Internet goes down? Your cameras are useless. The vendor's servers go down? Your cameras are useless. They decide to sunset your hardware model? Your cameras are useless.
- **AI Quality:** Cloud-based person detection still struggles to distinguish people from shadows. Processing in the cloud adds multi-second delay. You get 50 "motion detected" alerts a day and stop checking them.
- **Vendor Lock-in:** Proprietary cameras only work with the vendor's ecosystem. You can't use them with any other system. You're renting your security from a tech conglomerate.

### The Custos Alternative

| | Cloud Cameras (5-Year Cost) | Custos (5-Year Cost) |
|---|---|---|
| **Hardware** | $300 (doorbell + 2 cams) | $180–250 (mini PC + 2 PoE cams) |
| **Subscription** | $1,000 (5 yr × $200) | **$0** |
| **AI Accelerator** | Included (cloud) | $35–60 (USB TPU accelerator) |
| **Storage** | Included (cloud, 60 days) | $0–50 (microSD or USB drive) |
| **5-Year Total** | **$1,300–1,500** | **$215–360 (one time)** |
| **Works Offline** | No | Yes |
| **Law Enforcement Access** | Without your consent | Impossible — data never leaves your network |
| **AI Detection** | Cloud, 2–5 sec delay, high false positive | Local, <100ms, dedicated TPU, tunable zones |

---

## The User Experience

### Setup to First Alert

This is the exact experience we're designing for. Every engineering decision serves this flow.

#### The Box Arrives (Pre-Built Hub Option)

For users who buy the pre-built Custos Hub, the experience starts like any consumer electronics device:

1. Unbox the Custos Hub (mini PC with TPU accelerator pre-installed, Custos OS pre-loaded).
2. Plug it into power and your router with the included Ethernet cable.
3. Open any web browser on your phone or laptop. Navigate to `custos.local` (auto-discovered via mDNS, like a printer).
4. The setup wizard appears.

#### The Setup Wizard (10 Minutes)

The wizard is 5 screens. Not 5 pages of settings — 5 total screens.

**Screen 1 — Welcome:** "Let's find your cameras." One button: "Scan My Network." The system runs ONVIF/RTSP discovery and shows every camera it finds as a live thumbnail. Cameras that need passwords show a lock icon with a field to enter the camera's credentials (with a link to "Where do I find this?" showing photos of common camera sticker locations).

**Screen 2 — Name Your Cameras:** Each discovered camera shows its live feed. You type a name: "Front Door," "Driveway," "Backyard." That's it. One text field per camera.

**Screen 3 — What Should I Watch For?** Simple toggles per camera: People, Vehicles, Animals, Packages. Pre-checked with sensible defaults (People and Vehicles for outdoor cameras, People for indoor). Advanced users can draw custom zones later, but the defaults work out of the box.

**Screen 4 — Notifications:** "How should we tell you?" Three options presented as big cards:
- **(a) Custos Web App** — notifications in your browser, works right now
- **(b) Mobile Companion App** — install the free Home Assistant Companion app for rich push notifications with snapshots
- **(c) Email or Messaging Apps** — enter your details, done

Each option has a QR code or one-click setup link.

**Screen 5 — Remote Access:** "Want to check your cameras when you're away from home?" If yes, scan a QR code with the Tailscale app. 60-second setup, zero port forwarding, zero networking knowledge required. If no, skip — everything else works locally.

**Done.** The dashboard appears with live feeds from all cameras. The system is recording. AI detection is running. The user gets their first real notification within minutes.

#### Daily Use

The daily experience is a simple dashboard:

- Live camera grid (tap to fullscreen, pinch to zoom)
- Timeline of recent events with AI-labeled thumbnails ("Person detected — Front Door — 2:34 PM")
- Tap any event to see the 10-second clip with the detected object highlighted
- Quick toggles: Home mode (reduced alerts), Away mode (full alerts), Sleep mode (outdoor only)

That's the entire daily interface. No settings menus, no configuration panels, no dashboards full of graphs. Just cameras and events.

---

## Technology Stack

Custos is a thin integration and UX layer on top of battle-tested open source projects. We don't re-invent anything. We assemble, configure, and put a consumer-grade face on it.

| Layer | Technology | What It Does (and Why) |
|---|---|---|
| NVR + AI Brain | **Frigate** | Records video, runs AI detection, manages events. The core engine. Mature, fast, reliable. |
| AI Accelerator | **Coral TPU** | Dedicated ML chip. Person/vehicle/animal detection in <100ms. USB plug-and-play. |
| Automation Hub | **Home Assistant (headless)** | Runs behind the scenes for notification routing, automations, and phone app. Users never see HA directly unless they want to. |
| Message Bus | **Mosquitto (MQTT)** | Event pipeline between Frigate and HA. Internal plumbing, invisible to users. |
| Remote Access | **Tailscale** | Zero-config VPN. QR code enrollment from phone. No port forwarding, no dynamic DNS, no networking knowledge. |
| Web Server | **Caddy** | Automatic HTTPS, reverse proxy. Routes custos.local to the right services. |
| Custos UI | **SvelteKit or React** | Our custom dashboard layer. The setup wizard, event timeline, camera grid, and settings. This is what makes it feel like a product, not a project. |
| Containers | **Docker Compose** | Each service in its own container. Clean updates, easy rollback, isolation. |
| Base OS | **Debian 12 Minimal** | Rock solid. Long-term support. Boots fast. Runs on anything with an x86 CPU. |
| Notifications | **HA Companion + ntfy** | Rich push notifications with event thumbnails. Falls back to browser notifications or email. |
| Camera Protocol | **ONVIF + RTSP** | Industry standards. Works with hundreds of camera models from dozens of manufacturers. |

### The Custos Layer

What Custos actually builds (vs. what we assemble from existing projects):

- **Setup Wizard:** The 5-screen browser-based wizard that auto-discovers cameras, configures Frigate, sets up HA automations, and enrolls Tailscale. This is the product.
- **Custos Dashboard:** A custom web UI that replaces the need to interact with Frigate's UI or HA's UI for daily use. Designed for non-technical users.
- **Config Generator:** Takes wizard inputs and generates all the YAML/JSON config files for Frigate, HA, Mosquitto, and Caddy. Users never touch config files.
- **Update Manager:** One-click container updates with automatic rollback. Health checks post-update.
- **Camera Database:** Community-maintained database of camera models with known-good RTSP URLs, capabilities, and setup quirks.
- **OS Image Builder:** Packer pipeline that produces a flashable OS image with everything pre-installed and pre-configured.

---

## Hardware Guide

We maintain one official recommended build and test against it rigorously. This is the build we tell your mom to buy. See the **[Hardware Compatibility List](docs/hardware.md)** for specific tested models and purchase links (maintained separately to keep this doc vendor-neutral).

### The Recommended Build (~$180–250 Without Cameras)

| Component | Spec | Cost |
|---|---|---|
| Mini PC | x86 N100-class, 16GB RAM, 500GB SSD | $130–160 |
| AI Accelerator | USB TPU accelerator (Coral-compatible) | $35–60 |
| Ethernet Cable | Cat6, 3ft (included with most mini PCs) | $0–5 |
| **Total (Hub Only)** | *Everything you need to run Custos* | **$165–225** |

### Recommended Camera Specs

We recommend PoE (Power over Ethernet) cameras because they're more reliable than WiFi cameras, use a single cable for power and data, and last for years. Slightly harder to install but dramatically more reliable.

| Type | Best For | Cost Range | What to Look For |
|---|---|---|---|
| 4K PoE bullet | Outdoor / Driveway | $50–60 | 4K resolution, ONVIF support, good Frigate compatibility |
| 5MP PoE dome | Outdoor / Porch | $35–45 | 5MP, dome or bullet form factor, good value |
| 5MP PoE turret | Front Door | $40–55 | Wide angle, good night vision, ONVIF support |
| WiFi pan/tilt | Indoor / Baby Monitor | $40–50 | Pan/tilt, 2-way audio, RTSP stream accessible |
| 4-port PoE switch | Powering cameras | $30–40 | 4 PoE ports, 65W+ budget, unmanaged is fine |

> 📋 Specific model recommendations with purchase links are maintained in **[docs/hardware.md](docs/hardware.md)** to keep this roadmap vendor-neutral.

### Complete Starter System: $280–400

Mini PC ($150) + TPU ($45) + PoE switch ($35) + 2 outdoor cameras ($100) = a complete home security system for roughly the price of one year of a typical cloud camera subscription, and it runs forever with no fees.

### The Pre-Built Option (Phase 4)

For people who don't want to buy parts separately, we'll sell a pre-built Custos Hub: a mini PC with TPU pre-installed, Custos OS pre-loaded, a nice case, and a quick-start card. Target price: $199–249. Margin funds project development. The software is identical to the free DIY version.

---

## Product Roadmap

Twelve months to a product that makes cloud camera subscriptions obsolete. We move fast, ship early, and iterate based on real user feedback. Every phase has a single clear goal.

---

### Phase 1: Make It Work (Weeks 1–6)

> **Goal:** A technical user can flash the OS, run the setup wizard, and have working detection in under an hour. Ship the alpha to self-hosting communities and get 50 real users.

#### Core Infrastructure

| Week | Deliverable | Priority |
|---|---|---|
| 1 | Monorepo with Docker Compose: Frigate + HA + Mosquitto + Caddy | P0 |
| 1–2 | Debian 12 OS image builder (Packer) with all containers pre-pulled | P0 |
| 2 | Automatic TPU detection (USB and M.2) with driver setup on first boot | P0 |
| 2–3 | ONVIF/RTSP camera auto-discovery service with live thumbnail preview | P0 |

#### Setup Wizard v1 (Browser-Based)

| Week | Deliverable | Priority |
|---|---|---|
| 3–4 | 5-screen setup wizard: camera discovery → naming → detection type → notifications → remote access | P0 |
| 3–4 | Config generator: wizard outputs → Frigate YAML + HA automations + Mosquitto config | P0 |
| 4–5 | mDNS broadcast so `custos.local` works immediately on the local network | P1 |

#### Minimum Viable Dashboard

| Week | Deliverable | Priority |
|---|---|---|
| 4–5 | Live camera grid view with responsive layout (phone + desktop) | P0 |
| 5–6 | Event timeline: chronological list of AI detections with thumbnails and 10s clips | P0 |
| 5–6 | Basic notifications via HA Companion app and browser push | P0 |

#### Launch

| Week | Deliverable | Priority |
|---|---|---|
| 6 | Alpha release announcement in self-hosting and home automation communities | P0 |
| 6 | Hardware buying guide + step-by-step flash instructions with photos | P0 |

> ✅ **Exit Criteria:** 50 alpha users with working setups. Median setup time under 60 minutes. Core feedback collected.

---

### Phase 2: Make It Easy (Weeks 7–14)

> **Goal:** A non-technical user can set up Custos without help. This is the phase that makes or breaks the project. We obsess over every friction point the alpha testers hit.

#### Eliminate Every Friction Point From Alpha

| Week | Deliverable | Priority |
|---|---|---|
| 7–8 | Camera compatibility database: searchable list of tested cameras with known-good RTSP URLs and setup notes | P0 |
| 7–8 | Error recovery: if camera discovery fails, offer manual IP entry with visual guide. If TPU not found, fall back to CPU detection with performance warning. | P0 |
| 8–9 | Visual zone editor: draw detection areas on camera feed with finger/mouse. "Watch this area for people." | P0 |

#### Polish the Dashboard

| Week | Deliverable | Priority |
|---|---|---|
| 9–10 | Event detail view: full clip playback, AI bounding box overlay, object tracking path, confidence score (shown as simple label, not number) | P0 |
| 9–10 | Mode switching: Home / Away / Sleep with one tap. Configurable per-zone alert schedules. | P0 |
| 10–11 | Smart notification filtering: suppress duplicate detections within 30s, quiet hours, per-camera enable/disable | P0 |

#### Mobile Experience

| Week | Deliverable | Priority |
|---|---|---|
| 10–12 | PWA (Progressive Web App): installable on phone home screen, push notifications, live view, event review. No app store required. | P0 |
| 11–12 | Rich push notifications: event thumbnail + camera name + detection type. Tap to view clip. | P0 |

#### Self-Maintenance

| Week | Deliverable | Priority |
|---|---|---|
| 12–13 | One-click update button in dashboard: pulls new container images, runs migrations, auto-rollback on failure | P0 |
| 13–14 | System health page: storage usage, camera status, CPU/RAM, TPU status. Plain English alerts if something needs attention. | P1 |

#### Beta Launch

| Week | Deliverable | Priority |
|---|---|---|
| 14 | v0.5 Beta release. Video walkthrough: unbox → flash → setup → first alert in 20 minutes. | P0 |

> ✅ **Exit Criteria:** Non-technical testers complete setup without help. Median setup <30 min. "Mom test" passed by 3+ testers aged 55+.

---

### Phase 3: Make It Best-in-Class (Weeks 15–30)

> **Goal:** Add capabilities that cloud camera systems literally cannot offer because they require local processing. This is where people stop recommending subscription services and start recommending Custos.

#### Advanced AI (All Local, All Free)

| Week | Deliverable | Priority |
|---|---|---|
| 15–18 | Face recognition: train on family photos, distinguish "known person" from "stranger." Opt-in, local-only, data never leaves the device. | P1 |
| 16–20 | License plate recognition: log known vehicles, alert on unknown plates in driveway. Uses existing Frigate LPR models. | P1 |
| 18–22 | Package detection: identify delivery events, track package presence on porch. "Your package arrived at 2:14 PM." | P1 |
| 20–24 | Behavioral detection: loitering alerts (person in driveway >60s), unusual hours activity, vehicle casing patterns | P2 |

#### Smart Automations (Simple UI, Powered by HA)

| Week | Deliverable | Priority |
|---|---|---|
| 18–22 | Automation templates with one-tap setup: "Alert on strangers after 10pm," "Record-only when I'm home," "Flash porch light when person detected" | P1 |
| 20–24 | Geofencing via HA Companion: auto arm/disarm based on who's home. No manual mode switching needed. | P1 |
| 22–26 | Smart device integration: smart locks, lights, and sirens via HA. "Lock all doors when stranger detected after midnight." | P2 |

#### Quality of Life

| Week | Deliverable | Priority |
|---|---|---|
| 22–26 | Event search and filtering: by camera, detection type, date range, time of day. Fast local search. | P1 |
| 24–28 | Clip sharing: generate a shareable link for a specific event clip (peer-to-peer via Tailscale or local download) | P2 |
| 26–30 | Daily digest: morning summary of overnight activity. "3 events overnight. 1 unknown person at 2:14 AM (Front Door). 2 vehicles." | P2 |

#### v1.0 Stable Release

| Week | Deliverable | Priority |
|---|---|---|
| 30 | v1.0 release. Exceeds cloud camera parity + face recognition + LPR + package detection + automations. All free. | P0 |

> ✅ **Exit Criteria:** Custos does everything cloud camera systems do, plus things they can't. 2,000+ active installations. <5% false positive rate.

---

### Phase 4: Make It Accessible to Everyone (Weeks 31–52)

> **Goal:** Remove the last barrier: hardware assembly. Ship a pre-built box and camera kits so anyone can have Custos without buying parts. Revenue from hardware funds ongoing development. Software stays 100% free.

#### Custos Hub (Pre-Built Hardware)

| Week | Deliverable | Priority |
|---|---|---|
| 31–36 | Partner with OEM or assemble in-house: N100 mini PC + USB TPU + custom case + Custos OS pre-loaded | P1 |
| 34–38 | Camera starter kits: Hub + 2 PoE cameras + PoE switch + cables + printed quick-start guide. Target: $349–449 all-in. | P1 |
| 36–40 | Online store. Direct-to-consumer only. | P1 |

#### Community Ecosystem

| Week | Deliverable | Priority |
|---|---|---|
| 35–42 | Community camera database: wiki-style, user-submitted camera profiles with verified compatibility badges | P1 |
| 38–45 | Automation template gallery: community-shared automation recipes, one-click import | P2 |
| 40–48 | Local installer directory: vetted local IT professionals who can install Custos for homeowners who want help. Free listing, no fees. | P2 |

#### Hardening & Scale

| Week | Deliverable | Priority |
|---|---|---|
| 40–46 | Security audit: community-driven + professional pen test of exposed services. Bug bounty program. | P0 |
| 42–48 | Multi-location support: manage cameras at home + cabin + shop from one dashboard (via Tailscale mesh) | P2 |
| 48–52 | ARM support: single-board computers + TPU as a budget option ($80–100 hub). For markets where every dollar matters. | P2 |

> ✅ **Exit Criteria:** Anyone can order a Custos Hub online, plug it in, and be running in 15 minutes. 10,000+ installations. Self-sustaining funding.

---

## What We Will Never Do

This section is as important as the roadmap. These are permanent, irrevocable commitments. If the project ever violates these, fork it.

| We Will Never... | Why |
|---|---|
| **Charge a subscription fee for any feature** | Subscriptions are the mechanism of enshittification. The moment you gate a feature behind a monthly fee, you're incentivized to move more features behind it. |
| **Require an internet connection to function** | Your security system must work when your internet is down. That's when you need it most. |
| **Send video or metadata to any server** | Your cameras, your data, your network. We have no servers, no analytics, no telemetry. We literally cannot see your data. |
| **Create a "free" and "premium" tier** | There is one product. It is complete. If you build it yourself, you get 100% of the features. If you buy our hardware, you get 100% of the features. Same software. |
| **Accept VC funding** | VC money comes with growth obligations that inevitably lead to enshittification. We're funded by hardware margins and community donations. |
| **Add vendor lock-in** | Custos works with any ONVIF/RTSP camera. We will never make proprietary cameras or require specific hardware beyond a basic x86 PC. |
| **Make "smart" features cloud-dependent** | Face recognition, LPR, package detection — everything runs on local hardware. If it can't run locally, we don't ship it. |
| **Cooperate with law enforcement data requests** | We can't. We don't have your data. There's nothing to subpoena. This is a feature, not a bug. |

---

## How This Gets Funded (Without Selling Out)

Open source projects die when they run out of funding or maintainer energy. We plan for sustainability from day one, but only through revenue streams that align with the mission.

### Revenue Streams (All Optional, None Required)

| What | Price | Launch | Who It's For |
|---|---|---|---|
| Custos Hub (pre-built) | $199–249 | Month 9 | People who don't want to buy parts separately |
| Starter Kit (hub + cameras) | $349–449 | Month 10 | People who want a complete plug-and-play system |
| Community Sponsorships | Voluntary | Month 1 | Community members who want to fund development |
| Merch (stickers, shirts) | $5–30 | Month 6 | Community pride, minor revenue |

### What We're NOT Doing

- No cloud relay service. Tailscale's free tier is more than enough for personal use. We're not building infrastructure we'd have to charge for.
- No "premium" features. Everything is free. We don't need to create artificial scarcity.
- No affiliate links in camera recommendations. We recommend the best cameras, not the ones that pay us.
- No data monetization. Obviously. But worth stating explicitly.
- No installer certification fees. If local IT pros want to install Custos for people, great. We'll list them for free.

### Sustainability Math

Conservative estimate: if 5% of installations come from pre-built hardware sales at $50 margin per unit, 10,000 installations = 500 hardware sales = $25,000/year. Combined with community sponsorships, that's enough to fund 1–2 part-time maintainers. The project doesn't need to be a business. It needs to be sustainable.

---

## Community & Growth Plan

### Launch Strategy

We don't need a marketing budget. We need a great product and the right communities.

- **Week 1–2:** Soft announce in self-hosting and Frigate communities. Recruit 10–20 alpha testers who are willing to file detailed bug reports. Personal outreach to active community members in the home automation space.
- **Week 6 (Alpha):** Public posts in self-hosting, home automation, home security, privacy, and de-cloud communities. Title: "I built an open source cloud camera replacement that my mom can set up." Include a 3-minute demo video.
- **Week 10–14 (Beta):** Reach out to self-hosting content creators. Offer to ship them a pre-built hub for review. Their audience IS our audience.
- **Week 14 (v0.5):** Tech community launch posts. "Custos — Open source home security that's easier than a cloud subscription." Time it for a weekday morning.
- **Week 30 (v1.0):** Broader launch. Press outreach to tech publications. Angle: privacy + cost savings + the anti-subscription.
- **Ongoing:** Community forum. Weekly community calls. Transparent roadmap. Every contributor gets recognition.

### Content Strategy

- "Ditch the subscription" video series: side-by-side comparisons of cloud cameras vs. Custos for specific scenarios
- "Custos Setup Speedrun" videos: how fast can you go from unboxing to first detection?
- Written guides: "The Complete Guide to Home Security Without Subscriptions"
- Privacy-focused content: "What Your Cloud Camera Provider Knows About You (And How to Take It Back)"
- Community spotlights: showcase interesting Custos setups from real users

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| TPU accelerator hardware discontinued | 🔴 High | Abstract the AI accelerator layer now. Support multiple TPU/GPU backends as alternatives. Dedicated TPU is recommended, not required. CPU-only mode as fallback. |
| Setup still too hard for non-technical users | 🔴 High | The pre-built Hub is the ultimate backstop. Also: obsessive usability testing in Phase 2. Recruit actual parents as testers. If they struggle, we fix it. |
| Upstream NVR project changes license or direction | 🟡 Medium | Custos's value is the UX layer, not the NVR. We can swap NVR backends if needed. Maintain good upstream relationship and contribute back. |
| Camera compatibility hell | 🟡 Medium | Maintain a short "blessed" camera list (3–5 models) that we guarantee work. Community database for everything else. Auto-detection handles 80% of cameras. |
| Security vulnerabilities | 🔴 High | Zero exposed ports by default. Tailscale for all remote access. No UPnP. Professional security audit before v1.0. Bug bounty program. |
| Maintainer burnout | 🔴 High | Build community ownership early. Multiple maintainers with commit access by Month 6. Hardware revenue funds part-time maintainers. Don't try to do everything. |
| Cloud camera vendors drop subscription prices | 🟢 Low | Their business model requires subscriptions. They can't compete on ongoing cost. Our advantage is structural, not temporary. |
| Legal issues with face recognition | 🟡 Medium | Face recognition is opt-in, local-only, and clearly documented. Users own and control their data. No biometric data ever leaves the device. |

---

## Success Metrics

We measure success by adoption, usability, and sustainability. Not revenue, not growth rate, not engagement metrics.

| Metric | Month 3 | Month 6 | Month 12 |
|---|---|---|---|
| Active Installations | 50 (alpha) | 500 (beta) | 5,000+ |
| Setup Success Rate (no help needed) | 60% | 80% | 95% |
| Median Setup Time | 60 min | 30 min | 15 min |
| "Mom Test" Pass Rate | N/A | 50% | 90% |
| False Alert Rate | <15% | <5% | <2% |
| Repository Stars | 500 | 3,000 | 10,000+ |
| Active Contributors | 5 | 20 | 75+ |
| Cloud-to-Custos Migration Stories | 5 | 50 | 500+ |

---

## Immediate Next Steps (This Week)

Get the foundation in place so we can start shipping in Week 1.

| # | Action | Time | Blocks |
|---|---|---|---|
| 1 | Register custos domain, repository org (custos-home or similar), community channels, and social handles. Verify no major trademark conflicts. | 2 hours | Everything |
| 2 | Set up monorepo with Docker Compose, CI/CD pipeline, Apache 2.0 license, contributing guide | 4 hours | Phase 1 dev |
| 3 | Order reference hardware: N100 mini PC, USB TPU, 2x PoE cameras, PoE switch (see [docs/hardware.md](docs/hardware.md) for specific models) | 30 min + shipping | Testing |
| 4 | Get Docker Compose stack running locally: Frigate + HA + Mosquitto. Document every step as you go. | 1 day | Phase 1 core |
| 5 | Write the ONVIF camera auto-discovery script. Test against at least 3 camera brands. | 2 days | Setup wizard |
| 6 | Sketch the 5-screen setup wizard wireframes. Test the flow with 3 non-technical people (paper prototype is fine). | 1 day | UX direction |
| 7 | Post in self-hosting and home automation communities: "Building an open source cloud camera replacement — looking for alpha testers." | 1 hour | Community |

---

> *The best home security system is one that works for everyone, costs nothing to run, and answers to nobody but you.*
>
> **Let's build it.**

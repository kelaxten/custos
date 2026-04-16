#!/usr/bin/env bash
# Custos first-time setup — Raspberry Pi 5
# Run once after cloning the repo to your Pi.
#
# What this does:
#   1. Checks prerequisites (Docker, Docker Compose, git)
#   2. Creates storage directories
#   3. Copies .env.example to .env if it doesn't exist
#   4. Enables V4L2 kernel module for Pi 5 hardware video decode
#   5. Pulls all Docker images (so first start isn't slow)
#   6. Prints next steps

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[custos]${NC} $*"; }
warn()    { echo -e "${YELLOW}[custos]${NC} $*"; }
error()   { echo -e "${RED}[custos]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

echo ""
echo "  ██████╗██╗   ██╗███████╗████████╗ ██████╗ ███████╗"
echo " ██╔════╝██║   ██║██╔════╝╚══██╔══╝██╔═══██╗██╔════╝"
echo " ██║     ██║   ██║███████╗   ██║   ██║   ██║███████╗"
echo " ██║     ██║   ██║╚════██║   ██║   ██║   ██║╚════██║"
echo " ╚██████╗╚██████╔╝███████║   ██║   ╚██████╔╝███████║"
echo "  ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝    ╚═════╝ ╚══════╝"
echo ""
echo "  Home Security · Setup Script"
echo ""

cd "$REPO_DIR"

# ─── 1. Check prerequisites ───────────────────────────────────────────────────
info "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || die "Docker not found. Install it first: curl -fsSL https://get.docker.com | sh"
command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || die "Docker Compose (v2) not found. Update Docker: sudo apt-get install docker-compose-plugin"

# Check we're on a Pi (ARM64)
ARCH="$(uname -m)"
if [[ "$ARCH" != "aarch64" ]]; then
    warn "This setup script is designed for Raspberry Pi (aarch64). Detected: $ARCH"
    warn "Continuing anyway — some hardware acceleration features may not work."
fi

info "Docker: $(docker --version)"
info "Docker Compose: $(docker compose version)"

# ─── 2. Create storage directories ────────────────────────────────────────────
# Load storage path from .env if it exists, otherwise use default
STORAGE_PATH="/opt/custos/storage"
if [[ -f "$REPO_DIR/.env" ]]; then
    STORAGE_PATH=$(grep -oP '(?<=CUSTOS_STORAGE_PATH=).*' "$REPO_DIR/.env" | head -1 || echo "/opt/custos/storage")
fi

info "Creating storage directories at $STORAGE_PATH..."
sudo mkdir -p \
    "$STORAGE_PATH/recordings" \
    "$STORAGE_PATH/mosquitto/data" \
    "$STORAGE_PATH/mosquitto/log" \
    "$STORAGE_PATH/caddy/data" \
    "$STORAGE_PATH/caddy/config"

# Recordings need to be writable by the frigate container (uid 1000)
sudo chown -R 1000:1000 "$STORAGE_PATH/recordings" 2>/dev/null || true
info "Storage directories created."

# ─── 3. Create .env if missing ────────────────────────────────────────────────
if [[ ! -f "$REPO_DIR/.env" ]]; then
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
    warn ".env file created from template."
    warn "IMPORTANT: Edit .env and set your camera password before starting:"
    warn "  nano $REPO_DIR/.env"
    echo ""
fi

# ─── 4. Pi 5 V4L2 hardware decoder ───────────────────────────────────────────
# Load the V4L2 M2M video decode kernel module for hardware-accelerated decoding.
# This significantly reduces CPU load when decoding camera streams.
info "Enabling Pi 5 V4L2 hardware video decoder..."
if lsmod | grep -q v4l2_mem2mem 2>/dev/null; then
    info "V4L2 M2M module already loaded."
else
    sudo modprobe v4l2-mem2mem 2>/dev/null || warn "Could not load v4l2-mem2mem — hardware decode may not work. Is this a Pi 5?"
fi

# Persist the module across reboots
if ! grep -q "v4l2-mem2mem" /etc/modules 2>/dev/null; then
    echo "v4l2-mem2mem" | sudo tee -a /etc/modules >/dev/null
    info "V4L2 M2M module added to /etc/modules (will load on boot)."
fi

# ─── 5. mDNS: broadcast custos.local ─────────────────────────────────────────
# Avahi broadcasts custos.local on your LAN so you can reach the dashboard
# without knowing the Pi's IP address.
if ! command -v avahi-daemon >/dev/null 2>&1; then
    info "Installing avahi-daemon for custos.local mDNS..."
    sudo apt-get update -qq && sudo apt-get install -y -qq avahi-daemon
fi

if ! systemctl is-active --quiet avahi-daemon; then
    sudo systemctl enable avahi-daemon
    sudo systemctl start avahi-daemon
fi

# Set the hostname so custos.local resolves to this Pi
if [[ "$(hostname)" != "custos" ]]; then
    warn "Setting hostname to 'custos' so custos.local works on your network."
    warn "Your Pi will be reachable at custos.local after reboot."
    sudo hostnamectl set-hostname custos
fi
info "mDNS configured. This Pi will be reachable at http://custos.local"

# ─── 6. Pull Docker images ────────────────────────────────────────────────────
info "Pulling Docker images (this may take a few minutes on first run)..."
docker compose pull

# ─── 7. Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Edit camera IPs in config/frigate/config.yml:"
echo "       nano $REPO_DIR/config/frigate/config.yml"
echo ""
echo "  2. Set your camera password in .env:"
echo "       nano $REPO_DIR/.env"
echo ""
echo "  3. Start Custos:"
echo "       cd $REPO_DIR && docker compose up -d"
echo ""
echo "  4. Open the dashboard: http://custos.local  (or http://$(hostname -I | awk '{print $1}'):8123)"
echo ""
echo "  5. Install the Home Assistant Companion app on your phones."
echo "     Sign in to HA → notifications will start arriving automatically."
echo ""
echo "  See docs/raspberry-pi-setup.md for detailed instructions."
echo ""

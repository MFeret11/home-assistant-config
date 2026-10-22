#!/usr/bin/env bash
# ==============================================================================
# Home Assistant Config & Lovelace Dashboard Sync Utility
# Synchronizes dashboards/, pyscript/, packages/, and configuration files
# directly to Home Assistant Core on the Raspberry Pi 4 host.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

HA_HOST="${HA_HOST:-100.82.195.2}"
HA_USER="${HA_USER:-pi}"
HA_CONFIG_DEST="${HA_CONFIG_DEST:-/home/pi/docker/ha_config}"
HA_CONTAINER="${HA_CONTAINER:-homeassistant}"

DRY_RUN=false
RELOAD_AFTER=true

print_usage() {
  cat <<EOF
Usage: ./scripts/sync_to_ha.sh [OPTIONS]

Options:
  --dry-run       Preview file transfers without modifying Home Assistant
  --no-reload     Skip invoking PyScript/Lovelace reload services
  --local-docker  Copy directly into local Docker container on host
  --host <ip>     Override target host (default: 100.82.195.2)
  --dest <path>   Override target config path (default: /home/pi/docker/ha_config)
  --help          Show this message

Environment Variables:
  HA_HOST         Target IP / Tailscale address (default: 100.82.195.2)
  HA_USER         Target SSH user (default: pi)
  HA_CONFIG_DEST  Config destination directory on target host
  HA_TOKEN        Long-lived access token for automatic service reload
EOF
}

LOCAL_DOCKER=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --no-reload) RELOAD_AFTER=false; shift ;;
    --local-docker) LOCAL_DOCKER=true; shift ;;
    --host) HA_HOST="$2"; shift 2 ;;
    --dest) HA_CONFIG_DEST="$2"; shift 2 ;;
    --help) print_usage; exit 0 ;;
    *) echo "Unknown option: $1"; print_usage; exit 1 ;;
  esac
done

echo "================================================================="
echo "   HOME ASSISTANT DASHBOARD & AUTOMATION DEPLOYMENT"
echo "================================================================="
echo "Target Host:        $HA_HOST"
echo "Destination Path:   $HA_CONFIG_DEST"
echo "Dry Run:            $DRY_RUN"
echo "================================================================="

# Preflight: Verify dashboard integrity first
echo "▶ 1. Running preflight verification tests..."
python3 "$ROOT_DIR/scripts/build_dashboard.py"
python3 "$ROOT_DIR/tests/test_dashboard_integrity.py"
echo "✓ Preflight tests passed cleanly."

# Build sync payload list
SYNC_ITEMS=(
  "dashboards"
  "pyscript"
  "packages"
  "configuration.yaml"
  "automations.yaml"
  "scripts.yaml"
  "scenes.yaml"
)

if [ "$LOCAL_DOCKER" = true ]; then
  echo "▶ 2. Deploying directly to local Docker container '$HA_CONTAINER'..."
  for item in "${SYNC_ITEMS[@]}"; do
    if [ -e "$ROOT_DIR/$item" ]; then
      if [ "$DRY_RUN" = true ]; then
        echo "  [DRY-RUN] docker cp $ROOT_DIR/$item $HA_CONTAINER:/config/$item"
      else
        docker cp "$ROOT_DIR/$item" "$HA_CONTAINER:/config/"
        echo "  ✓ Copied $item to $HA_CONTAINER:/config/"
      fi
    fi
  done
else
  echo "▶ 2. Synchronizing via rsync over SSH to $HA_USER@$HA_HOST:$HA_CONFIG_DEST..."
  RSYNC_OPTS="-avz --delete --exclude '__pycache__' --exclude '*.pyc' --exclude '.DS_Store'"
  if [ "$DRY_RUN" = true ]; then
    RSYNC_OPTS="$RSYNC_OPTS --dry-run"
  fi

  for item in "${SYNC_ITEMS[@]}"; do
    if [ -e "$ROOT_DIR/$item" ]; then
      echo "  • Syncing $item..."
      rsync $RSYNC_OPTS "$ROOT_DIR/$item" "$HA_USER@$HA_HOST:$HA_CONFIG_DEST/"
    fi
  done
fi

echo "================================================================="
echo "✓ SYNCHRONIZATION COMPLETE"
echo "================================================================="

if [ "$RELOAD_AFTER" = true ] && [ -n "${HA_TOKEN:-}" ]; then
  echo "▶ 3. Triggering Home Assistant configuration reload..."
  curl -s -X POST \
    -H "Authorization: Bearer $HA_TOKEN" \
    -H "Content-Type: application/json" \
    "http://$HA_HOST:8123/api/services/pyscript/reload" || true
  curl -s -X POST \
    -H "Authorization: Bearer $HA_TOKEN" \
    -H "Content-Type: application/json" \
    "http://$HA_HOST:8123/api/services/homeassistant/reload_all" || true
  echo "✓ PyScript & Home Assistant configurations reloaded."
fi

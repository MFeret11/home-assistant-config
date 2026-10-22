#!/usr/bin/env bash
# ==============================================================================
# Safe Online SQLite Backup Script for Home Assistant
# Uses SQLite Online Backup API (.backup) to prevent lock contention
# ==============================================================================
set -euo pipefail

HA_CONFIG_DIR="${HA_CONFIG_DIR:-/config}"
DB_PATH="${HA_CONFIG_DIR}/home-assistant_v2.db"
BACKUP_DIR="${HA_CONFIG_DIR}/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/home-assistant_v2_${TIMESTAMP}.db"

mkdir -p "${BACKUP_DIR}"

if [ ! -f "${DB_PATH}" ]; then
  echo "[-] SQLite database not found at ${DB_PATH}"
  exit 1
fi

echo "[*] Initiating non-blocking online backup of ${DB_PATH}..."
sqlite3 "${DB_PATH}" ".backup '${BACKUP_FILE}'"

if [ -f "${BACKUP_FILE}" ]; then
  SIZE_MB=$(du -m "${BACKUP_FILE}" | cut -f1)
  echo "[+] Backup successfully created: ${BACKUP_FILE} (${SIZE_MB} MB)"
  
  # Keep only last 5 backups
  echo "[*] Cleaning old backups (keeping latest 5)..."
  ls -1t "${BACKUP_DIR}"/home-assistant_v2_*.db | tail -n +6 | xargs -I {} rm -- "{}" 2>/dev/null || true
  echo "[+] Done."
else
  echo "[-] Backup failed!"
  exit 1
fi

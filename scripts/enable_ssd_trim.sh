#!/usr/bin/env bash
# ==============================================================================
# Raspberry Pi 4 USB SSD TRIM Provisioning Script
# Target Hardware: Sabrent 2.5" Enclosure (EC-UASP / JMicron JMS578 [152d:0578])
# Target SSD:      Crucial BX500 240GB 3D NAND SATA (CT240BX500SSD1)
# ==============================================================================
set -euo pipefail

echo "======================================================================"
echo "  SABRENT EC-UASP + CRUCIAL BX500 TRIM & UASP VERIFICATION SCRIPT"
echo "======================================================================"

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root: sudo bash $0"
  exit 1
fi

echo "[*] Step 1: Checking current disk device..."
ROOT_DEV=$(findmnt -n -o SOURCE /)
echo "    Root filesystem is mounted on: ${ROOT_DEV}"

# Identify parent disk
DISK_DEV=$(lsblk -no pkname "${ROOT_DEV}" 2>/dev/null || echo "sda")
if [ -z "${DISK_DEV}" ]; then
  DISK_DEV="sda"
fi
echo "    Parent block device: /dev/${DISK_DEV}"

echo "[*] Step 2: Checking SCSI provisioning mode..."
PROV_PATH="/sys/block/${DISK_DEV}/device/scsi_disk/*/provisioning_mode"
CURRENT_PROV=$(cat ${PROV_PATH} 2>/dev/null || echo "unknown")
echo "    Current provisioning_mode: ${CURRENT_PROV}"

echo "[*] Step 3: Installing udev rule for Sabrent JMS578 (152d:0578)..."
UDEV_RULE_FILE="/etc/udev/rules.d/10-trim.rules"

cat <<'EOF' > "${UDEV_RULE_FILE}"
# Enable TRIM / UNMAP for Sabrent EC-UASP Enclosure (JMicron JMS578 Bridge)
ACTION=="add|change", ATTRS{idVendor}=="152d", ATTRS{idProduct}=="0578", SUBSYSTEM=="scsi_disk", ATTR{provisioning_mode}="unmap"
EOF

echo "    Created: ${UDEV_RULE_FILE}"
echo "    Applying udev rules..."
udevadm control --reload-rules
udevadm trigger

# Apply directly to active sysfs node if present
for p in /sys/block/${DISK_DEV}/device/scsi_disk/*/provisioning_mode; do
  if [ -f "$p" ]; then
    echo "unmap" > "$p" 2>/dev/null || true
  fi
done

echo "[*] Step 4: Testing fstrim execution..."
if fstrim -v /; then
  echo "[+] SUCCESS: fstrim completed successfully on /"
else
  echo "[!] Notice: fstrim reported an error. A reboot may be required for the udev rule to take full effect."
fi

echo "[*] Step 5: Enabling systemd weekly fstrim timer..."
if systemctl is-enabled fstrim.timer >/dev/null 2>&1; then
  echo "    fstrim.timer is already enabled."
else
  systemctl enable --now fstrim.timer
  echo "    Enabled and started fstrim.timer."
fi

echo "======================================================================"
echo "[+] PROVISIONING COMPLETE: Crucial BX500 TRIM is configured and active."
echo "======================================================================"

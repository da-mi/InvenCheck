#!/bin/bash
set -e

REPO_URL="https://github.com/da-mi/InvenCheck.git"
INSTALL_DIR="/opt/invencheck"
PYTHON_EXEC="/usr/bin/python3"
VENV_DIR="$INSTALL_DIR/venv"
PY_VENV_ALIAS="py-invencheck"
SERVICE_NAME="invencheck"
SNMP_COMMUNITY="itmxp-invensense"

# === BANNER ===
print_banner() {
    echo "#############################################"
    echo "#    InvenCheck NFC Attendance System       #"
    echo "#    Damiano Milani - 2025                  #"
    echo "#                                           #"
    echo "#    Installer & Updater Script             #"
    echo "#############################################"
    echo
}

# === FUNCTIONS ===

setup_base() {
    echo "[System] Updating system..."
    apt update
    echo

    echo "[System] Installing required packages..."
    apt install -y git python3 python3-venv python3-pip watchdog snmp snmpd
    echo

    echo "[System] Disabling unused services..."
    systemctl disable bluetooth.service hciuart.service triggerhappy.service
    echo

    echo "[System] Enabling watchdog..."
    sed -i 's/^#watchdog-device/watchdog-device/' /etc/watchdog.conf
    systemctl enable watchdog
    echo

    echo "[System] Disabling Wi-Fi power management..."
    IWCONFIG_OUT=$(iwconfig 2>/dev/null | grep -o "wlan[0-9]*" || true)
    for IFACE in $IWCONFIG_OUT; do
        iwconfig "$IFACE" power off || true
    done
    cat <<EOF >/etc/NetworkManager/conf.d/wifi-pm.conf
[connection]
wifi.powersave = 2
EOF
    echo

    echo "[Service] Configuring pigpiod..."
    systemctl enable pigpiod
    systemctl start pigpiod
    echo

    echo "[Service] Enabling time synchronization..."
    systemctl enable systemd-timesyncd
    systemctl start systemd-timesyncd
    systemctl enable systemd-time-wait-sync
    systemctl start systemd-time-wait-sync
    echo

    echo "[Service] Configuring SNMP client..."
    sed -i "s/^rocommunity .*/rocommunity $SNMP_COMMUNITY/" /etc/snmp/snmpd.conf || \
    echo "rocommunity $SNMP_COMMUNITY" >> /etc/snmp/snmpd.conf
    systemctl enable snmpd
    systemctl restart snmpd
    echo

    echo "[OK] Base system setup complete."
    echo
}

enable_usb_gadget() {
    echo "[USB] Enabling USB Gadget Mode (OTG)..."
    BOOT_CONFIG="/boot/firmware/config.txt"
    CMDLINE_FILE="/boot/firmware/cmdline.txt"
    MODULES_FILE="/etc/modules"

    echo "-> Ensuring 'dtoverlay=dwc2' in $BOOT_CONFIG"
    if ! grep -q "dtoverlay=dwc2,dr_mode=peripheral" "$BOOT_CONFIG"; then
        echo -e "dtoverlay=dwc2,dr_mode=peripheral" >> "$BOOT_CONFIG"
    fi

    echo "-> Adding 'modules-load=dwc2,g_ether' to $CMDLINE_FILE"
    if ! grep -q "modules-load=dwc2,g_ether" "$CMDLINE_FILE"; then
        sed -i 's|\(rootwait\)|\1 modules-load=dwc2,g_ether|' "$CMDLINE_FILE"
    fi
    echo

    echo "[USB] Configuring USB gadget for NetworkManager..."
    setup_usb_gadget_networkmanager

    echo "[OK] USB gadget mode setup complete. A reboot is required."
    echo
}

setup_usb_gadget_networkmanager() {
    echo "-> Patching unmanaged rule (if needed)..."
    if [ -f /usr/lib/udev/rules.d/85-nm-unmanaged.rules ]; then
        cp /usr/lib/udev/rules.d/85-nm-unmanaged.rules /etc/udev/rules.d/85-nm-unmanaged.rules
        sed -i 's/^[^#]*gadget/# &/' /etc/udev/rules.d/85-nm-unmanaged.rules
    fi

    echo "-> Creating usb0-dhcp config..."
    CONNFILE1=/etc/NetworkManager/system-connections/usb0-dhcp.nmconnection
    UUID1=$(uuid -v4)
    cat <<EOF > "$CONNFILE1"
[connection]
id=usb0-dhcp
uuid=$UUID1
type=ethernet
interface-name=usb0
autoconnect-priority=100
autoconnect-retries=2

[ethernet]

[ipv4]
dhcp-timeout=3
method=auto

[ipv6]
addr-gen-mode=default
method=auto

[proxy]
EOF

    echo "-> Creating usb0-ll fallback config..."
    CONNFILE2=/etc/NetworkManager/system-connections/usb0-ll.nmconnection
    UUID2=$(uuid -v4)
    cat <<EOF > "$CONNFILE2"
[connection]
id=usb0-ll
uuid=$UUID2
type=ethernet
interface-name=usb0
autoconnect-priority=50

[ethernet]

[ipv4]
method=link-local

[ipv6]
addr-gen-mode=default
method=auto

[proxy]
EOF
    chmod 600 "$CONNFILE1" "$CONNFILE2"

    echo "[OK] NetworkManager usb0 configuration complete."
    echo
}

setup_venv() {
    echo "[Python] Creating Python virtual environment..."
    mkdir -p "$INSTALL_DIR"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install -r "$INSTALL_DIR/invencheck-raspi/requirements.txt"
    deactivate
    echo

    echo "[Python] Adding global alias: $PY_VENV_ALIAS"
    ALIAS_LINE="alias $PY_VENV_ALIAS='$VENV_DIR/bin/python'"
    grep -qxF "$ALIAS_LINE" /etc/bash.bashrc || echo "$ALIAS_LINE" >> /etc/bash.bashrc
    echo
}

clone_repo() {
    echo "[Git] Cloning or updating repository..."
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "-> Repo already exists, pulling latest..."
        cd "$INSTALL_DIR"
        git pull
    else
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
    
    echo "-> Setting Git safe.directory for ${INSTALL_DIR}"
    git config --system --add safe.directory "$INSTALL_DIR"

    cd "$INSTALL_DIR"
    echo "-> Install/update time: $(date)"
    echo "-> Current commit: $(git log -1 --pretty=format:'%h - %s (%ci)')"
    echo
}

setup_service() {
    echo "[Daemon] Creating systemd services..."
    
    echo "-> Optimizing pigpiod for lower CPU usage..."
    mkdir -p /etc/systemd/system/pigpiod.service.d
    cat <<EOF >/etc/systemd/system/pigpiod.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/pigpiod -l -m
EOF
    
    echo
    echo "-> Creating InvenCheck service..."
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=InvenCheck NFC Attendance System
After=network-online.target systemd-time-wait-sync.service pigpiod.service
Wants=network-online.target systemd-time-wait-sync.service pigpiod.service

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/python -u $INSTALL_DIR/invencheck-raspi/InvenCheck_main.py
ExecStopPost=$VENV_DIR/bin/python -u $INSTALL_DIR/invencheck-raspi/boot_message.py stopped
WorkingDirectory=$INSTALL_DIR/invencheck-raspi
StandardOutput=journal
StandardError=journal
Restart=on-failure
User=morpheus

[Install]
WantedBy=multi-user.target
EOF

    echo
    echo "-> Creating boot LCD service..."
    cat <<EOF >/etc/systemd/system/boot-lcd.service
[Unit]
Description=LCD Boot Message
DefaultDependencies=no
After=local-fs.target

[Service]
Type=oneshot
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/invencheck-raspi/boot_message.py boot

[Install]
WantedBy=sysinit.target
EOF

    echo
    echo "-> Running new services..."
    systemctl daemon-reexec
    systemctl daemon-reload
    systemctl daemon-reload
    systemctl restart pigpiod
    systemctl enable boot-lcd.service
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"
    
    echo
    echo "[OK] Systemd services setup complete."
    echo
}

update_repo() {
    echo "[Git] Checking repository..."
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        echo "-> Repo not found at $INSTALL_DIR"
        exit 1
    fi

    echo "-> Pulling latest changes..."
    cd "$INSTALL_DIR"
    git pull
    echo "-> Update time: $(date)"
    echo "-> Current commit: $(git log -1 --pretty=format:'%h - %s (%ci)')"
    echo

    echo "-> Updating Python dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install -r "$INSTALL_DIR/invencheck-raspi/requirements.txt"
    deactivate
    echo

    systemctl restart "$SERVICE_NAME"
    echo "[OK] Update complete and service restarted."
    echo
}

# === ENTRY POINT ===

print_banner

case "$1" in
    install)
        setup_base
        enable_usb_gadget
        clone_repo
        setup_venv
        setup_service

        echo "=== INSTALLATION COMPLETE ==="
        echo "-> Reboot is required to activate USB gadget mode."
        echo "-> To monitor logs: journalctl -u $SERVICE_NAME -f"
        ;;
    update)
        update_repo
        ;;
    *)
        echo "Usage: $0 [install|update]"
        exit 1
        ;;
esac

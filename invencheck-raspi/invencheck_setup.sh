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
    #systemctl start pigpiod
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


build_wifi_driver() {
    DRIVER_REPO="https://github.com/da-mi/aic8800dc-linux-patched"
    DRIVER_BUILD_DIR="/tmp/aic8800dc-build"

    echo "[Driver] Installing build dependencies..."
    apt install -y git build-essential raspberrypi-kernel-headers
    echo

    echo "[Driver] Cloning driver source..."
    rm -rf "$DRIVER_BUILD_DIR"
    git clone "$DRIVER_REPO" "$DRIVER_BUILD_DIR"
    echo

    echo "[Driver] Compiling..."
    make -C "$DRIVER_BUILD_DIR/drivers/aic8800"
    echo

    echo "[Driver] Installing module..."
    make -C "$DRIVER_BUILD_DIR/drivers/aic8800" install
    depmod -a
    echo

    echo "[Driver] Configuring module to load at boot..."
    echo "aic8800dc" > /etc/modules-load.d/aic8800dc.conf
    echo

    rm -rf "$DRIVER_BUILD_DIR"
    echo "[OK] WiFi driver build and install complete."
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

    echo "-> Running new services..."
    systemctl daemon-reexec
    systemctl daemon-reload
    systemctl daemon-reload
    systemctl is-active --quiet pigpiod && systemctl restart pigpiod || systemctl start pigpiod
    systemctl enable boot-lcd.service
    systemctl enable "$SERVICE_NAME"
    systemctl is-active --quiet "$SERVICE_NAME" && systemctl restart "$SERVICE_NAME" || systemctl start "$SERVICE_NAME"
    
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
        build_wifi_driver
        clone_repo
        setup_venv
        setup_service

        echo "=== INSTALLATION COMPLETE ==="
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

#!/bin/bash
set -e

REPO_URL="https://github.com/da-mi/InvenCheck.git"
INSTALL_DIR="/opt/invencheck"
PYTHON_EXEC="/usr/bin/python3"
VENV_DIR="$INSTALL_DIR/venv"
PY_VENV_ALIAS="py-invencheck"
SERVICE_NAME="invencheck"
SNMP_COMMUNITY="itmxp-invensense"
DRIVER_MARKER_FILE="/var/lib/invencheck/wifi_driver_installed"
FORCE_WIFI_DRIVER_BUILD=0

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

setup_persistent_wlan_names() {
    echo "-> Detecting WiFi interfaces..."

    # Get all wlan interfaces and their MAC addresses
    WLAN_INTERFACES=$(ip link show | grep -E "^[0-9]+: wlan" | awk '{print $2}' | tr -d ':')

    if [ -z "$WLAN_INTERFACES" ]; then
        echo "   Warning: No WiFi interfaces found"
        return
    fi

    # Detect internal vs USB by driver
    INTERNAL_MAC=""
    USB_MAC=""

    for IFACE in $WLAN_INTERFACES; do
        MAC=$(cat /sys/class/net/$IFACE/address 2>/dev/null)
        DRIVER=$(basename $(readlink /sys/class/net/$IFACE/device/driver) 2>/dev/null)

        if [[ "$DRIVER" == *"brcm"* ]] || [[ "$DRIVER" == *"aic8800"* ]] || [[ ! -L /sys/class/net/$IFACE/device ]]; then
            # Likely internal (Broadcom or AIC8800)
            INTERNAL_MAC="$MAC"
            echo "   Internal WiFi: $IFACE ($MAC)"
        else
            # Likely USB
            USB_MAC="$MAC"
            echo "   USB WiFi: $IFACE ($MAC)"
        fi
    done

    # If only one interface, keep it as wlan0
    if [ -z "$USB_MAC" ]; then
        echo "   Single interface detected, skipping persistent naming"
        return
    fi

    # Create udev rule file
    echo "-> Creating udev rules..."
    cat <<EOF >/etc/udev/rules.d/70-persistent-wlan.rules
# Internal WiFi → wlan0
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="$INTERNAL_MAC", NAME="wlan0"

# USB WiFi dongle → wlan1
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="$USB_MAC", NAME="wlan1"
EOF

    # Apply udev rules
    udevadm control --reload-rules
    udevadm trigger

    echo "   Udev rules applied. Interfaces will be stable after reboot."
}

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
    echo

    echo "[Service] Configuring SNMP client..."
    if grep -Eq "^[[:space:]]*rocommunity[[:space:]]+$SNMP_COMMUNITY([[:space:]]|$)" /etc/snmp/snmpd.conf; then
        echo "-> SNMP community already configured"
    elif grep -Eq "^[[:space:]]*rocommunity[[:space:]]+" /etc/snmp/snmpd.conf; then
        sed -i "0,/^[[:space:]]*rocommunity[[:space:]]\+.*/s//rocommunity $SNMP_COMMUNITY/" /etc/snmp/snmpd.conf
    else
        echo "rocommunity $SNMP_COMMUNITY" >> /etc/snmp/snmpd.conf
    fi
    systemctl enable snmpd
    systemctl restart snmpd
    echo

    echo "[OK] Base system setup complete."
    echo
}


build_wifi_driver() {
    DRIVER_REPO="https://github.com/da-mi/aic8800dc-linux-patched"
    DRIVER_BUILD_DIR="/tmp/aic8800dc-build"

    if [ "$FORCE_WIFI_DRIVER_BUILD" -ne 1 ] && [ -f "$DRIVER_MARKER_FILE" ]; then
        echo "[Driver] Marker found, skipping WiFi driver build."
        echo "         Use '--rebuild-wifi-driver' with install to force rebuild."
        echo
        return
    fi

    echo "[Driver] Installing build dependencies..."
    apt install -y git dkms build-essential linux-headers-$(uname -r) linux-headers-generic
    echo

    echo "[Driver] Cloning driver source..."
    rm -rf "$DRIVER_BUILD_DIR"
    git clone "$DRIVER_REPO" "$DRIVER_BUILD_DIR"
    echo

    echo "[Driver] Running install script..."
    chmod +x "$DRIVER_BUILD_DIR/install.sh"
    bash "$DRIVER_BUILD_DIR/install.sh"
    echo

    rm -rf "$DRIVER_BUILD_DIR"
    mkdir -p "$(dirname "$DRIVER_MARKER_FILE")"
    date -Iseconds > "$DRIVER_MARKER_FILE"
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
    if git config --system --get-all safe.directory | grep -Fxq "$INSTALL_DIR"; then
        echo "-> safe.directory already configured"
    else
        git config --system --add safe.directory "$INSTALL_DIR"
    fi

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
After=network.target pigpiod.service
Wants=pigpiod.service

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
        for arg in "$@"; do
            case "$arg" in
                install)
                    ;;
                --rebuild-wifi-driver)
                    FORCE_WIFI_DRIVER_BUILD=1
                    ;;
                *)
                    echo "Unknown option for install: $arg"
                    echo "Usage: $0 install [--rebuild-wifi-driver]"
                    exit 1
                    ;;
            esac
        done

        setup_base
        build_wifi_driver
        setup_persistent_wlan_names
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
        echo "Usage: $0 [install [--rebuild-wifi-driver]|update]"
        exit 1
        ;;
esac

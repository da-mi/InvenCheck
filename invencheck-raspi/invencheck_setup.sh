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
    echo "#    Damiano Milani  - 2025                 #"
    echo "#                                           #"
    echo "#    Installer & Updater Script - v1.0      #"
    echo "#############################################"
    echo
}

# === FUNCTIONS ===

setup_base() {
    echo "=== Updating system ==="
    apt update

    echo "=== Installing essentials ==="
    apt install -y git python3 python3-venv python3-pip watchdog snmp snmpd

    echo "=== Disabling unused services ==="
    systemctl disable bluetooth.service hciuart.service triggerhappy.service

    echo "=== Enabling watchdog ==="
    sed -i 's/^#watchdog-device/watchdog-device/' /etc/watchdog.conf
    systemctl enable watchdog

    # echo "=== Disabling IPv6 system-wide ==="
    # sysctl_conf="/etc/sysctl.d/99-disable-ipv6.conf"
    # echo "net.ipv6.conf.all.disable_ipv6 = 1" > $sysctl_conf
    # echo "net.ipv6.conf.default.disable_ipv6 = 1" >> $sysctl_conf
    # sysctl -p $sysctl_conf

    echo "=== Disabling Wi-Fi power management ==="
    IWCONFIG_OUT=$(iwconfig 2>/dev/null | grep -o "wlan[0-9]*" || true)
    for IFACE in $IWCONFIG_OUT; do
        iwconfig "$IFACE" power off || true
    done
    cat <<EOF >/etc/NetworkManager/conf.d/wifi-pm.conf
[connection]
wifi.powersave = 2
EOF

    echo "=== Configuring pigpiod ==="
    systemctl enable pigpiod
    systemctl start pigpiod

    echo "=== Enabling time sync ==="
    systemctl enable systemd-timesyncd
    systemctl start systemd-timesyncd
    systemctl enable systemd-time-wait-sync
    systemctl start systemd-time-wait-sync

    echo "=== Configuring SNMP client ==="
    sed -i "s/^rocommunity .*/rocommunity $SNMP_COMMUNITY/" /etc/snmp/snmpd.conf || \
    echo "rocommunity $SNMP_COMMUNITY" >> /etc/snmp/snmpd.conf
    systemctl enable snmpd
    systemctl restart snmpd

    echo "=== Base system setup complete ==="
}

enable_usb_gadget() {
    echo "=== Enabling USB Gadget Mode (OTG) ==="

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

#     echo "-> Ensuring required modules are listed in $MODULES_FILE"
#     grep -q "^dwc2" "$MODULES_FILE" || echo "dwc2" >> "$MODULES_FILE"
#     grep -q "^g_ether" "$MODULES_FILE" || echo "g_ether" >> "$MODULES_FILE"

#     echo "-> Setting up udev rule for USB gadget network interface (usb0)"
#     cat <<EOF >/etc/udev/rules.d/90-usb-gadget.rules
# SUBSYSTEM=="usb", ATTR{idVendor}=="1d6b", ATTR{idProduct}=="0104", ACTION=="add", RUN+="/sbin/ifconfig usb0 up"
# EOF

    echo "-> USB gadget mode setup done. A reboot is required to activate."
}

setup_venv() {
    echo "=== Creating Python virtual environment ==="
    mkdir -p "$INSTALL_DIR"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install -r "$INSTALL_DIR/invencheck-raspi/requirements.txt"
    deactivate

    echo "=== Adding alias for venv Python as '$PY_VENV_ALIAS' ==="
    ALIAS_LINE="alias $PY_VENV_ALIAS='$VENV_DIR/bin/python'"
    grep -qxF "$ALIAS_LINE" /etc/bash.bashrc || echo "$ALIAS_LINE" >> /etc/bash.bashrc
}

clone_repo() {
    echo "=== Setting up InvenCheck repo ==="
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "Repo already exists, updating..."
        cd "$INSTALL_DIR"
        git pull
    else
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi

    cd "$INSTALL_DIR"
    echo "Install/update time: $(date)"
    echo "Current commit: $(git log -1 --pretty=format:'%h - %s (%ci)')"
}

setup_service() {
    echo "=== Setting up systemd service ==="
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

    systemctl daemon-reexec
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"

    echo "=== Setting up LCD boot systemd service ==="
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

    systemctl daemon-reload
    systemctl enable boot-lcd.service

    echo "=== Optimizing pigpiod to limit CPU usage ==="
    mkdir -p /etc/systemd/system/pigpiod.service.d
    cat <<EOF >/etc/systemd/system/pigpiod.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/pigpiod -l -m
EOF
    systemctl daemon-reexec
    systemctl daemon-reload
    systemctl restart pigpiod
}

update_repo() {
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        echo "Repo not found at $INSTALL_DIR"
        exit 1
    fi

    echo "=== Updating InvenCheck repo ==="
    cd "$INSTALL_DIR"
    git pull
    echo "Update time: $(date)"
    echo "Current commit: $(git log -1 --pretty=format:'%h - %s (%ci)')"

    source "$VENV_DIR/bin/activate"
    pip install -r "$INSTALL_DIR/invencheck-raspi/requirements.txt"
    deactivate

    systemctl restart "$SERVICE_NAME"
    echo "=== Update complete and service restarted ==="
}

# === ENTRY POINT ===

print_banner

case "$1" in
    install)
        setup_base
        clone_repo
        setup_venv
        setup_service
        enable_usb_gadget
        echo "All done. Reboot is required to activate USB gadget mode."
        echo "To see logs: journalctl -u $SERVICE_NAME -f"
        ;;
    update)
        update_repo
        ;;
    *)
        echo "Usage: $0 [install|update]"
        exit 1
        ;;
esac

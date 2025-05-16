#!/bin/bash
set -e

REPO_URL="https://github.com/da-mi/InvenCheck.git"
INSTALL_DIR="/opt/invencheck"
VENV_DIR="$INSTALL_DIR/venv"
PYTHON_EXEC="/usr/bin/python3"
SERVICE_NAME="invencheck"

# === FUNCTIONS ===

setup_base() {
    echo "=== Updating system ==="
    apt update

    echo "=== Installing essentials ==="
    apt install -y git python3 python3-venv python3-pip watchdog

    echo "=== Disable unused services ==="
    systemctl disable bluetooth.service hciuart.service triggerhappy.service

    # echo "=== Enable tmpfs for /tmp ==="
    # grep -q '/tmp tmpfs' /etc/fstab || echo 'tmpfs /tmp tmpfs defaults,noatime,nosuid 0 0' >> /etc/fstab

    echo "=== Enable watchdog ==="
    sed -i 's/^#watchdog-device/watchdog-device/' /etc/watchdog.conf
    systemctl enable watchdog

    echo "=== Configure pigpiod ==="
    systemctl enable pigpiod
    systemctl start pigpiod

    echo "=== Force time wait sync ==="
    systemctl enable systemd-time-wait-sync

    # echo "=== Reduce systemd timeouts ==="
    # for CONF in /etc/systemd/system.conf /etc/systemd/user.conf; do
    #     sed -i 's/^#*DefaultTimeoutStartSec=.*$/DefaultTimeoutStartSec=5s/' "$CONF"
    #     sed -i 's/^#*DefaultTimeoutStopSec=.*$/DefaultTimeoutStopSec=5s/' "$CONF"
    # done

    echo "=== Base system setup complete ==="
}

setup_venv() {
    echo "=== Creating Python virtual environment ==="
    mkdir -p "$INSTALL_DIR"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install -r "$INSTALL_DIR/invencheck-raspi/requirements.txt"
    deactivate
}

clone_repo() {
    echo "=== Cloning InvenCheck repo ==="
    if [ -d "$INSTALL_DIR" ]; then
        echo "Repo already exists, skipping clone."
    else
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
}

setup_service() {
    echo "=== Setting up systemd service ==="
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=InvenCheck NFC Attendance System
After=network.target

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
    echo "=== Service '$SERVICE_NAME' started ==="

    echo "=== Setting up LCD boot systemd services ==="
    #Create boot-lcd.service
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

    # Reload systemd to detect new services
    systemctl daemon-reload
    systemctl enable boot-lcd.service

    echo "===  boot-lcd service installed and enabled. === "


    ### === Optimize pigpiod with -m flag ===
    echo "===  Configuring pigpiod for reduced CPU usage... === "

    # Create systemd override directory if needed
    mkdir -p /etc/systemd/system/pigpiod.service.d

    # Create override file
    cat <<EOF >/etc/systemd/system/pigpiod.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/pigpiod -l -m
EOF

    # Reload and restart the service
    systemctl daemon-reexec
    systemctl daemon-reload
    systemctl restart pigpiod

    echo "===  pigpiod reconfigured to use -m flag. === "
}

update_repo() {
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        echo "Repo not found at $INSTALL_DIR"
        exit 1
    fi

    echo "=== Updating InvenCheck repo ==="
    cd "$INSTALL_DIR"
    git pull
    source "$VENV_DIR/bin/activate"
    pip install -r "$INSTALL_DIR/invencheck-raspi/requirements.txt"
    deactivate
    systemctl restart "$SERVICE_NAME"
    echo "=== Update complete and service restarted ==="
}

# === ENTRY POINT ===

case "$1" in
    install)
        setup_base
        clone_repo
        setup_venv
        setup_service
        echo "All done. To see logs: journalctl -u $SERVICE_NAME -f"
        ;;
    update)
        update_repo
        ;;
    *)
        echo "Usage: $0 [install|update]"
        exit 1
        ;;
esac

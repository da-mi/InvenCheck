"""
LCD class definition
LCD 2004 connected to a Raspberry Pi via I2C

Damiano Milani
2025
"""

from RPLCD.i2c import CharLCD
import socket
import time
import threading
import subprocess
import psutil

class LCD:
    def __init__(self, address=0x27, cols=20, rows=4, default_interval=5, diag_duration=30, backlight_timeout=60):
        self.lcd = CharLCD('PCF8574', address, cols=cols, rows=rows, backlight_enabled=True, auto_linebreaks=True)
        self.default_interval = default_interval
        self.diag_duration = diag_duration
        self.backlight_timeout = backlight_timeout
        self.last_interaction_time = time.time()
        self.active_message_until = 0
        self.lock = threading.RLock()
        self.default_screen_lines = ["***  InvenCheck  ***", "", "Place NFC", "tag below"]
        self.current_lines = ["", "", "", ""]

        threading.Thread(target=self._screen_manager_loop, daemon=True).start()

    def clear(self):
        with self.lock:
            self.lcd.clear()

    def _write_lines(self, lines):
        with self.lock:
            self.clear()
            for i, line in enumerate(lines[:4]):
                self.lcd.cursor_pos = (i, 0)
                self.lcd.write_string(line.ljust(20))
            self.current_lines = lines

    def show_message(self, lines, duration=None):
        if duration is None:
            duration = self.default_interval
        with self.lock:
            self.last_interaction_time = time.time()
            self.active_message_until = self.last_interaction_time + duration
            self.lcd.backlight_enabled = True
        self._write_lines(lines)

    def show_diagnostic(self):
        try:
            hostname = socket.gethostname()

            # SSID
            ssid = subprocess.check_output(['iwgetid', '-r'], text=True).strip()

            # IP
            ip_output = subprocess.check_output(['ip', '-4', 'addr', 'show', 'wlan0'], text=True)
            ip_line = next((line for line in ip_output.splitlines() if "inet " in line), "")
            ip_address = ip_line.split()[1].split('/')[0] if ip_line else "N/A"

            # CPU Temp
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp_c = int(f.read().strip()) / 1000.0

            # CPU Usage
            cpu_usage = psutil.cpu_percent(interval=0.5)

            lines = [
                f"{hostname}",
                f"SSID: {ssid[:15]}" if ssid else "SSID: Unknown",
                f"IP: {ip_address}",
                f"Temp: {temp_c:.1f}C CPU: {cpu_usage:.0f}%",
            ]
            self.show_message(lines, duration=self.diag_duration)

        except Exception as e:
            self.show_message(["Diagnostic Fail", str(e)[:20], "", ""], duration=self.diag_duration)

    def _default_screen(self):
        self._write_lines(self.default_screen_lines)

    def _screen_manager_loop(self):
        self._default_screen()
        while True:
            time.sleep(0.5)
            now = time.time()

            with self.lock:
                # Backlight timeout
                if now - self.last_interaction_time >= self.backlight_timeout:
                    self.lcd.backlight_enabled = False
                else:
                    self.lcd.backlight_enabled = True

                # Return to default screen
                if self.current_lines != self.default_screen_lines and now >= self.active_message_until:
                    self._default_screen()

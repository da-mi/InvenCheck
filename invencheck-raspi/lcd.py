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
from datetime import datetime

class LCD:
    def __init__(self, address=0x27, cols=20, rows=4, default_interval=5, diag_duration=30, backlight_timeout=300):
        self.lcd = CharLCD('PCF8574', address, cols=cols, rows=rows, backlight_enabled=True, auto_linebreaks=True)
        self.default_interval = default_interval
        self.diag_duration = diag_duration
        self.backlight_timeout = backlight_timeout
        self.last_interaction_time = time.time()
        self.active_message_until = 0
        self.lock = threading.RLock()
        self.last_minute_displayed = None
        self.current_lines = ["", "", "", ""]

        threading.Thread(target=self._screen_manager_loop, daemon=True).start()

    def clear(self):
        with self.lock:
            self.lcd.clear()

    def _write_lines(self, lines):
        with self.lock:
            self.clear()
            for i, line in enumerate(lines[:4]):
                if len(line):
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
        def get_diagnostic_screens():
            hostname = socket.gethostname()

            # SSID
            try:
                ssid = subprocess.check_output(['iwgetid', '-r'], text=True).strip() or "Unknown"
            except:
                ssid = "Unknown"

            # IP wlan0
            try:
                ip_output_wlan = subprocess.check_output(['ip', '-4', 'addr', 'show', 'wlan0'], text=True)
                ip_line_wlan = next((line for line in ip_output_wlan.splitlines() if "inet " in line), "")
                ip_wlan = ip_line_wlan.split()[1].split('/')[0] if ip_line_wlan else "N/A"
            except:
                ip_wlan = "N/A"

            # IP usb0
            try:
                ip_output_usb = subprocess.check_output(['ip', '-4', 'addr', 'show', 'usb0'], text=True)
                ip_line_usb = next((line for line in ip_output_usb.splitlines() if "inet " in line), "")
                ip_usb = ip_line_usb.split()[1].split('/')[0] if ip_line_usb else "N/A"
            except:
                ip_usb = "N/A"

            # Git info
            try:
                git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()[:7]
                git_raw_date = subprocess.check_output(['git', 'log', '-1', '--format=%cd'], text=True).strip()
                git_date = datetime.strptime(git_raw_date, '%a %b %d %H:%M:%S %Y %z').strftime('%d%b%y')
            except:
                git_hash = "no-git"
                git_date = "unknown"

            # CPU Temp
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp_c = int(f.read().strip()) / 1000.0
            except:
                temp_c = 0.0

            # CPU and memory usage
            cpu_usage = psutil.cpu_percent(interval=0.1)
            mem_usage = psutil.virtual_memory().percent

            # Uptime
            uptime_seconds = time.time() - psutil.boot_time()
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            uptime_str = f"{days}d{hours}h{minutes}m"

            screen1 = [
                f"HOST {hostname}",
                f"SSID {ssid[:15]}",
                f"WLAN {ip_wlan}",
                f"USB  {ip_usb}",
            ]
            screen2 = [
                f"GIT  {git_hash} {git_date}",
                f"CPU  {cpu_usage:.0f}%    MEM  {mem_usage:.0f}%",
                f"TEMP {temp_c:.1f}C",
                f"UP   {uptime_str}",
            ]
            return screen1, screen2

        try:
            start_time = time.time()
            screen1, screen2 = get_diagnostic_screens()
            screens = [screen1, screen2]
            index = 0

            with self.lock:
                self.last_interaction_time = time.time()
                self.active_message_until = self.last_interaction_time + self.diag_duration
                self.lcd.backlight_enabled = True

            while time.time() - start_time < self.diag_duration:
                with self.lock:
                    if time.time() >= self.active_message_until:
                        break  # Another show_message was called externally

                self._write_lines(screens[index % 2])
                index += 1
                time.sleep(5)

            self._default_screen(force=True)

        except Exception as e:
            self.show_message(["Diagnostic Fail", str(e)[:20], "", ""], duration=self.diag_duration)
    
    def _default_screen(self, force=False):
        now = datetime.now()
        current_minute = now.strftime("%Y-%m-%d     %H:%M")
        
        if not force and self.current_lines == self.default_screen_lines and self.last_minute_displayed == current_minute:
            return  # Avoid redundant refresh

        self.last_minute_displayed = current_minute
        self.default_screen_lines = [
            "***  InvenCheck  ***",
            "",
            "Place NFC Tag below",
            current_minute
        ]
        self._write_lines(self.default_screen_lines)

    def _screen_manager_loop(self):
        self._default_screen(force=True)
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
                    self._default_screen(force=True)
                elif self.current_lines == self.default_screen_lines:
                    self._default_screen(force=False)

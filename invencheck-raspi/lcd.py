"""
LCD class definition
LCD 2004 connected to a Raspberry Pi via I2C

Damiano Milani
2025
"""
from RPLCD.i2c import CharLCD
import socket
import time as t
import threading

class LCD:
    def __init__(self, address=0x27, cols=20, rows=4, default_interval=5, diag_duration=20, backlight_timeout=60):
        self.lcd = CharLCD('PCF8574', address, cols=cols, rows=rows, backlight_enabled=True, auto_linebreaks=True)
        self.default_interval = default_interval
        self.diag_duration = diag_duration
        self.backlight_timeout = backlight_timeout
        self.last_interaction_time = t.time()
        self.lock = threading.RLock()
        self.default_screen_lines = ["***  InvenCheck  ***", "", "Place NFC", "tag below"]
        self.current_lines = ["", "", "", ""]

        threading.Thread(target=self._backlight_watcher, daemon=True).start()
        threading.Thread(target=self._default_screen_loop, daemon=True).start()

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
        with self.lock:
            self.lcd.backlight_enabled = True 
        self._write_lines(lines)
        self.last_interaction_time = t.time()
        if duration is None:
            duration = self.default_interval
        threading.Thread(target=self._restore_default_after_delay, args=(duration,), daemon=True).start()

    def show_diagnostic(self):
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            lines = [
                "InvenCheck Ready",
                f"Host: {hostname[:13]}",
                f"IP: {ip_address}",
                "Status: OK"
            ]
            self.show_message(lines, duration=self.diag_duration)
        except Exception as e:
            self.show_message(["Diagnostic Fail", str(e)[:20], "", ""], duration=self.diag_duration)

    def _default_screen(self):
        self._write_lines(self.default_screen_lines)

    def _restore_default_after_delay(self, delay):
        t.sleep(delay)
        if t.time() - self.last_interaction_time >= delay:
            self._default_screen()

    def _default_screen_loop(self):
        self._default_screen()
        while True:
            t.sleep(1)
            if self.current_lines != self.default_screen_lines and t.time() - self.last_interaction_time >= self.default_interval:
                self._default_screen()

    def _backlight_watcher(self):
        while True:
            t.sleep(5)
            if t.time() - self.last_interaction_time >= self.backlight_timeout:
                with self.lock:
                    self.lcd.backlight_enabled = False
            else:
                with self.lock:
                    self.lcd.backlight_enabled = True


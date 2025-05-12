from lcd import LCD
import socket 



#!/usr/bin/env python3

import sys
from RPLCD.i2c import CharLCD

lcd = CharLCD('PCF8574', 0x27, cols=20, rows=4)  # Update I2C address if needed

def show(lines):
    lcd.clear()
    for line in lines:
        lcd.write_string(line.ljust(20) + '\n')

if __name__ == "__main__":
    lcd = LCD()

    if len(sys.argv) != 2:
        print("Usage: boot_message.py [boot|shutdown|stopped]")
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "boot":
        lcd.show_message(["SYSTEM IS STARTING..", "", f"{socket.gethostname()}", "Please wait..."])
    elif mode == "shutdown":
        lcd.show_message(["REBOOTING SYSTEM...", "", f"{socket.gethostname()}", "Please wait 10s..."])
    elif mode == "stopped":
        lcd.show_message(["INVENCHECK SERVICE", "OR RASPI OS STOPPED!", f"{socket.gethostname()}", "Please wait/reboot.."])

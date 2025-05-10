"""
InvenCheck - Raspberry Pi daemon
Read NFC tag and manage Supabase communication

Damiano Milani
2025
"""

import os
import time
import threading
import socket
import requests
from datetime import datetime
from datetime import time as dt_time
import pytz

from dotenv import load_dotenv

from buzzer import Buzzer
from lcd import LCD
from nfc import NFCReader

# === Load Configuration ===
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
ATTENDANCE_TABLE = "attendance"
EMPLOYEES_TABLE = "users"
DEVICES_TABLE = "devices"

DEVICE_ID = socket.gethostname()
BUZZER_PIN = 13
DB_PING_INTERVAL = 1200  # Every 20 minutes
CONN_CHECK_INTERVAL = 10 

# Initialize Buzzer
buzzer = Buzzer(BUZZER_PIN)

# Initialize LCD (SPI)
lcd = LCD()

# Initialize NFC Reader (I2C)
nfc = NFCReader()

# === API Headers ===
HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# === In-Memory Cache ===
employee_cache = {}



# === Internet Check ===


# === NFC Logic ===
def get_employee_by_uid(uid):
    if str(uid) in employee_cache:
        print(f"[INFO] Tag UID {uid} already in local cache.")
        if employee_cache[str(uid)]["user_id"] == "Unknown":
            print(f"[INFO] Tag UID {uid} is in local cache but Unknown, check if database has been updated.")
        else:
            return employee_cache[str(uid)]

    url = f"{SUPABASE_URL}/rest/v1/{EMPLOYEES_TABLE}?uid=eq.{uid}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        if data:
            employee_cache[str(uid)] = data[0]
            print(f"[INFO] Tag UID {uid} fetched from remote database.")
            return data[0]
    else:
        print(f"[ERROR] Failed to fetch employee: {response.text}")
    return None

def register_unknown_employee(uid):
    payload = {"uid": str(uid), "user_id": "Unknown"}
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{EMPLOYEES_TABLE}", headers=HEADERS, json=payload)
    if response.status_code in (200, 201):
        print(f"[INFO] Unknown employee with UID {uid} registered.")
        employee_cache[str(uid)] = payload
        return payload
    else:
        print(f"[ERROR] Failed to register employee: {response.text}")
        return None

def get_today_cutoff_utc():
    rome = pytz.timezone("Europe/Rome")
    local_midnight = rome.localize(datetime.combine(datetime.now(rome).date(), dt_time.min))
    return local_midnight.astimezone(pytz.utc).isoformat().replace("+00:00", "Z")

def get_last_action_today(user_id):
    utc_cutoff = get_today_cutoff_utc()
    url = (
        f"{SUPABASE_URL}/rest/v1/{ATTENDANCE_TABLE}"
        f"?user_id=eq.{user_id}&timestamp=gte.{utc_cutoff}"
        f"&order=timestamp.desc&limit=1"
    )
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        return data[0]["action"] if data else None
    else:
        print(f"[ERROR] Failed to query Supabase: {response.text}")
        return None

def send_event(user_id, action, device_id):
    payload = {
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "device_id": device_id
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{ATTENDANCE_TABLE}", headers=HEADERS, json=payload)
    if response.status_code in (200, 201):
        now = datetime.now()
        if action == "check_in":
            print(f"\033[32m[OK] {action.replace('_', ' ').upper()} recorded.\033[0m")
            lcd.show_message([user_id, "", "⌂⌂ CHECK-IN", now.strftime("%Y-%m-%d %H:%M")])
            buzzer.checkin()
        else:
            print(f"\033[31m[OK] {action.replace('_', ' ').upper()} recorded.\033[0m")
            lcd.show_message([user_id, "", "~~ CHECK-OUT", now.strftime("%Y-%m-%d %H:%M")])
            buzzer.checkout()
    else:
        print(f"[ERROR] Failed to write to Supabase: {response.text}")
        lcd.show_message(["DB ERROR", "Try again"])
        buzzer.error()
        

# === Heartbeat ===
def device_heartbeat():
    while True:
        payload = {"timestamp": datetime.utcnow().isoformat()}
        try:
            response = requests.patch(
                f"{SUPABASE_URL}/rest/v1/{DEVICES_TABLE}?device_id=eq.{DEVICE_ID}",
                headers=HEADERS,
                json=payload
            )
            if response.status_code == 404 or (response.status_code == 200 and not response.json()):
                payload["device_id"] = DEVICE_ID
                response = requests.post(f"{SUPABASE_URL}/rest/v1/{DEVICES_TABLE}", headers=HEADERS, json=payload)
                if response.status_code not in (200, 201):
                    print(f"[WARN] Failed to insert device: {response.text}")
            elif response.status_code not in (200, 204):
                print(f"[WARN] Heartbeat failed: {response.text}")
        except Exception as e:
            print(f"[WARN] Heartbeat error: {e}")
        time.sleep(DB_PING_INTERVAL)

# === Internet Monitor ===
def has_internet():
    try:
        socket.setdefaulttimeout(1)
        host = socket.gethostbyname("8.8.8.8")
        s = socket.create_connection((host, 53), 2)
        s.close()
        return True
    except:
        return False
    
def internet_check():
    while True:
        if not has_internet():
            print("[WARN] No internet connection!")
            lcd.show_message(["SYSTEM OFFLINE", "", "No internet/network", "Check WiFi config"])
        time.sleep(CONN_CHECK_INTERVAL)


# === Main Loop ===
def main_loop():
    print("\033[1;36m**** TDK InvenCheck - NFC Listener ****\033[0m")
    buzzer.online()

    threading.Thread(target=device_heartbeat, daemon=True).start()
    threading.Thread(target=internet_check, daemon=True).start()

    while True:
        print("\nWaiting for NFC Tag...")
        try:
            uid = nfc.read_uid()
            print(f"Tag detected: UID {uid}")
            lcd.show_message(["Reading Tag..."])
            buzzer.read()

            employee = get_employee_by_uid(uid)

            if not employee:
                employee = register_unknown_employee(uid)
                if not employee:
                    continue

            if employee['user_id'] == "Unknown":
                print("[INFO] Unknown user!")
                lcd.show_message(["UNKNOWN TAG","","Please assign this  tag to someone first"])
                buzzer.error()
                continue
            
            if employee['user_id'].lower() == "administrator":
                print("[INFO] GodMode activated")
                lcd.show_diagnostic()
                buzzer.sweep_test()
                continue

            user_id = employee["user_id"]
            last_action = get_last_action_today(user_id)
            action = "check_out" if last_action == "check_in" else "check_in"

            print(f"Processing {action} for {user_id} at {DEVICE_ID}")
            send_event(user_id, action, DEVICE_ID)
            time.sleep(0.1)

        except Exception as e:
            print(f"[ERROR] {e}")
            lcd.show_message(["ERROR",str(e)])
            buzzer.error()
            time.sleep(0.1)

if __name__ == "__main__":
    main_loop()

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

last_uid_scanned = None
repeat_count = 0

# === NFC Logic ===
def load_all_employees():
    print("[DB] Loading all employees from Supabase...")
    url = f"{SUPABASE_URL}/rest/v1/{EMPLOYEES_TABLE}?select=uid,user_id"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            for employee in response.json():
                employee_cache[str(employee["uid"])] = employee
            print(f"[DB] Loaded {len(employee_cache)} employees into cache.")
        else:
            print(f"[ERROR] Failed to load employee list: {response.text}")
    except Exception as e:
        print(f"[ERROR] Exception while loading employees: {e}")

def delete_unknown_employees():
    url = f"{SUPABASE_URL}/rest/v1/{EMPLOYEES_TABLE}?user_id=eq.Unknown"
    try:
        response = requests.delete(url, headers=HEADERS)
        if response.status_code in (200, 204):
            print("[DB] Unknown employees removed from Supabase.")
        else:
            print(f"[ERROR] Failed to delete unknown employees: {response.text}")
    except Exception as e:
        print(f"[ERROR] Exception during unknown employee cleanup: {e}")

def nightly_employee_refresh():
    while True:
        now = datetime.now()
        next_run = now.replace(hour=4, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run.replace(day=now.day + 1)
        sleep_duration = (next_run - now).total_seconds()
        print(f"[INFO] Next employee cache refresh in {sleep_duration / 3600:.2f} hours.")
        time.sleep(sleep_duration)
        load_all_employees()
        delete_unknown_employees()

def get_employee_by_uid(uid):
    uid_str = str(uid)
    if uid_str in employee_cache:
        print(f"[INFO] Tag UID {uid} already in local cache.")
        if employee_cache[uid_str]["user_id"] == "Unknown":
            print(f"[INFO] Tag UID {uid} is in local cache but Unknown, check if database has been updated.")
        else:
            return employee_cache[uid_str]

    print(f"[INFO] Tag UID {uid} not found in cache. Checking remote database...")
    url = f"{SUPABASE_URL}/rest/v1/{EMPLOYEES_TABLE}?uid=eq.{uid}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        if data:
            employee_cache[uid_str] = data[0]
            print(f"[DB] UID {uid} fetched and cached.")
            return data[0]
    else:
        print(f"[ERROR] Failed to fetch UID {uid}: {response.text}")
    return None

def register_unknown_employee(uid):
    payload = {"uid": str(uid), "user_id": "Unknown"}
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{EMPLOYEES_TABLE}", headers=HEADERS, json=payload)
    if response.status_code in (200, 201):
        print(f"[DB] Unknown employee with UID {uid} registered.")
        employee_cache[str(uid)] = payload
        return payload
    else:
        print(f"[ERROR] Failed to register employee: {response.text}")
        return None
    
def update_unknown_timestamp(uid):
    payload = {"timestamp": datetime.utcnow().isoformat()}
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{EMPLOYEES_TABLE}?uid=eq.{uid}&user_id=eq.Unknown",
        headers=HEADERS,
        json=payload
    )
    if response.status_code in (200, 204):
        print(f"[DB] Updated timestamp for unknown UID {uid}.")
    else:
        print(f"[ERROR] Failed to update timestamp for unknown UID {uid}: {response.text}")


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
            lcd.show_message([user_id, "", "⌂⌂ CHECK-IN", now.strftime("%Y-%m-%d     %H:%M")])
            buzzer.checkin()
        else:
            print(f"\033[31m[OK] {action.replace('_', ' ').upper()} recorded.\033[0m")
            lcd.show_message([user_id, "", "~~ CHECK-OUT", now.strftime("%Y-%m-%d     %H:%M")])
            buzzer.checkout()
    else:
        print(f"[ERROR] Failed to write to Supabase: {response.text}")
        lcd.show_message(["DB ERROR", "Try again"])
        buzzer.error()
        
# === Uovo Handler ===
def check_uovo(tag_uid):
    global last_uid_scanned, repeat_count
    try:
        _l, _c = 'last_uid_scanned', 'repeat_count'
        globals()[_l], globals()[_c] = (
            (tag_uid, globals()[_c] + 1)
            if tag_uid == globals().get(_l) else (tag_uid, 1)
        )

        if globals()[_c] == 7:
            print("[EGG] Sequence complete.")
            msg1 = "".join([chr(c) for c in [87, 97, 107, 101, 32, 117, 112, 44, 32, 78, 101, 111, 46, 46, 46]])
            msg2 = "".join([chr(c) for c in [84, 104, 101, 32, 77, 97, 116, 114, 105, 120, 32, 104, 97, 115, 32, 121, 111, 117, 46, 46]])
            msg3 = "".join([chr(c) for c in [70, 111, 108, 108, 111, 119, 32, 116, 104, 101, 32, 119, 104, 105, 116, 101, 32, 32, 32, 32, 114, 97, 98, 98, 105, 116, 46]])
            msg4 = "".join([chr(c) for c in [75, 110, 111, 99, 107, 44, 32, 107, 110, 111, 99, 107, 44, 32, 78, 101, 111, 46]])
            lcd.show_message([msg1], duration=20)
            buzzer.matrix1()
            lcd.show_message([msg1, "", msg2], duration=20)
            buzzer.matrix2()
            lcd.show_message([msg3], duration=30)
            buzzer.matrix3()
            lcd.show_message([msg4], duration=30)
            globals()[_c] = 0
            return True
    except Exception as e:
        print(f"[EGG ERROR] {e}")
    return False


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
            time.sleep(2)
        else:
            time.sleep(CONN_CHECK_INTERVAL)


# === Main Loop ===
def main_loop():
    print("\033[1;36m**** TDK InvenCheck - NFC Attendance System ****\033[0m")
    print("\033[1;36mdamiano.milani@tdk.com - 2025\033[0m")
    
    load_all_employees()
    threading.Thread(target=nightly_employee_refresh, daemon=True).start()
    threading.Thread(target=device_heartbeat, daemon=True).start()
    threading.Thread(target=internet_check, daemon=True).start()
    buzzer.online()

    while True:
        print("\n[NFC] Waiting for NFC Tag...")
        try:
            uid = nfc.read_uid()
            print(f"[NFC] Tag detected: UID {uid}")
            if check_uovo(uid):
                continue
            lcd.show_message(["***  InvenCheck  ***", "", "Tag detected!", "Reading database..."], duration=10)
            buzzer.read()

            employee = get_employee_by_uid(uid)

            if not employee:
                employee = register_unknown_employee(uid)
                if not employee:
                    continue

            if employee['user_id'] == "Unknown":
                print("[INFO] Unknown user!")
                lcd.show_message(["UNKNOWN TAG","","Please assign this  tag to someone first"])
                update_unknown_timestamp(uid) #renew timestamp
                buzzer.error()
                continue
            
            if employee['user_id'].lower() == "morpheus":
                print("[INFO] God Mode activated")
                lcd.show_diagnostic()
                buzzer.sweep()
                continue

            user_id = employee["user_id"]
            last_action = get_last_action_today(user_id)
            action = "check_out" if last_action == "check_in" else "check_in"

            print(f"[DB] Processing {action} for \"{user_id}\" at {DEVICE_ID}")
            send_event(user_id, action, DEVICE_ID)
            time.sleep(0.1)

        except Exception as e:
            print(f"[ERROR] {e}")
            lcd.show_message(["ERROR",str(e)[:60]])
            buzzer.error()
            time.sleep(0.1)

if __name__ == "__main__":
    main_loop()

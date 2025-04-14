import requests
from datetime import datetime, time
import pytz
import os
import time as t
from dotenv import load_dotenv
from mfrc522 import SimpleMFRC522

import RPi.GPIO as GPIO


# === Load Configuration ===
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
ATTENDANCE_TABLE = "attendance"
EMPLOYEES_TABLE = "employees"

DOOR_ID = "Ingresso A10"

BUZZER_PIN = 24


# --- Setup GPIO ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
buzzer_pwm = GPIO.PWM(BUZZER_PIN, 2000) 


# === NFC Reader ===
reader = SimpleMFRC522()

# === API Headers ===
HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def beep(duration=0.1, frequency=2000):
    buzzer_pwm.ChangeFrequency(frequency)
    buzzer_pwm.start(10)
    t.sleep(duration)
    buzzer_pwm.stop()

def read_beep():
    beep(0.05, 3000)

def online_beep():
    beep(0.05, 1047*2)
    t.sleep(0.05)
    beep(0.05, 1319*2)
    t.sleep(0.05)
    beep(0.05, 1568*2)

def checkin_beep():
    beep(0.05, 3000)
    t.sleep(0.05)
    beep(0.05, 3000)
    t.sleep(0.05)
    beep(0.1, 3000)

def checkout_beep():
    beep(0.1, 2000)
    t.sleep(0.05)
    beep(0.1, 1500)
    t.sleep(0.05)
    beep(0.1, 880)


def error_beep():
    beep(0.2, 150)
    t.sleep(0.05)
    beep(0.2, 150)
    t.sleep(0.05)
    beep(0.2, 150)


def get_today_cutoff_utc():
    rome = pytz.timezone("Europe/Rome")
    local_midnight = rome.localize(datetime.combine(datetime.now(rome).date(), time.min))
    return local_midnight.astimezone(pytz.utc).isoformat().replace("+00:00", "Z")

def get_employee_by_uid(uid):
    url = f"{SUPABASE_URL}/rest/v1/{EMPLOYEES_TABLE}?uid=eq.{uid}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        return data[0] if data else None
    else:
        print(f"[ERROR] Failed to fetch employee: {response.text}")
        return None

def register_unknown_employee(uid):
    payload = {"uid": str(uid), "name": "Unknown"}
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{EMPLOYEES_TABLE}",
        headers=HEADERS,
        json=payload
    )
    if response.status_code in (200, 201):
        print(f"[INFO] Unknown employee with UID {uid} registered.")
        return payload
    else:
        print(f"[ERROR] Failed to register employee: {response.text}")
        return None

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

def send_event(user_id, action, door_id):
    payload = {
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "door_id": door_id
    }
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{ATTENDANCE_TABLE}",
        headers=HEADERS,
        json=payload
    )
    if response.status_code in (200, 201):
        if action == "check_in":
            print(f"\033[32m[OK] {action.replace('_', ' ').upper()} recorded.\033[0m")
            checkin_beep()
        else:
            print(f"\033[31m[OK] {action.replace('_', ' ').upper()} recorded.\033[0m")
            checkout_beep()
    else:
        print(f"[ERROR] Failed to write to Supabase: {response.text}")
        error_beep()

def main_loop():
    print("\033[1;36m**** TDK InvenCheck - NFC Listener ****\033[0m")
    online_beep()
    while True:
        print("\nWaiting for NFC tag...")
        try:
            uid, _ = reader.read()
            read_beep()
            print(f"Tag detected: UID {uid}")
            
            employee = get_employee_by_uid(uid)
            
            if not employee:
                employee = register_unknown_employee(uid)
                if not employee:
                    continue
            
            if employee['name']==("Unknown"):
                print("[INFO] Unknown user!")
                error_beep()
                continue

            user_id = employee["name"] if employee["name"] != "Unknown" else f"UID_{uid}"
            last_action = get_last_action_today(user_id)
            action = "check_out" if last_action == "check_in" else "check_in"

            print(f"Processing {action} for {user_id} at {DOOR_ID}")
            send_event(user_id, action, DOOR_ID)
            t.sleep(0.1)

        except Exception as e:
            print(f"[ERROR] {e}")
            error_beep()
            t.sleep(0.1)

if __name__ == "__main__":
    main_loop()
import os
import time
import requests
from datetime import datetime, time as dt_time
import pytz
from dotenv import load_dotenv

# === Load Configuration ===
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
ATTENDANCE_TABLE = "attendance"

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
}

# === Time Helper ===
def get_today_cutoff_utc():
    rome = pytz.timezone("Europe/Rome")
    local_midnight = rome.localize(datetime.combine(datetime.now(rome).date(), dt_time.min))
    return local_midnight.astimezone(pytz.utc).isoformat().replace("+00:00", "Z")

# === Query Function with Retry ===
def get_last_action_today(user_id):
    utc_cutoff = get_today_cutoff_utc()
    url = (
        f"{SUPABASE_URL}/rest/v1/{ATTENDANCE_TABLE}"
        f"?user_id=eq.{user_id}&timestamp=gte.{utc_cutoff}"
        f"&order=timestamp.desc&limit=1"
    )

    print(f"[INFO] Requesting last action for {user_id}")

    # First Attempt - short timeout
    start_time = time.time()
    try:
        response = requests.get(url, headers=HEADERS, timeout=(1, 1))
        elapsed = time.time() - start_time
        if response.status_code == 200:
            print(f"[OK] Response time: {elapsed:.3f}s | Records: {len(response.json())}")
        else:
            print(f"[ERROR] Status {response.status_code} in {elapsed:.3f}s | {response.text}")
        return response.json()[0]["action"] if response.json() else None
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[WARN] First attempt failed after {elapsed:.3f}s: {e}")

    # Second Attempt - no timeout
    print("[INFO] Retrying with no timeout...")
    start_time = time.time()
    try:
        response = requests.get(url, headers=HEADERS)
        elapsed = time.time() - start_time
        if response.status_code == 200:
            print(f"[OK] Retry response time: {elapsed:.3f}s | Records: {len(response.json())}")
        else:
            print(f"[ERROR] Retry status {response.status_code} in {elapsed:.3f}s | {response.text}")
        return response.json()[0]["action"] if response.json() else None
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[EXCEPTION] Retry failed after {elapsed:.3f}s: {e}")
        return None
    

# === Periodic Test ===
if __name__ == "__main__":
    TEST_USER_ID = "Milani Damiano"  
    INTERVAL = 2  # Seconds between requests

    while True:
        get_last_action_today(TEST_USER_ID)
        time.sleep(INTERVAL)

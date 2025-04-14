import requests
from datetime import datetime
import sys, os
from dotenv import load_dotenv

"""
Example

sudo python3 InvenCheck_cli.py "Milani Damiano" "Ingresso A10" 

# with small LCD screen
sudo python3 InvenCheck_cli.py "Milani Damiano" "Ingresso A10" | tee /dev/tty1

"""

# === Configuration ===
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
SUPABASE_TABLE = "attendance"

# === Inputs (change these or pass as arguments) ===
USER_ID = "Damiano Milani"
DOOR_ID = "Porta_1"

# === API Headers ===
HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def clear_screen():
    os.system('clear')

def clear_tty(tty="/dev/tty1"):
    with open(tty, "w") as f:
        f.write("\033c")

def get_last_action_today(user_id):
    today = datetime.utcnow().date().isoformat()
    url = (
        f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
        f"?user_id=eq.{user_id}&timestamp=gte.{today}T00:00:00.000Z"
        f"&order=timestamp.desc&limit=1"
    )
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        if data:
            return data[0]["action"]
        else:
            return None
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
        f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
        headers=HEADERS,
        json=payload
    )
    if response.status_code in (200, 201):
        print(f"\033[32m\n\n[OK] {action.replace('_', ' ').upper()} recorded.\n\033[0m")
    else:
        print(f"\n\n[ERROR] Failed to write to Supabase: {response.text}\n")

def main():
    global USER_ID, DOOR_ID

    # Optional CLI arguments
    if len(sys.argv) >= 2:
        USER_ID = sys.argv[1]
    if len(sys.argv) >= 3:
        DOOR_ID = sys.argv[2]

    # clear_screen()          # Clear SSH terminal
    # clear_tty("/dev/tty1")    # Clear LCD screen output

    print(f"\033[1;36m**** TDK InvenCheck ****\n\033[0m")

    print(f"Processing attendance... \n  Employee: {USER_ID} \n  Entrance: {DOOR_ID}")

    last_action = get_last_action_today(USER_ID)
    if last_action == "check_in":
        action = "check_out"
    else:
        action = "check_in"

    send_event(USER_ID, action, DOOR_ID)

if __name__ == "__main__":
    main()
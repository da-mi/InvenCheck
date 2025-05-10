import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import sys

# === Configuration ===
FIREBASE_CRED_PATH = "/home/dami/invencheck-68622-firebase-adminsdk-fbsvc-c82111751a.json" 
FIREBASE_COLLECTION = "attendance"

# === Inputs (default) ===
USER_ID = "Damiano Milani"
DOOR_ID = "Porta_1"

# === Initialize Firebase ===
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CRED_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def clear_tty(tty="/dev/tty1"):
    try:
        with open(tty, "w") as f:
            f.write("\033c")
    except Exception as e:
        print(f"[WARNING] Could not clear TTY screen: {e}")

def get_last_action_today(user_id):
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    docs = (
        db.collection(FIREBASE_COLLECTION)
        .where("user_id", "==", user_id)
        .where("date", "==", today_str)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    for doc in docs:
        return doc.to_dict().get("action")
    return None

def send_event(user_id, action, door_id):
    timestamp = datetime.utcnow()
    payload = {
        "user_id": user_id,
        "door_id": door_id,
        "timestamp": timestamp.isoformat(),
        "date": timestamp.strftime("%Y-%m-%d"),
        "action": action
    }
    try:
        db.collection(FIREBASE_COLLECTION).add(payload)
        print(f"\033[32m\n\n[OK] {action.replace('_', ' ').upper()} recorded.\n\033[0m")
    except Exception as e:
        print(f"\033[31m\n\n[ERROR] Failed to write to Firebase: {e}\n\033[0m")

def main():
    global USER_ID, DOOR_ID

    # Optional CLI args
    if len(sys.argv) >= 2:
        USER_ID = sys.argv[1]
    if len(sys.argv) >= 3:
        DOOR_ID = sys.argv[2]

    clear_tty("/dev/tty1")

    print(f"\033[1;36m**** TDK InvenCheck ****\n\033[0m")
    print(f"Processing attendance... \n  Employee: {USER_ID} \n  Entrance: {DOOR_ID}")

    last_action = get_last_action_today(USER_ID)
    action = "check_out" if last_action == "check_in" else "check_in"

    send_event(USER_ID, action, DOOR_ID)

if __name__ == "__main__":
    main()

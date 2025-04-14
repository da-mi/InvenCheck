
import tkinter as tk
import requests
import datetime
import os
from dotenv import load_dotenv

# Replace with your Supabase REST endpoint and API key


load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TABLE_NAME = "attendance"

# Global variables
user_id = "Damiano Milani"  # Replace with the actual user logic
door_id = "Porta_1"  # Door ID for the door (could be dynamic)


def send_event(action):
    """Send check-in or check-out data to Supabase"""
    data = {
        "user_id": user_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "action": action,
        "door_id": door_id
    }

    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}",
        json=data,
        headers=headers
    )

    if response.status_code == 201:
        print(f"{action.capitalize()} recorded.")
    else:
        print(f"Error: {response.status_code} - {response.text}")

def check_if_checked_in():
    """Check if the user has already checked in today"""
    today = datetime.datetime.now().date().isoformat()  # Get today's date (YYYY-MM-DD)

    # Query Supabase to check if a check-in exists today
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
    }

    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?user_id=eq.{user_id}&door_id=eq.{door_id}&action=eq.check_in&timestamp=like.{today}%",
        headers=headers
    )

    if response.status_code == 200:
        return len(response.json()) > 0
    else:
        print(f"Error fetching check-in data: {response.status_code}")
        return False

def update_button_label():
    """Update the button label based on check-in status"""
    if check_if_checked_in():
        button.config(text="Check Out", bg='red')
        status_label.config(text="User is currently checked in. Press to check out.")
    else:
        button.config(text="Check In", bg='green')
        status_label.config(text="User is not checked in. Press to check in.")

def on_button_click():
    """Handle button click (check-in or check-out)"""
    if check_if_checked_in():
        # If the user is checked in, check them out
        send_event("check_out")
        update_button_label()
    else:
        # If the user is not checked in, check them in
        send_event("check_in")
        update_button_label()

def build_gui():
    """Build the GUI for attendance check-in/out"""
    root = tk.Tk()
    root.title("InvenCheck")
    root.configure(bg='black')

    global status_label, button
    label = tk.Label(root, text="Tap to Check In or Out", font=('Arial', 20), bg='black', fg='white')
    label.pack(pady=40)

    # The action button (Check In / Check Out)
    button = tk.Button(root, text="Check In", font=('Arial', 18), bg='green', fg='white', width=20, height=3, command=on_button_click)
    button.pack(pady=10)

    # Status label showing if the user is checked in or out
    status_label = tk.Label(root, text="", font=('Arial', 14), bg='black', fg='white')
    status_label.pack(pady=20)

    update_button_label()  # Initialize button with proper label

    root.mainloop()

if __name__ == "__main__":
    build_gui()

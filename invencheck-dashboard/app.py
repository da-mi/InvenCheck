import streamlit as st
from supabase import create_client, Client
import pandas as pd
import pytz
from datetime import datetime

# --- Load Supabase credentials ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(url, key)

# --- Page setup ---
st.set_page_config(page_title="TDK InvenCheck - Attendance Tracker", 
                   page_icon="https://invensense.tdk.com/wp-content/themes/invensense//images/favicon/favicon-32x32.png", 
                   layout="centered",
                   menu_items={'About': "### TDK InvenCheck - DM 2025"})

st.markdown("""
    <style>
        .block-container {
            padding-top: 3rem;
        }
    </style>
    """, 
    unsafe_allow_html=True)

# --- Top bar with logo ---
st.markdown(
    """
    <div style="background-color:#0033a0;padding:0px 15px;display:flex;align-items:center">
        <img src="https://invensense.tdk.com/wp-content/themes/invensense/images/tdk-white-logo.svg" height="30" style="margin-right:10px"/>
        <h1 style="color:white;margin:0;font-size:1.4em">InvenCheck</h1>
    </div>
    <div style="margin-bottom:20px"></div>
    """,
    unsafe_allow_html=True
)


# --- Load data ---
@st.cache_data(ttl=60)
def load_device_status():
    response = supabase.table("devices").select("device_id, timestamp").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=["device_id", "timestamp", "status", "last_seen"])

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    now = datetime.now(pytz.UTC)
    df["status"] = df["timestamp"].apply(lambda x: "🟢 Online" if (now - x).total_seconds() < 1200 else "🔴 Offline")
    df["last_seen"] = df["timestamp"].dt.tz_convert("Europe/Rome").dt.strftime("%Y-%m-%d %H:%M")
    return df[["device_id", "status", "last_seen"]]

@st.cache_data(ttl=300)
def load_attendance():
    response = supabase.table("attendance").select("*").execute()
    df = pd.DataFrame(response.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Europe/Rome")
    return df.sort_values("timestamp", ascending=False)

df = load_attendance()

# --- Device panel ---
with st.expander("📡 Device Connection Status", expanded=False):
    device_df = load_device_status()
    if device_df.empty:
        st.warning("No device heartbeat data available.")
    else:
        st.dataframe(device_df.rename(columns={
            "device_id": "Device",
            "status": "Status",
            "last_seen": "Last Seen"
        }), hide_index=True, use_container_width=True)

# --- Prepare derived tables ---
today = datetime.now(pytz.timezone("Europe/Rome")).date()
df_today = df[df["timestamp"].dt.date == today]

# 1. Present employees today (last action is check_in, no later check_out)
present_employees = (
    df_today.sort_values("timestamp")
    .groupby("user_id")
    .last()
    .reset_index()
)
present_employees = present_employees[present_employees["action"] == "check_in"]
present_employees_display = present_employees[["user_id", "door_id", "timestamp", "action"]]
present_employees_display.columns = ["Employee", "Door", "Timestamp", "Action"]

# 2. Last entry per employee today
last_entries_today = (
    df_today.sort_values("timestamp")
    .groupby("user_id")
    .last()
    .reset_index()
)
last_entries_today_display = last_entries_today[["user_id", "door_id", "timestamp", "action"]]
last_entries_today_display.columns = ["Employee", "Door", "Timestamp", "Action"]

# 3. All data (already sorted)
display_df = df[["user_id", "door_id", "timestamp", "action"]]
display_df.columns = ["Employee", "Door", "Timestamp", "Action"]

# Format timestamp column to remove timezone info
for table in [present_employees_display, last_entries_today_display, display_df]:
    table["Timestamp"] = table["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")

# --- Counters and refresh ---
col1, col2, col3 = st.columns([2, 2, 1], vertical_alignment="center")
col1.metric("🟢 Employees In The Office", len(present_employees), border=True)
col2.metric("📅 Checked In Today", df_today[df_today["action"] == "check_in"]["user_id"].nunique(), border=True)

# --- Manual refresh button ---
with col3:
    if st.button("Refresh", icon=":material/refresh:", type="primary"):
        st.cache_data.clear()
        st.rerun()


# --- Tabs UI ---
tabs = st.tabs(["Currently in the Office", "Attendance Today", "All Entries"])

with tabs[0]:
    st.dataframe(present_employees_display, hide_index=True, use_container_width=True)

with tabs[1]:
    st.dataframe(last_entries_today_display, hide_index=True, use_container_width=True)

with tabs[2]:
    st.dataframe(display_df, use_container_width=True)

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
                   layout="wide",
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
    response = supabase.table("devices").select("device_id, timestamp, location").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=["device_id", "timestamp", "location", "status", "last_seen"])

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    now = datetime.now(pytz.UTC)
    df["status"] = df["timestamp"].apply(lambda x: "🟢 Online" if (now - x).total_seconds() < 1200 else "🔴 Offline")
    df["last_seen"] = df["timestamp"].dt.tz_convert("Europe/Rome").dt.strftime("%Y-%m-%d %H:%M")
    return df[["device_id", "location", "status", "last_seen"]]

@st.cache_data(ttl=300)
def load_attendance():
    response = supabase.table("attendance").select("*").execute()
    df = pd.DataFrame(response.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Europe/Rome")
    return df.sort_values("timestamp", ascending=False)

df = load_attendance()

# --- Sidebar: Device panel ---
st.sidebar.subheader("🛜 Device Connection")
device_df = load_device_status()
if device_df.empty:
    st.sidebar.warning("No device heartbeat data available.")
else:
    st.sidebar.dataframe(device_df.sort_values("device_id").rename(columns={
        "device_id": "Device",
        "location": "Location",
        "status": "Status",
        "last_seen": "Last seen"
    }), column_config={'Last seen':None}, hide_index=True, use_container_width=True)

# --- Present employees (always based on today) ---
today = datetime.now(pytz.timezone("Europe/Rome")).date()
df_today = df[df["timestamp"].dt.date == today]

present_employees = (
    df_today.sort_values("timestamp")
    .groupby("user_id")
    .last()
    .reset_index()
)
present_employees = present_employees[present_employees["action"] == "check_in"]
present_employees_display = present_employees[["user_id", "device_id", "timestamp"]]
present_employees_display.columns = ["Employee", "Door", "Last Check-in"]
present_employees_display["Last Check-in"] = present_employees_display["Last Check-in"].dt.strftime("%Y-%m-%d %H:%M")

# --- Counters and refresh ---
col1, col2, col3 = st.columns([2, 2, 1], vertical_alignment="center")
col1.metric("🙋🏻‍♂️🙋🏼‍♀️ Employees in the office", len(present_employees), border=True)
col2.metric("➜🏢 Checked-in today", df_today[df_today["action"] == "check_in"]["user_id"].nunique(), border=True)

with col3:
    if st.button("Refresh", icon=":material/refresh:", type="primary"):
        st.cache_data.clear()
        st.rerun()

# --- Tabs UI ---
tabs = st.tabs(["Currently in the office", "Attendance Record", "All entries"])

with tabs[0]:
    st.dataframe(present_employees_display, hide_index=True, use_container_width=True)

with tabs[1]:
    date_selected = st.date_input("📅 Select date to view attendance", today)
    df_filtered = df[df["timestamp"].dt.date == date_selected]

    # --- First check-in and last check-out per employee on selected day ---
    df_checkins = df_filtered[df_filtered["action"] == "check_in"].sort_values("timestamp")
    df_checkouts = df_filtered[df_filtered["action"] == "check_out"].sort_values("timestamp")

    first_checkins = df_checkins.groupby("user_id").first().reset_index()
    last_checkouts = df_checkouts.groupby("user_id").last().reset_index()

    attendance_summary = pd.merge(first_checkins[["user_id", "timestamp"]],
                                  last_checkouts[["user_id", "timestamp"]],
                                  on="user_id", how="outer", suffixes=("_in", "_out"))
    attendance_summary.columns = ["Employee", "First Check-in", "Last Check-out"]
    attendance_summary["First Check-in"] = attendance_summary["First Check-in"].dt.strftime("%Y-%m-%d %H:%M")
    attendance_summary["Last Check-out"] = attendance_summary["Last Check-out"].dt.strftime("%Y-%m-%d %H:%M")

    st.dataframe(attendance_summary, hide_index=True, use_container_width=True)

with tabs[2]:
    display_df = df[["user_id", "device_id", "timestamp", "action"]]
    display_df.columns = ["Employee", "Door", "Timestamp", "Action"]
    display_df["Timestamp"] = display_df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(display_df, use_container_width=True)

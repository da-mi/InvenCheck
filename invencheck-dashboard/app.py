"""
InvenCheck - WebApp interface
Streamlit interface to Supabase database.

Damiano Milani
2025
"""

import streamlit as st
from supabase import create_client, Client
import pandas as pd
import pytz
from datetime import datetime
from dateutil import parser

##### [PAGE SETTINGS]
st.set_page_config(
    page_title="TDK InvenCheck - Attendance Tracker",
    page_icon="https://invensense.tdk.com/wp-content/themes/invensense//images/favicon/favicon-32x32.png",
    layout="centered",
    menu_items={'About': "### TDK InvenCheck - DM 2025"}
)

st.markdown("""
    <style>
        .block-container {
            padding-top: 3rem;
        }
    </style>
    """, unsafe_allow_html=True)

##### [TOP BAR WITH LOGO]
st.markdown("""
    <div style="background-color:#0046ad;padding:0px 15px;display:flex;align-items:center;border-radius:0.35rem;">
        <img src="https://invensense.tdk.com/wp-content/themes/invensense/images/tdk-white-logo.svg" height="30" style="margin-right:10px"/>
        <h1 style="color:white;margin:0;font-size:1.4em">InvenCheck</h1>
    </div>
    <div style="margin-bottom:20px"></div>
    """, unsafe_allow_html=True)



##### [SUPABASE SETUP]
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

##### [DATA LOADING FUNCTIONS]
@st.cache_data(ttl=300)
def load_attendance():
    response = supabase.table("attendance").select("*").order("timestamp", desc=True).range(0, 499).execute()
    df = pd.DataFrame(response.data)
    # df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Europe/Rome") 
    #bug found on 2025/12/04, when the timestamp was recoreded exactly at .000000 second and microseconds were cut
    df['timestamp'] = df['timestamp'].astype(str).map(parser.parse).map(pd.Timestamp).dt.tz_convert("Europe/Rome")
    return df.sort_values("timestamp", ascending=False)

@st.cache_data(ttl=60)
def load_devices():
    response = supabase.table("devices").select("device_id, timestamp, location, ip").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=["device_id", "location", "ip", "status", "last_seen"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    now = datetime.now(pytz.UTC)
    df["status"] = df["timestamp"].apply(lambda x: "🟢 Online" if (now - x).total_seconds() < 1500 else "🔴 Offline")
    df["last_seen"] = df["timestamp"].dt.tz_convert("Europe/Rome").dt.strftime("%Y-%m-%d %H:%M")
    return df[["device_id", "location", "ip", "status", "last_seen"]]

@st.cache_data(ttl=300)
def load_users():
    response = supabase.table("users").select("uid, user_id, timestamp").execute()
    df = pd.DataFrame(response.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df



##### [SIDEBAR]
# --- Manual Check-in/Check-out ---
st.sidebar.header(":material/settings: Admin panel")
st.sidebar.divider()
st.sidebar.subheader(":material/table_edit: Manual Entry")
users_df = load_users().sort_values("user_id")
filtered_users = users_df[users_df["user_id"].str.lower() != "unknown"]
user_names = filtered_users["user_id"].tolist()
selected_user = st.sidebar.selectbox("Select Employee", user_names)
action = st.sidebar.radio("Action", ["Check-in", "Check-out"], horizontal=True)
submit = st.sidebar.button("Submit", icon=":material/send:", type="primary")

if submit:
    selected_id = filtered_users[filtered_users["user_id"] == selected_user]["user_id"].values[0]
    now = datetime.now(pytz.UTC)
    supabase.table("attendance").insert({
        "user_id": selected_id,
        "action": action.lower().replace('-', '_'),
        "timestamp": now.isoformat(),
        "device_id": "Manual"
    }).execute()
    st.sidebar.success(f"{action.replace('_', ' ').title()} recorded for {selected_user}")
    st.cache_data.clear()
    st.rerun()


# --- Assign new tag to user ---
st.sidebar.divider()
st.sidebar.subheader(":material/person_add: Assign new Tag")
now = datetime.now(pytz.UTC)
recent_unknowns = users_df[(users_df["user_id"].str.lower() == "unknown") & ((now - pd.to_datetime(users_df["timestamp"], utc=True)).dt.total_seconds() < 600)].copy()

if not recent_unknowns.empty:
    recent_unknowns["time_ago"] = (now - pd.to_datetime(recent_unknowns["timestamp"], utc=True)).apply(lambda x: f"{int(x.total_seconds() // 60)} min ago")
    unknown_options = [f"{row['uid']} ({row['time_ago']})" for _, row in recent_unknowns.iterrows()]
    selected_label = st.sidebar.selectbox("Select Unknown UID", unknown_options)
    selected_uid = selected_label.split(" ")[0]
    new_user_id = st.sidebar.text_input("Assign New User ID")
    assign = st.sidebar.button("Assign ID", icon=":material/nfc:", type="primary", disabled=False if new_user_id else True)

    if assign and new_user_id:
        supabase.table("users").update({"user_id": new_user_id}).eq("uid", selected_uid).execute()
        st.sidebar.success(f"Updated UID {selected_uid} with User ID '{new_user_id}'")
        st.cache_data.clear()
        st.rerun()
else:
    st.sidebar.selectbox("Select Unknown Tag UID (last 10min)", ["No recent unknown users"], disabled=True)
    st.sidebar.text_input("Assign New User Name to Tag UID", disabled=True)
    st.sidebar.button("Assign ID", icon=":material/nfc:", type="primary", disabled=True)

# --- Delete existing user ---
st.sidebar.divider()
st.sidebar.subheader(":material/person_remove: Remove Tag")
deletable_users = users_df[users_df["user_id"].str.lower() != "unknown"]["user_id"].unique().tolist()
user_to_delete = st.sidebar.selectbox("Select User ID to remove", deletable_users)

if "reset_confirm" not in st.session_state:
    st.session_state.reset_confirm = False
    st.session_state.confirm_delete = False
if st.session_state.reset_confirm:
    st.session_state.confirm_delete = False
    st.session_state.reset_confirm = False

confirm_delete = st.sidebar.checkbox(":material/warning: Confirm removal", key="confirm_delete")

delete = st.sidebar.button(":material/nfc_off: Remove ID", type="primary", disabled=not confirm_delete)
if delete:
    if st.session_state.get("confirm_delete", False):
        supabase.table("users").delete().eq("user_id", user_to_delete).execute()
        st.sidebar.success("User deleted")
        st.cache_data.clear()
        st.session_state.reset_confirm = True
        st.rerun()
    else:
        st.sidebar.warning("Please confirm deletion first.")

# --- Device status panel ---
st.sidebar.divider()
st.sidebar.subheader(":material/cloud_upload: Device Connection")
device_df = load_devices()
if device_df.empty:
    st.sidebar.warning("No device heartbeat data available.")
else:
    st.sidebar.dataframe(device_df.sort_values("device_id").rename(columns={
        "device_id": "Device",
        "location": "Location",
        "status": "Status",
        "ip": "IP",
        "last_seen": "Last seen"
    }), column_config={'Last seen': None, 'IP': None}, hide_index=True, width='stretch')



##### [MAIN VIEW]
# --- Present employees (always based on today) ---
df = load_attendance()
df["entrance"] = df["device_id"].apply(lambda x: "Manual" if x == "Manual" else 
                                       device_df[device_df["device_id"] == x]["location"].values[0] 
                                       if not device_df[device_df["device_id"] == x].empty else "Unknown")

today = datetime.now(pytz.timezone("Europe/Rome")).date()
df_today = df[df["timestamp"].dt.date == today]

present_employees = (
    df_today.sort_values("timestamp")
    .groupby("user_id")
    .last()
    .reset_index()
)
present_employees = present_employees[present_employees["action"] == "check_in"]
present_employees_display = present_employees[["user_id", "entrance", "timestamp"]].copy()
present_employees_display.columns = ["Employee", "Entrance", "Last Check-in"]
present_employees_display["Last Check-in"] = present_employees_display["Last Check-in"].dt.strftime("%Y-%m-%d %H:%M")

# --- Counters ---
col1, col2, col3 = st.columns([2, 2, 1], vertical_alignment="center")
col1.metric("🙋🏻‍♂️🙋🏼‍♀️ Employees in the office", len(present_employees), border=True)
col2.metric("➜🏢 Checked-in today", df_today[df_today["action"] == "check_in"]["user_id"].nunique(), border=True)

# --- Refresh button ---
with col3:
    if st.button("Refresh", icon=":material/refresh:", type="primary"):
        st.cache_data.clear()
        st.rerun()

# --- Tabs UI ---
tabs = st.tabs(["Currently in the office", "Attendance Record", "All entries"])

with tabs[0]:
    st.dataframe(present_employees_display, hide_index=True, width='stretch')

with tabs[1]:
    date_selected = st.date_input("📅 Select date to view attendance", today)
    df_filtered = df[df["timestamp"].dt.date == date_selected].copy()

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

    st.dataframe(attendance_summary, hide_index=True, width='stretch')

with tabs[2]:
    display_df = df[["user_id", "entrance", "timestamp", "action"]].copy()
    display_df.columns = ["Employee", "Entrance", "Timestamp", "Action"]
    display_df["Timestamp"] = display_df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(display_df, width='stretch', height=500)

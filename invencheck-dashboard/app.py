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
from datetime import datetime, timedelta
from dateutil import parser

##### [PAGE SETTINGS]
st.set_page_config(
    page_title="TDK InvenCheck - Attendance Tracker",
    page_icon="https://invensense.tdk.com/favicon.ico",
    layout="wide",
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
        <img src="https://invensense.tdk.com/web-app-manifest-512x512.png" height="30" style="margin-right:10px;border-radius:6px"/>
        <h1 style="color:white;margin:0;font-size:1.4em">InvenCheck</h1>
    </div>
    <div style="margin-bottom:20px"></div>
    """, unsafe_allow_html=True)

##### [LOCATION CONFIGURATION]
OFFICE_LOCATIONS = {"Ingresso A8", "Ingresso A10", "Backup"}
LABORATORY_LOCATIONS = {"Laboratorio", "BackupLab"}

def resolve_place(device_id, device_df):
    """Returns (entrance_label, place) for a given device_id."""
    if device_id == "Manual-Office":
        return "Manual", "Office"
    if device_id == "Manual-Laboratory":
        return "Manual", "Laboratory"
    if device_id == "Manual":
        return "Manual", "Office"
    if device_id == "Automatic":
        return "Automatic", "Unknown"
    matches = device_df[device_df["device_id"] == device_id]
    if matches.empty:
        return "Unknown", "Unknown"
    location = matches["location"].values[0]
    if location in OFFICE_LOCATIONS:
        return location, "Office"
    if location in LABORATORY_LOCATIONS:
        return location, "Laboratory"
    return location, "Unknown"

def normalize_attendance(df):
    """Insert virtual checkouts when a user checks in at a new location without checking out from the previous one."""
    if df.empty:
        return df
    extra_rows = []
    for _, events in df.groupby("user_id"):
        events = events.sort_values("timestamp")
        active_place = None
        active_row = None
        for _, row in events.iterrows():
            if row["action"] == "check_in":
                if active_place is not None and active_place != row["place"]:
                    virtual = active_row.copy()
                    virtual["action"] = "check_out"
                    virtual["timestamp"] = row["timestamp"]
                    virtual["device_id"] = "Automatic"
                    virtual["entrance"] = "Automatic"
                    extra_rows.append(virtual)
                active_place = row["place"]
                active_row = row
            elif row["action"] == "check_out" and row["place"] == active_place:
                active_place = None
                active_row = None
    if extra_rows:
        df = pd.concat([df, pd.DataFrame(extra_rows)], ignore_index=True).sort_values("timestamp", ascending=False)
    return df

##### [SUPABASE SETUP]
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

##### [DATA LOADING FUNCTIONS]
@st.cache_data(ttl=60)
def load_attendance_for_date(date):
    rome = pytz.timezone("Europe/Rome")
    start = rome.localize(datetime.combine(date, datetime.min.time())).astimezone(pytz.UTC)
    end = rome.localize(datetime.combine(date + timedelta(days=1), datetime.min.time())).astimezone(pytz.UTC)
    response = (supabase.table("attendance").select("*")
                .gte("timestamp", start.isoformat())
                .lt("timestamp", end.isoformat())
                .order("timestamp", desc=True)
                .execute())
    if not response.data:
        return pd.DataFrame(columns=["user_id", "device_id", "action", "timestamp"])
    df = pd.DataFrame(response.data)
    df['timestamp'] = df['timestamp'].astype(str).map(parser.parse).map(pd.Timestamp).dt.tz_convert("Europe/Rome")
    return df.sort_values("timestamp", ascending=False)

@st.cache_data(ttl=300)
def load_attendance(max_records=4000):
    # Fetch up to max_records records in chunks of 800
    all_data = []
    page_size = 800
    offset = 0
    while len(all_data) < max_records:
        response = supabase.table("attendance").select("*").order("timestamp", desc=True).range(offset, offset + page_size - 1).execute()
        if not response.data:
            break
        all_data.extend(response.data)
        if len(response.data) < page_size:
            break
        offset += page_size

    df = pd.DataFrame(all_data)
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

##### [LOGIN]
if "role" not in st.session_state:
    st.session_state.role = None

# Login disabled temporarily — uncomment this block and remove the line below to re-enable
# if st.session_state.role is None:
#     _, center, _ = st.columns([2, 1, 2])
#     with center:
#         st.markdown("#### Sign in")
#         password = st.text_input("Password", type="password")
#         if st.button("Login", type="primary", icon=":material/login:"):
#             if password == st.secrets["ADMIN_PASSWORD"]:
#                 st.session_state.role = "admin"
#                 st.rerun()
#             elif password == st.secrets["USER_PASSWORD"]:
#                 st.session_state.role = "user"
#                 st.rerun()
#             else:
#                 st.error("Incorrect password.")
#     st.stop()
st.session_state.role = "admin"

##### [LOGOUT BUTTON - sidebar for admin, main area for user]
def logout():
    st.session_state.role = None

##### [SHARED DATA]
today = datetime.now(pytz.timezone("Europe/Rome")).date()
device_df = load_devices()
df_today = load_attendance_for_date(today)
df_today["entrance"] = df_today["device_id"].apply(lambda x: resolve_place(x, device_df)[0])
df_today["place"] = df_today["device_id"].apply(lambda x: resolve_place(x, device_df)[1])
df_today = normalize_attendance(df_today)

def get_present_in_place(df_day, place):
    df_place = df_day[df_day["place"] == place]
    if df_place.empty:
        return pd.DataFrame(columns=["user_id", "entrance", "timestamp", "action"])
    present = (
        df_place.sort_values("timestamp")
        .groupby("user_id")
        .last()
        .reset_index()
    )
    return present[present["action"] == "check_in"]

present_office = get_present_in_place(df_today, "Office")
present_lab = get_present_in_place(df_today, "Laboratory")

##### [SHARED COMPONENTS]
def render_counters_and_refresh():
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1], vertical_alignment="center")
    col1.metric("🏢 Currently in the Office", len(present_office), border=True)
    col2.metric("🔬 Currently in the Laboratory", len(present_lab), border=True)
    col3.metric("➜ Total checked-in today", df_today[df_today["action"] == "check_in"]["user_id"].nunique(), border=True)
    with col4:
        if st.button("Refresh", icon=":material/refresh:", type="primary"):
            st.cache_data.clear()
            st.rerun()

def render_present_tables():
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🏢 Office**")
        if not present_office.empty:
            office_display = present_office[["user_id", "entrance", "timestamp"]].copy()
            office_display.columns = ["Employee", "Entrance", "Last Check-in"]
            office_display["Last Check-in"] = office_display["Last Check-in"].dt.strftime("%H:%M")
            st.dataframe(office_display, hide_index=True, width='stretch')
        else:
            st.info("Nobody in the Office")
    with c2:
        st.markdown("**🔬 Laboratory**")
        if not present_lab.empty:
            lab_display = present_lab[["user_id", "entrance", "timestamp"]].copy()
            lab_display.columns = ["Employee", "Entrance", "Last Check-in"]
            lab_display["Last Check-in"] = lab_display["Last Check-in"].dt.strftime("%H:%M")
            st.dataframe(lab_display, hide_index=True, width='stretch')
        else:
            st.info("Nobody in the Laboratory")

##### [USER VIEW]
if st.session_state.role == "user":
    render_counters_and_refresh()
    st.divider()
    render_present_tables()
    st.sidebar.button("Logout", icon=":material/logout:", on_click=logout)
    st.stop()

##### [ADMIN VIEW]
# --- Sidebar ---
st.sidebar.header(":material/settings: Admin panel")
st.sidebar.divider()
st.sidebar.subheader(":material/table_edit: Manual Entry")
users_df = load_users().sort_values("user_id")
filtered_users = users_df[users_df["user_id"].str.lower() != "unknown"]
user_names = filtered_users["user_id"].tolist()
selected_user = st.sidebar.selectbox("Select Employee", user_names)
action = st.sidebar.radio("Action", ["Check-in", "Check-out"], horizontal=True)
manual_location = st.sidebar.radio("Location", ["Office", "Laboratory"], horizontal=True)
submit = st.sidebar.button("Submit", icon=":material/send:", type="primary")

if submit:
    selected_id = filtered_users[filtered_users["user_id"] == selected_user]["user_id"].values[0]
    now = datetime.now(pytz.UTC)
    supabase.table("attendance").insert({
        "user_id": selected_id,
        "action": action.lower().replace('-', '_'),
        "timestamp": now.isoformat(),
        "device_id": f"Manual-{manual_location}"
    }).execute()
    st.sidebar.success(f"{action.replace('_', ' ').title()} recorded for {selected_user} ({manual_location})")
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

# --- Logout ---
st.sidebar.divider()
st.sidebar.button("Logout", icon=":material/logout:", on_click=logout)

# --- Main view ---
render_counters_and_refresh()

tabs = st.tabs(["Currently present", "Attendance Record", "All entries"])

with tabs[0]:
    render_present_tables()

with tabs[1]:
    date_selected = st.date_input("📅 Select date to view attendance", today)

    df_filtered = load_attendance_for_date(date_selected)
    if not df_filtered.empty:
        df_filtered["entrance"] = df_filtered["device_id"].apply(lambda x: resolve_place(x, device_df)[0])
        df_filtered["place"] = df_filtered["device_id"].apply(lambda x: resolve_place(x, device_df)[1])
        df_filtered = normalize_attendance(df_filtered)

    def build_attendance_summary(df_filtered, place):
        df_place = df_filtered[df_filtered["place"] == place]
        df_checkins = df_place[df_place["action"] == "check_in"].sort_values("timestamp")
        df_checkouts = df_place[df_place["action"] == "check_out"].sort_values("timestamp")
        first_checkins = (df_checkins.groupby("user_id").first().reset_index()
                          if not df_checkins.empty
                          else pd.DataFrame(columns=["user_id", "timestamp"]))
        last_checkouts = (df_checkouts.groupby("user_id").last().reset_index()
                          if not df_checkouts.empty
                          else pd.DataFrame(columns=["user_id", "timestamp"]))
        if first_checkins.empty and last_checkouts.empty:
            return None
        summary = pd.merge(
            first_checkins[["user_id", "timestamp"]],
            last_checkouts[["user_id", "timestamp"]],
            on="user_id", how="outer", suffixes=("_in", "_out")
        )
        summary.columns = ["Employee", "First Check-in", "Last Check-out"]
        summary["First Check-in"] = summary["First Check-in"].apply(
            lambda x: x.strftime("%H:%M") if pd.notna(x) else "-"
        )
        summary["Last Check-out"] = summary["Last Check-out"].apply(
            lambda x: x.strftime("%H:%M") if pd.notna(x) else "-"
        )
        return summary

    tc1, tc2 = st.columns(2)
    with tc1:
        summary = build_attendance_summary(df_filtered, "Office")
        count = len(summary) if summary is not None else 0
        st.markdown(f"**🏢 Office — {count} {'person' if count == 1 else 'people'}**")
        if summary is not None:
            st.dataframe(summary, hide_index=True, width='stretch')
        else:
            st.info("No data for Office on this date.")
    with tc2:
        summary = build_attendance_summary(df_filtered, "Laboratory")
        count = len(summary) if summary is not None else 0
        st.markdown(f"**🔬 Laboratory — {count} {'person' if count == 1 else 'people'}**")
        if summary is not None:
            st.dataframe(summary, hide_index=True, width='stretch')
        else:
            st.info("No data for Laboratory on this date.")

with tabs[2]:
    if "load_all_entries" not in st.session_state:
        st.session_state.load_all_entries = False

    if not st.session_state.load_all_entries:
        st.info("Showing last 800 entries.")
        if st.button("Load all entries", icon=":material/download:"):
            st.session_state.load_all_entries = True
            st.rerun()
        source_df = load_attendance(max_records=800)
    else:
        source_df = load_attendance(max_records=4000)

    source_df = source_df.copy()
    source_df["entrance"] = source_df["device_id"].apply(lambda x: resolve_place(x, device_df)[0])
    source_df["place"] = source_df["device_id"].apply(lambda x: resolve_place(x, device_df)[1])
    source_df = normalize_attendance(source_df)
    display_df = source_df[["user_id", "place", "entrance", "timestamp", "action"]].copy()
    display_df.columns = ["Employee", "Place", "Entrance", "Timestamp", "Action"]
    display_df["Timestamp"] = display_df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(display_df, width='stretch', height=500)

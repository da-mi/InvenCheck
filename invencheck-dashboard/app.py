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
st.set_page_config(page_title="InvenCheck Attendance Tracker", layout="wide")

# --- Top bar with logo ---
st.markdown(
    """
    <div style="background-color:#0033a0;padding:5px 15px;display:flex;align-items:center">
        <img src="https://invensense.tdk.com/wp-content/themes/invensense/images/tdk-white-logo.svg" height="30" style="margin-right:10px"/>
        <h1 style="color:white;margin:0;font-size:1.4em">InvenCheck</h1>
    </div>
    <div style="margin-bottom:20px"></div>
    """,
    unsafe_allow_html=True
)

# --- Load data ---
@st.cache_data(ttl=300)
def load_attendance():
    response = supabase.table("attendance").select("*").execute()
    df = pd.DataFrame(response.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Europe/Rome")
    return df.sort_values("timestamp", ascending=False)



df = load_attendance()

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
col1, col2, col3 = st.columns([2, 2, 1])
col1.metric("🟢 Employees In The Office", len(present_employees))
col2.metric("📅 Checked In Today", df_today[df_today["action"] == "check_in"]["user_id"].nunique())

# --- Manual refresh button ---
with col3:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()


# --- Tabs UI ---
tabs = st.tabs(["Currently in the Office", "Attendance Today", "All Entries"])

with tabs[0]:
    st.dataframe(present_employees_display, use_container_width=True)

with tabs[1]:
    st.dataframe(last_entries_today_display, use_container_width=True)

with tabs[2]:
    st.dataframe(display_df, use_container_width=True)
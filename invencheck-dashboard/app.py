import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- Load Supabase credentials ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- Page setup ---
st.set_page_config(page_title="InvenCheck Attendance Tracker", layout="wide")
st.title("👨‍💼 InvenCheck: Office Attendance Tracker")

# --- Load data ---
@st.cache_data(ttl=300)
def load_attendance():
    response = supabase.table("attendance").select("*").execute()
    df = pd.DataFrame(response.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values("timestamp", ascending=False)

df = load_attendance()

# --- Filter UI ---
with st.sidebar:
    user_filter = st.multiselect("Filter by User", options=df["user_id"].unique())
    door_filter = st.multiselect("Filter by Door", options=df["door_id"].unique())
    action_filter = st.multiselect("Filter by Action", options=["check_in", "check_out"])
    only_today = st.checkbox("Show only today's records", value=True)

# --- Filter Logic ---
if user_filter:
    df = df[df["user_id"].isin(user_filter)]
if door_filter:
    df = df[df["door_id"].isin(door_filter)]
if action_filter:
    df = df[df["action"].isin(action_filter)]
if only_today:
    df = df[df["timestamp"].dt.date == pd.Timestamp.today().date()]

# --- Display table ---
st.dataframe(df, use_container_width=True)

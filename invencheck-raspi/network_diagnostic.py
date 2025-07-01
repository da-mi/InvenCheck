#!/usr/bin/env python3
import subprocess
import socket
import time
import os
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

# === Load Config ===
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
parsed_url = urlparse(SUPABASE_URL)
SUPABASE_HOST = parsed_url.hostname
THRESHOLD = 2.0  # seconds

# === Helper Functions ===
def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, timeout=5).decode().strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return str(e)

def check_wifi_status():
    ssid = run_cmd("iwgetid -r")
    ip = run_cmd("hostname -I")
    return ssid or "NO SSID", ip.split()[0] if ip else "NO IP"

def timed_ping(host):
    if not host:
        return False, None
    start = time.time()
    try:
        subprocess.check_call(["ping", "-c", "2", "-W", "2", host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elapsed = time.time() - start
        return True, round(elapsed, 3)
    except subprocess.CalledProcessError:
        elapsed = time.time() - start
        return False, round(elapsed, 3)

def timed_dns_resolve(hostname="google.com"):
    start = time.time()
    try:
        socket.gethostbyname(hostname)
        elapsed = time.time() - start
        return True, round(elapsed, 3)
    except socket.gaierror:
        elapsed = time.time() - start
        return False, round(elapsed, 3)

def get_default_gateway():
    out = run_cmd("ip route | grep default")
    if out.startswith("default"):
        return out.split()[2]
    return None

def format_time(t):
    """Format time with highlight if above threshold."""
    if t is None:
        return "  N/A "
    marker = " !!" if t > THRESHOLD else "    "
    return f"{t:5.3f}s{marker}"

# === Full Report ===
def full_report():
    print(f"\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔍 Full Network Diagnostic\n")

    ssid, ip = check_wifi_status()
    print(f"📶 SSID: {ssid}")
    print(f"🌐 IP: {ip}")

    gateway = get_default_gateway()
    print(f"🚪 Gateway: {gateway or 'Not found'}")

    gw_ok, gw_time = timed_ping(gateway) if gateway else (False, None)
    dns_ok, dns_time = timed_dns_resolve()
    ext_ok, ext_time = timed_ping("8.8.8.8")
    web_ok, web_time = timed_ping("google.com")
    supabase_ok, supa_time = timed_ping(SUPABASE_HOST)

    print(f"\n{'GW':<8}{'DNS':<10}{'8.8.8.8':<10}{'Web':<10}{'Supabase':<12}Status")
    print(f"{format_time(gw_time):<8}{format_time(dns_time):<10}{format_time(ext_time):<10}{format_time(web_time):<10}{format_time(supa_time):<12}", end="")

    all_ok = (
        ssid != "NO SSID"
        and ip != "NO IP"
        and gw_ok
        and dns_ok
        and ext_ok
        and web_ok
        and supabase_ok
    )

    if all_ok:
        print("✅ All OK")
    else:
        print("⚠️ Issue Detected")
        if ssid == "NO SSID":
            print("❌ Not connected to any Wi-Fi.")
        elif ip == "NO IP":
            print("❌ No IP assigned — check DHCP.")
        elif not gw_ok:
            print("❌ Cannot reach gateway — local Wi-Fi issue.")
        elif not dns_ok:
            print("❌ DNS failure — try using 8.8.8.8 as nameserver.")
        elif not ext_ok:
            print("❌ No internet access — check router uplink.")
        elif not web_ok:
            print("❌ Cannot reach websites — possible DNS/filter issue.")
        elif not supabase_ok:
            print(f"❌ Cannot reach Supabase at {SUPABASE_HOST} — check Supabase status or your network.")

# === Minimal Check ===
def minimal_check():
    ssid, ip = check_wifi_status()
    gateway = get_default_gateway()
    gw_ok, gw_time = timed_ping(gateway) if gateway else (False, None)
    dns_ok, dns_time = timed_dns_resolve()
    ext_ok, ext_time = timed_ping("8.8.8.8")
    web_ok, web_time = timed_ping("google.com")
    supabase_ok, supa_time = timed_ping(SUPABASE_HOST)

    all_ok = (
        ssid != "NO SSID"
        and ip != "NO IP"
        and gw_ok
        and dns_ok
        and ext_ok
        and web_ok
        and supabase_ok
    )

    print(f"\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'GW':<8}{'DNS':<10}{'8.8.8.8':<10}{'Web':<10}{'Supabase':<12}Status")
    
    print(f"{format_time(gw_time):<8}{format_time(dns_time):<10}{format_time(ext_time):<10}{format_time(web_time):<10}{format_time(supa_time):<12}", end="")

    if all_ok:
        print("✅ All OK")
    else:
        print("⚠️ Issue Detected")
        if ssid == "NO SSID":
            print("❌ Not connected to any Wi-Fi.")
        elif ip == "NO IP":
            print("❌ No IP assigned — check DHCP.")
        elif not gw_ok:
            print("❌ Cannot reach gateway — local Wi-Fi issue.")
        elif not dns_ok:
            print("❌ DNS failure — try using 8.8.8.8 as nameserver.")
        elif not ext_ok:
            print("❌ No internet access — check router uplink.")
        elif not web_ok:
            print("❌ Cannot reach websites — possible DNS/filter issue.")
        elif not supabase_ok:
            print(f"❌ Cannot reach Supabase at {SUPABASE_HOST} — check Supabase status or your network.")

# === Main Loop ===
if __name__ == "__main__":
    full_report()
    while True:
        minimal_check()
        time.sleep(5)

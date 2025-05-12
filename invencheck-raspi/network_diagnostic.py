#!/usr/bin/env python3
import subprocess
import socket
import time
from datetime import datetime

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

def ping_host(host):
    try:
        subprocess.check_call(["ping", "-c", "2", "-W", "2", host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def resolve_dns(hostname="google.com"):
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False

def get_default_gateway():
    out = run_cmd("ip route | grep default")
    if out.startswith("default"):
        return out.split()[2]
    return None

def full_report():
    print(f"\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔍 Full Network Diagnostic\n")

    ssid, ip = check_wifi_status()
    print(f"📶 SSID: {ssid}")
    print(f"🌐 IP: {ip}")

    gateway = get_default_gateway()
    print(f"🚪 Gateway: {gateway or 'Not found'}")

    gw_ok = ping_host(gateway) if gateway else False
    print(f"📡 Ping Gateway: {'OK' if gw_ok else 'FAILED'}")

    dns_ok = resolve_dns()
    print(f"🧭 DNS Resolve: {'OK' if dns_ok else 'FAILED'}")

    ext_ok = ping_host("8.8.8.8")
    print(f"🌍 Ping 8.8.8.8: {'OK' if ext_ok else 'FAILED'}")

    web_ok = ping_host("google.com")
    print(f"🕸️ Ping google.com: {'OK' if web_ok else 'FAILED'}")

    print("\n📋 Diagnosis:")
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
    else:
        print("✅ Internet looks OK.")

def minimal_check():
    ssid, ip = check_wifi_status()
    gateway = get_default_gateway()
    gw_ok = ping_host(gateway) if gateway else False
    dns_ok = resolve_dns()
    ext_ok = ping_host("8.8.8.8")
    web_ok = ping_host("google.com")

    if ssid == "NO SSID" or ip == "NO IP" or not gw_ok or not dns_ok or not ext_ok or not web_ok:
        print(f"\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — Network Issue Detected")
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

if __name__ == "__main__":
    full_report()  # Show all info once at start
    while True:
        minimal_check()
        time.sleep(5)

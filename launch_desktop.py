"""
BTC 15M Kalshi AI Trader & Pattern Analyzer - Smart Desktop Launcher
- Single-instance detection (prevents port 8056 conflicts)
- Health check polling before opening browser
- Supports LAN and local access
"""

import os
import sys
import time
import urllib.request
import webbrowser
import threading

PORT = 8056
LOCAL_URL = f"http://localhost:{PORT}"
HEALTH_URL = f"http://localhost:{PORT}/api/health"
APP_DIR = os.path.dirname(os.path.abspath(__file__))

def is_server_running() -> bool:
    try:
        req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "Desktop-Launcher"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False

def open_browser():
    # Wait for server to start responding
    for _ in range(30):
        time.sleep(0.5)
        if is_server_running():
            break
    webbrowser.open(LOCAL_URL)

def main():
    print("=" * 68)
    print("     BTC 15M CONFLUENCE & KALSHI AI TRADER // DESKTOP LAUNCHER")
    print("=" * 68)

    if is_server_running():
        print(f"\n[+] Server is already active on port {PORT}!")
        print(f"[+] Opening dashboard in browser: {LOCAL_URL}")
        webbrowser.open(LOCAL_URL)
        print("[+] Done.")
        time.sleep(1.5)
        return

    print(f"\n[+] Starting server on port {PORT}...")
    print(f"[+] Browser will launch automatically once server is live at {LOCAL_URL}")
    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    sys.path.insert(0, APP_DIR)
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, reload=True, app_dir=APP_DIR)

if __name__ == "__main__":
    main()

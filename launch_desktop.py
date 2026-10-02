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
import ssl

import secrets

PORT = 8058
BIND_HOST = "0.0.0.0"
APP_DIR = os.path.dirname(os.path.abspath(__file__))

USE_SSL = os.path.exists(os.path.join(APP_DIR, "key.pem")) and os.path.exists(os.path.join(APP_DIR, "cert.pem"))
SCHEME = "https" if USE_SSL else "http"
HEALTH_URL = f"{SCHEME}://127.0.0.1:{PORT}/api/health"

# Check if optional APP_API_TOKEN is defined
ACTIVE_TOKEN = os.environ.get("APP_API_TOKEN", "").strip()
if not ACTIVE_TOKEN:
    token_file = os.path.join(APP_DIR, ".local_token")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as tf:
                ACTIVE_TOKEN = tf.read().strip()
        except Exception:
            pass

LOCAL_URL = f"{SCHEME}://localhost:{PORT}/?token={ACTIVE_TOKEN}" if ACTIVE_TOKEN else f"{SCHEME}://localhost:{PORT}/"

def is_server_running() -> bool:
    try:
        ctx = ssl._create_unverified_context() if USE_SSL else None
        req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "Desktop-Launcher"})
        with urllib.request.urlopen(req, timeout=1.5, context=ctx) as resp:
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
        if "--no-browser" in sys.argv:
            # Started by the watchdog while another copy is serving: wait before handing
            # back, so the watchdog doesn't spin in a fast restart loop.
            time.sleep(60)
            return
        print(f"[+] Opening dashboard in browser: {SCHEME}://localhost:{PORT}/")
        webbrowser.open(LOCAL_URL)
        print("[+] Done.")
        time.sleep(1.5)
        return

    no_browser = "--no-browser" in sys.argv
    print(f"\n[+] Starting server on {BIND_HOST}:{PORT} ({SCHEME.upper()})...")
    if not no_browser:
        print(f"[+] Browser will launch automatically at {SCHEME}://localhost:{PORT}/")
        threading.Thread(target=open_browser, daemon=True).start()

    import subprocess
    venv_python = os.path.join(APP_DIR, ".venv", "Scripts", "python.exe")
    cmd = [
        venv_python, "-m", "uvicorn", "backend.main:app",
        "--host", BIND_HOST,
        "--port", str(PORT),
        "--no-access-log"
    ]
    if os.path.exists(os.path.join(APP_DIR, "key.pem")) and os.path.exists(os.path.join(APP_DIR, "cert.pem")):
        cmd.extend([
            "--ssl-keyfile", os.path.join(APP_DIR, "key.pem"),
            "--ssl-certfile", os.path.join(APP_DIR, "cert.pem")
        ])
    # Launch the background worker (places and settles trades) and restart it if it
    # ever exits while the web server is running. worker.py refuses to run twice, so a
    # duplicate simply exits and is retried later.
    worker_cmd = [venv_python, "backend/worker.py"]
    stop_event = threading.Event()
    worker_state = {"proc": None}

    def supervise_worker():
        delay = 5.0
        while not stop_event.is_set():
            started = time.time()
            proc = subprocess.Popen(worker_cmd, cwd=APP_DIR)
            worker_state["proc"] = proc
            while proc.poll() is None and not stop_event.is_set():
                time.sleep(1.0)
            if stop_event.is_set():
                break
            delay = 5.0 if time.time() - started > 60 else min(delay * 2, 120.0)
            print(f"[!] Worker exited with code {proc.returncode}; restarting in {delay:.0f}s")
            stop_event.wait(delay)

    threading.Thread(target=supervise_worker, daemon=True, name="WorkerSupervisor").start()

    # Launch uvicorn
    try:
        subprocess.run(cmd, cwd=APP_DIR)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        proc = worker_state["proc"]
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

if __name__ == "__main__":
    main()

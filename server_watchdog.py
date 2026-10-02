"""
BTC 15M Kalshi AI Trader - Auto-Restarting Watchdog Supervisor
Monitors the FastAPI / Uvicorn server process and automatically restarts it
with backoff if it ever crashes, exits, or fails.
"""

import os
import sys
import time
import subprocess
import logging
from logging.handlers import RotatingFileHandler

APP_DIR = os.environ.get("APP_DIR", os.path.dirname(os.path.abspath(__file__)))
venv_python = os.path.join(APP_DIR, ".venv", "Scripts", "python.exe")
if os.path.exists(venv_python):
    PYTHON_EXE = venv_python
elif sys.executable.lower().endswith("pythonw.exe"):
    cand = sys.executable[:-9] + "python.exe"
    PYTHON_EXE = cand if os.path.exists(cand) else sys.executable
else:
    PYTHON_EXE = sys.executable

LOG_FILE = os.path.join(APP_DIR, "server_watchdog.log")

# Rotating log handler keeps file under 5 MB to eliminate disk I/O bottlenecks
log_handlers = [RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")]
if sys.stdout is not None:
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers
)
logger = logging.getLogger("Watchdog")

def run_server():
    cmd = [
        PYTHON_EXE,
        "launch_desktop.py",
        "--no-browser"
    ]
    
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    logger.info("Starting BTC 15M Server process: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=flags,
        close_fds=True
    )
    return proc

NGROK_DOMAIN = os.environ.get("NGROK_DOMAIN", "moneyprinter.ngrok.app")
APP_PORT = 8058  # keep in sync with PORT in launch_desktop.py


import psutil

def _ngrok_processes():
    """(pid, command line) of ngrok processes serving this app's domain."""
    procs = []
    try:
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            if p.info['name'] == 'ngrok.exe':
                cmdline = ' '.join(p.info['cmdline'] or [])
                if NGROK_DOMAIN in cmdline:
                    procs.append((p.info['pid'], cmdline))
    except Exception as e:
        logger.warning(f"Error checking ngrok processes with psutil: {e}")
    return procs


def _ngrok_running() -> bool:
    """True if this app's tunnel is up AND points at the current port. A tunnel left
    over from before a port change is stopped so a correct one can start."""
    ok = False
    for pid, cmdline in _ngrok_processes():
        if f" {APP_PORT} " in f" {cmdline} ":
            ok = True
        else:
            logger.warning("[Watchdog] ngrok (pid %s) points at the wrong port; stopping it: %s", pid, cmdline)
            subprocess.call(["taskkill", "/F", "/PID", str(pid)],
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000))
    return ok


def ensure_ngrok():
    """Start the ngrok tunnel if it is not running (the authtoken comes from ngrok's own config)."""
    try:
        if _ngrok_running():
            return
        logger.info("[Watchdog] Starting ngrok tunnel %s -> port %s...", NGROK_DOMAIN, APP_PORT)
        subprocess.Popen(
            ["ngrok", "http", str(APP_PORT), f"--url={NGROK_DOMAIN}"],
            cwd=APP_DIR,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            close_fds=True
        )
    except Exception as e:
        logger.warning("[Watchdog] Could not start ngrok tunnel: %s", e)


def _ngrok_monitor():
    while True:
        ensure_ngrok()
        time.sleep(60)


def _acquire_watchdog_lock():
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "KalshiAITraderWatchdogLock")
    if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        return None
    return mutex

def main():
    lock_socket = _acquire_watchdog_lock()
    if lock_socket is None:
        logger.info("[Watchdog] Another server_watchdog instance is already active. Exiting duplicate process cleanly.")
        return

    logger.info("==================================================")
    logger.info("  BTC 15M WATCHDOG SUPERVISOR INITIATED")
    logger.info("  Auto-Reboot on Crash Enabled")
    logger.info("==================================================")

    # Keep the ngrok tunnel up: checked now and every 60 s (restarted if it died)
    import threading
    threading.Thread(target=_ngrok_monitor, daemon=True, name="NgrokMonitor").start()

    restart_count = 0

    while True:
        start_time = time.time()
        try:
            proc = run_server()
            
            for line in proc.stdout:
                line_str = line.strip()
                if line_str:
                    logger.info("[Server] %s", line_str)

            proc.wait()
            exit_code = proc.returncode
            uptime = round(time.time() - start_time, 1)

            logger.warning(
                f"[Watchdog] Server process terminated with exit code {exit_code} (Uptime: {uptime}s)."
            )

            if uptime > 60:
                restart_count = 0

            restart_count += 1
            backoff_delay = min(2.0 * (1.5 ** (min(restart_count, 15) - 1)), 60.0)
            logger.info(f"[Watchdog] Automatically restarting server in {backoff_delay:.1f} seconds... (Attempt #{restart_count})")
            time.sleep(backoff_delay)

        except Exception as e:
            logger.error(f"[Watchdog] Supervisor error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()

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
        "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8056",
        "--app-dir", APP_DIR,
        "--no-access-log"
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

    # Start Cloudflare Remote Tunnel in background
    try:
        from remote_tunnel import start_tunnel_in_background
        start_tunnel_in_background()
        logger.info("[Watchdog] Cloudflare Remote Access tunnel initiated.")
    except Exception as e:
        logger.warning("[Watchdog] Could not start remote tunnel: %s", e)

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

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

APP_DIR = os.environ.get("APP_DIR", os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXE = sys.executable
LOG_FILE = os.path.join(APP_DIR, "server_watchdog.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Watchdog")

def run_server():
    cmd = [
        PYTHON_EXE,
        "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8056",
        "--app-dir", APP_DIR
    ]
    
    logger.info("Starting BTC 15M Server process: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    return proc

def main():
    logger.info("==================================================")
    logger.info("  BTC 15M WATCHDOG SUPERVISOR INITIATED")
    logger.info("  Auto-Reboot on Crash Enabled")
    logger.info("==================================================")

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
            logger.info(f"[Watchdog] Automatically restarting server in 2 seconds... (Restart #{restart_count})")
            time.sleep(2)

        except Exception as e:
            logger.error(f"[Watchdog] Supervisor error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()

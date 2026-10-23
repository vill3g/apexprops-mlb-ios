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
logging.raiseExceptions = False
logger = logging.getLogger("Watchdog")


def run_sports_bridge():
    bridge_dir = os.path.abspath(os.path.join(APP_DIR, '..', '..', '.gemini', 'antigravity', 'scratch', 'apexprops-mlb-ios'))
    if not os.path.exists(bridge_dir):
        logger.warning(f"[Watchdog] Sports bridge directory not found: {bridge_dir}")
        return None

    cmd = [
        PYTHON_EXE,
        "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8057"
    ]
    
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    sub_env = os.environ.copy()
    sub_env["PYTHONIOENCODING"] = "utf-8"
    sub_env["PYTHONUTF8"] = "1"

    logger.info("Starting Sports Bridge Server process: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=bridge_dir,
        env=sub_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=flags,
        close_fds=True
    )
    return proc

def _sports_bridge_monitor():
    restart_count = 0
    while True:
        start_time = time.time()
        try:
            proc = run_sports_bridge()
            if not proc:
                logger.error("[Watchdog] Failed to start sports bridge. Retrying in 60s...")
                time.sleep(60)
                continue
                
            try:
                while True:
                    line = proc.stdout.readline()
                    if line:
                        line_str = line.strip()
                        if line_str:
                            logger.info("[SportsBridge] %s", line_str)
                    elif proc.poll() is not None:
                        break
                    else:
                        time.sleep(0.02)
            except Exception as stream_err:
                logger.debug(f"[Watchdog] SportsBridge stream error: {stream_err}")

            proc.wait()
            exit_code = proc.returncode
            uptime = round(time.time() - start_time, 1)

            logger.warning(
                f"[Watchdog] Sports bridge terminated with exit code {exit_code} (Uptime: {uptime}s)."
            )

            if uptime > 60:
                restart_count = 0

            restart_count += 1
            backoff_delay = min(2.0 * (1.5 ** (min(restart_count, 15) - 1)), 60.0)
            logger.info(f"[Watchdog] Automatically restarting sports bridge in {backoff_delay:.1f} seconds... (Attempt #{restart_count})")
            time.sleep(backoff_delay)

        except Exception as e:
            logger.error(f"[Watchdog] Sports bridge supervisor error: {e}")
            time.sleep(3)

def run_server():
    cmd = [
        PYTHON_EXE,
        "launch_desktop.py",
        "--no-browser"
    ]
    
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    sub_env = os.environ.copy()
    sub_env["PYTHONIOENCODING"] = "utf-8"
    sub_env["PYTHONUTF8"] = "1"

    logger.info("Starting BTC 15M Server process: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=APP_DIR,
        env=sub_env,
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

def ensure_tunnels():
    import psutil, subprocess
    domains = [
        (NGROK_DOMAIN, APP_PORT),
        ("mlb-predictz.ngrok.app", 8057)
    ]
    for domain, port in domains:
        ok = False
        try:
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                if p.info['name'] == 'ngrok.exe':
                    cmdline = ' '.join(p.info['cmdline'] or [])
                    if domain in cmdline:
                        if f" {port} " in f" {cmdline} " or f":{port} " in f" {cmdline} " or f":{port}" in f" {cmdline}":
                            ok = True
                        else:
                            subprocess.call(["taskkill", "/F", "/PID", str(p.info['pid'])], creationflags=0x08000000)
        except:
            pass
        if not ok:
            logger.info(f"[Watchdog] Starting ngrok tunnel {domain} -> port {port}...")
            ngrok_bin = r"C:\Users\Vill3\AppData\Local\ngrok\ngrok.exe" if os.path.exists(r"C:\Users\Vill3\AppData\Local\ngrok\ngrok.exe") else "ngrok"
            subprocess.Popen([ngrok_bin, "http", "127.0.0.1:" + str(port), f"--url={domain}"], creationflags=0x08000000, close_fds=True)

def _ngrok_monitor():
    while True:
        ensure_tunnels()
        time.sleep(60)


import atexit
import signal

_watchdog_mutex = None

def _release_watchdog_lock():
    global _watchdog_mutex
    if _watchdog_mutex and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(_watchdog_mutex)
            _watchdog_mutex = None
        except Exception as e:
            logger.debug(f"[Watchdog] Error releasing mutex handle: {e}")

atexit.register(_release_watchdog_lock)

def _is_another_watchdog_running():
    import psutil
    current_pid = os.getpid()
    parent_pid = os.getppid()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.info['pid'] in (current_pid, parent_pid):
                continue
            pname = str(p.info.get('name') or '').lower()
            if not pname.startswith('python'):
                continue
            cmdline = p.info.get('cmdline') or []
            if len(cmdline) >= 2 and os.path.basename(cmdline[1]).lower() == 'server_watchdog.py':
                return True
        except Exception:
            pass
    return False

def _acquire_watchdog_lock():
    global _watchdog_mutex
    if sys.platform != "win32":
        return not _is_another_watchdog_running()
    
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "KalshiAITraderWatchdogLock")
    if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(mutex)
        return None
        
    _watchdog_mutex = mutex
    return mutex

def _terminate_conflicting_watchdogs():
    """If another watchdog or legacy instance is running, allow graceful takeover if requested."""
    import psutil
    current_pid = os.getpid()
    parent_pid = os.getppid()
    targets = ["server_watchdog.py", "launch_desktop.py", "backend/worker.py", "backend\\worker.py", "backend.main:app"]
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.info['pid'] in (current_pid, parent_pid):
                continue
            cmdline = ' '.join(p.info['cmdline'] or [])
            if any(t in cmdline for t in targets):
                logger.warning(f"[Watchdog] Graceful restart: Terminating existing process {cmdline[:60]} (PID {p.info['pid']})...")
                if sys.platform == "win32":
                    subprocess.call(["taskkill", "/F", "/T", "/PID", str(p.info['pid'])], creationflags=0x08000000)
                else:
                    p.kill()
        except Exception:
            pass


def _check_http_health(port: int = 8058, timeout: float = 3.0) -> bool:
    """True if port responds to HTTP GET or TCP connect."""
    import socket, urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/", headers={"User-Agent": "WatchdogHealthCheck"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        # Fall back to TCP connection check
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=timeout):
                return True
        except Exception:
            return False

def _kill_port_owner(port: int = 8058):
    """Kills any process currently listening on or holding the target port."""
    import psutil
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                pid = conn.pid
                if pid and pid != os.getpid():
                    logger.warning(f"[Watchdog] Killing orphan process PID {pid} holding port {port}...")
                    if sys.platform == "win32":
                        subprocess.call(["taskkill", "/F", "/T", "/PID", str(pid)], creationflags=0x08000000)
                    else:
                        psutil.Process(pid).kill()
    except Exception as e:
        logger.debug(f"[Watchdog] Error clearing port {port}: {e}")

def main():
    if "--restart" in sys.argv or "--force" in sys.argv or os.environ.get("WATCHDOG_RESTART") == "1":
        logger.info("[Watchdog] Restart requested. Terminating conflicting watchdogs for graceful restart...")
        _terminate_conflicting_watchdogs()
        time.sleep(1.0)

    lock_socket = _acquire_watchdog_lock()
    if lock_socket is None:
        logger.info("[Watchdog] Another server_watchdog instance is already active. Exiting duplicate process cleanly.")
        return 0

    def _sig_handler(sig, frame):
        logger.info(f"[Watchdog] Received signal {sig}. Exiting gracefully...")
        _release_watchdog_lock()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)
    except Exception:
        pass

    logger.info("==================================================")
    logger.info("  BTC 15M WATCHDOG SUPERVISOR INITIATED")
    logger.info("  Auto-Reboot on Crash Enabled")
    logger.info("==================================================")

    # Keep the ngrok tunnel up: checked now and every 60 s (restarted if it died)
    import threading
    threading.Thread(target=_ngrok_monitor, daemon=True, name="NgrokMonitor").start()
    threading.Thread(target=_sports_bridge_monitor, daemon=True, name="SportsBridgeMonitor").start()

    restart_count = 0

    while True:
        start_time = time.time()
        try:
            proc = run_server()
            
            last_health_check = time.time()
            consecutive_health_fails = 0
            HEALTH_STARTUP_GRACE_SEC = 45.0  # Allow server 45s to load weights & connect WS
            try:
                while True:
                    line = proc.stdout.readline()
                    if line:
                        line_str = line.strip()
                        if line_str:
                            logger.info("[Server] %s", line_str)
                    elif proc.poll() is not None:
                        break
                    else:
                        time.sleep(0.02)

                    # Periodic Port 8058 Health Check
                    now_ts = time.time()
                    if (now_ts - last_health_check) >= 20.0:
                        last_health_check = now_ts
                        elapsed_uptime = now_ts - start_time
                        if elapsed_uptime > HEALTH_STARTUP_GRACE_SEC:
                            healthy = _check_http_health(APP_PORT, timeout=2.5)
                            if healthy:
                                consecutive_health_fails = 0
                            else:
                                consecutive_health_fails += 1
                                logger.warning(f"[Watchdog] Port {APP_PORT} health check FAILED ({consecutive_health_fails}/3)")
                                if consecutive_health_fails >= 3:
                                    logger.error(f"[Watchdog] Port {APP_PORT} unresponsive for >60s! Killing frozen process tree & respawning...")
                                    try:
                                        if sys.platform == "win32":
                                            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], creationflags=0x08000000)
                                        else:
                                            proc.kill()
                                    except Exception:
                                        pass
                                    _kill_port_owner(APP_PORT)
                                    break
            except Exception as stream_err:
                logger.debug(f"[Watchdog] Server stream error: {stream_err}")

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

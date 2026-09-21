"""
Remote Tunnel Supervisor for Kalshi AI Trader
Uses Cloudflare Quick Tunnel (cloudflared) to provide free, secure HTTPS remote access.
Automatically detects the public URL, generates a QR code, and creates Desktop shortcuts.
"""

import os
import sys
import time
import re
import glob
import subprocess
import logging

logger = logging.getLogger("RemoteTunnel")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(APP_DIR, ".local_token")
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
URL_FILE = os.path.join(DESKTOP_DIR, "REMOTE_ACCESS_URL.txt")
SHORTCUT_FILE = os.path.join(DESKTOP_DIR, "Remote AI Trader (Phone Link).url")
QR_DESKTOP_FILE = os.path.join(DESKTOP_DIR, "REMOTE_ACCESS_QR.png")
QR_ASSET_FILE = os.path.join(APP_DIR, "static", "assets", "server_qr.png")
CLOUDFLARED_LOG = os.path.join(APP_DIR, "cloudflared.log")
TUNNEL_LOG = os.path.join(APP_DIR, "remote_tunnel.log")

# Setup logging
_handlers = [logging.FileHandler(TUNNEL_LOG, encoding="utf-8")]
if sys.stdout is not None:
    _handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_handlers
)


def find_cloudflared_exe() -> str:
    """Find installed cloudflared executable."""
    import shutil
    path_hit = shutil.which("cloudflared")
    if path_hit and os.path.exists(path_hit):
        return path_hit

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        pattern = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages", "*cloudflared*", "cloudflared.exe")
        matches = glob.glob(pattern)
        if matches and os.path.exists(matches[0]):
            return matches[0]

    common = [
        r"C:\Program Files\cloudflared\cloudflared.exe",
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    ]
    for c in common:
        if os.path.exists(c):
            return c

    return "cloudflared.exe"


def get_auth_token() -> str:
    """Load API token from environment or .local_token file."""
    token = os.environ.get("APP_API_TOKEN", "").strip()
    if token:
        return token
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""


def generate_qr_and_shortcuts(tunnel_url: str, token: str):
    """Save user-friendly links, Desktop shortcut, and QR code."""
    auth_url = f"{tunnel_url}/?token={token}" if token else f"{tunnel_url}/"

    # 1. Write text file on Desktop
    try:
        content = (
            "===================================================================\n"
            "   KALSHI AI TRADER - SECURE CLOUD REMOTE ACCESS\n"
            "===================================================================\n\n"
            "Your PC is now broadcasting the AI Trader dashboard over a secure,\n"
            "encrypted Cloudflare HTTPS connection.\n\n"
            f"DIRECT PHONE / MOBILE LINK:\n{auth_url}\n\n"
            "HOW TO USE FROM YOUR PHONE (SAFARI / CHROME):\n"
            "1. Open the link above in your phone's browser.\n"
            "2. (Optional) In Safari: tap the Share button -> 'Add to Home Screen'\n"
            "   In Chrome: tap the 3 dots menu -> 'Add to Home screen'\n"
            "3. The dashboard will launch full-screen just like a native app!\n\n"
            f"API TOKEN PRE-LOADED: {token or '(None)'}\n"
            "QR CODE: Open 'REMOTE_ACCESS_QR.png' on your Desktop and scan\n"
            "with your phone camera.\n"
            "===================================================================\n"
        )
        with open(URL_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("[RemoteTunnel] Updated %s", URL_FILE)
    except Exception as e:
        logger.warning("[RemoteTunnel] Failed to write %s: %s", URL_FILE, e)

    # 2. Write Windows .url Internet Shortcut
    try:
        url_content = f"[InternetShortcut]\nURL={auth_url}\nIconIndex=0\n"
        with open(SHORTCUT_FILE, "w", encoding="utf-8") as f:
            f.write(url_content)
        logger.info("[RemoteTunnel] Updated %s", SHORTCUT_FILE)
    except Exception as e:
        logger.warning("[RemoteTunnel] Failed to write %s: %s", SHORTCUT_FILE, e)

    # 3. Generate QR code
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(auth_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        os.makedirs(os.path.dirname(QR_ASSET_FILE), exist_ok=True)
        img.save(QR_ASSET_FILE)
        img.save(QR_DESKTOP_FILE)
        logger.info("[RemoteTunnel] Generated QR code at %s and %s", QR_ASSET_FILE, QR_DESKTOP_FILE)
    except Exception as e:
        logger.warning("[RemoteTunnel] Failed to generate QR code: %s", e)


def run_tunnel():
    """Runs cloudflared tunnel in a loop with auto-reconnect."""
    exe = find_cloudflared_exe()
    if not os.path.exists(exe):
        logger.error("[RemoteTunnel] cloudflared.exe not found at %s. Tunnel cannot start.", exe)
        return

    token = get_auth_token()
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Cleanup lingering cloudflared processes from prior runs
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True, text=True)
        except Exception:
            pass

    while True:
        try:
            active_url = None
            if os.path.exists(CLOUDFLARED_LOG):
                try:
                    os.remove(CLOUDFLARED_LOG)
                except Exception:
                    pass

            logger.info("[RemoteTunnel] Starting Cloudflare Quick Tunnel on port 8056...")
            cmd = [exe, "tunnel", "--url", "http://127.0.0.1:8056", "--logfile", CLOUDFLARED_LOG]
            proc = subprocess.Popen(
                cmd,
                cwd=APP_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=flags
            )

            # Tail log until URL is detected
            for _ in range(40):
                time.sleep(0.5)
                if os.path.exists(CLOUDFLARED_LOG):
                    try:
                        with open(CLOUDFLARED_LOG, "r", encoding="utf-8", errors="ignore") as lf:
                            log_text = lf.read()
                            matches = url_regex.findall(log_text)
                            if matches:
                                active_url = matches[-1]
                                logger.info("[RemoteTunnel] *** LIVE REMOTE ACCESS URL: %s ***", active_url)
                                generate_qr_and_shortcuts(active_url, token)
                                break
                    except Exception:
                        pass
                if proc.poll() is not None:
                    break
            
            # Liveness loop
            consecutive_failures = 0
            while proc.poll() is None:
                time.sleep(20)
                if active_url:
                    try:
                        import requests
                        res = requests.get(f"{active_url}/api/health", timeout=10)
                        if res.status_code == 200:
                            consecutive_failures = 0
                        else:
                            consecutive_failures += 1
                    except Exception:
                        consecutive_failures += 1
                    
                    if consecutive_failures >= 3:
                        logger.warning("[RemoteTunnel] Tunnel liveness check failed 3 times. Forcing restart.")
                        proc.terminate()
                        time.sleep(2)
                        proc.kill()
                        break
            
            logger.warning("[RemoteTunnel] cloudflared process exited with code %s. Restarting in 5s...", proc.returncode)
            time.sleep(5)

        except Exception as e:
            logger.error("[RemoteTunnel] Error in tunnel runner: %s", e)
            time.sleep(5)


def start_tunnel_in_background():
    """Starts the tunnel in a background daemon thread."""
    import threading
    t = threading.Thread(target=run_tunnel, daemon=True, name="CloudflareTunnelWorker")
    t.start()
    return t


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_tunnel()

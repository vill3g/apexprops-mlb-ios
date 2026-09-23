import os
import sys
import time
import logging
import qrcode
import threading
from urllib.parse import quote
from pyngrok import ngrok, conf

logger = logging.getLogger(__name__)

DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
URL_FILE = os.path.join(DESKTOP_DIR, "REMOTE_ACCESS_URL.txt")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".local_token")

def get_auth_token() -> str:
    token = os.environ.get("APP_API_TOKEN", "").strip()
    if token: return token
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

def generate_qr_and_shortcuts(tunnel_url: str, token: str):
    try:
        full_url = tunnel_url
        if token:
            full_url += f"/?token={quote(token)}"
            
        shortcut_path = os.path.join(DESKTOP_DIR, "Remote AI Trader (Phone Link).url")
        with open(shortcut_path, "w", encoding="utf-8") as f:
            f.write("[InternetShortcut]\n")
            f.write(f"URL={full_url}\n")
            f.write("IconIndex=0\n")
            
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(full_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        static_assets = os.path.join(os.path.dirname(__file__), "static", "assets")
        os.makedirs(static_assets, exist_ok=True)
        img.save(os.path.join(static_assets, "server_qr.png"))
        img.save(os.path.join(DESKTOP_DIR, "REMOTE_ACCESS_QR.png"))
        
        with open(URL_FILE, "w", encoding="utf-8") as f:
            f.write("===================================================================\n")
            f.write("   KALSHI AI TRADER - SECURE NGROK REMOTE ACCESS\n")
            f.write("===================================================================\n\n")
            f.write("Your PC is now broadcasting the AI Trader dashboard over a permanent,\n")
            f.write("encrypted ngrok HTTPS connection.\n\n")
            f.write("DIRECT PHONE / MASTER LINK (Private):\n")
            f.write(f"{full_url}\n\n")
            f.write("SAAS PUBLIC COPILOT LINK (Share with users):\n")
            f.write(f"{tunnel_url}/login.html\n\n")
            f.write("===================================================================\n")
            
        logger.info("[RemoteTunnel] *** LIVE REMOTE ACCESS URL: %s ***", tunnel_url)
    except Exception as e:
        logger.error(f"[RemoteTunnel] Failed to generate links/QR: {e}")

def run_tunnel():
    try:
        # User's provided permanent auth token
        conf.get_default().auth_token = "3JhyBfP9ni38Xo5aAMpHnsEshOO_2CuYDLLwz4rY3oBz8stsg"
        
        # Connect ngrok to local port 8056
        http_tunnel = ngrok.connect(8056)
        public_url = http_tunnel.public_url
        
        token = get_auth_token()
        generate_qr_and_shortcuts(public_url, token)
        
        # Keep daemon thread alive
        while True:
            time.sleep(3600)
    except Exception as e:
        logger.error(f"[RemoteTunnel] ngrok tunnel error: {e}")

def start_tunnel_in_background():
    t = threading.Thread(target=run_tunnel, daemon=True, name="NgrokTunnelWorker")
    t.start()
    return t

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_tunnel()

import os
import subprocess
import urllib.request
import json
import base64

def get_token():
    out = subprocess.check_output(["gh.exe", "auth", "token"]).decode().strip()
    return out

token = get_token()
repo = "vill3g/apexprops-mlb-ios"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "ApexProps-Uploader"
}

files_to_upload = [
    "package.json",
    "capacitor.config.json",
    "README.md",
    "static/index.html",
    "static/manifest.json",
    "static/assets/logo_minimal.jpg",
    "static/assets/logo_monogram.jpg",
    "static/assets/logo_shield.jpg",
    "static/data/top5.json",
    "static/data/props.json",
    "static/data/pitchers.json",
    "static/data/npb.json",
    "static/data/kbo.json",
    "static/data/npb_standings.json",
    "static/data/kbo_standings.json",
    "static/data/historical.json",
    "static/data/draftkings.json",
    "backend/main.py",
    "backend/data/espn_client.py",
    "backend/data/draftkings_client.py",
    "backend/data/verified_mlb_client.py",
    "backend/data/injuries_client.py",
    "backend/data/player_photos.py",
    "backend/data/player_photos_registry.json",
    "static/data/player_photos.json",
    "backend/engine/top5_selector.py",
    "backend/engine/pitcher_k_model.py",
    "backend/engine/simulator.py",
    "backend/engine/international_model.py",
    "backend/engine/bvp_weather.py",
    "backend/btc/__init__.py",
    "backend/btc/data_fetcher.py",
    "backend/btc/kalshi_client.py",
    "backend/btc/indicators.py",
    "backend/btc/pattern_detector.py",
    "backend/btc/analyzer.py",
    "static/data/gamelogs_cache.json",
    "static/data/injuries.json",
    "static/data/btc_analysis.json",
    "static/data/btc_candles.json",
    "static/data/btc_ticker.json",
    ".github/workflows/build_ipa.yml"
]

base_dir = os.path.abspath(os.path.dirname(__file__))

for rel_path in files_to_upload:
    full_path = os.path.join(base_dir, rel_path.replace('/', os.sep))
    if not os.path.exists(full_path):
        print(f"Skipping {rel_path}, not found.")
        continue

    with open(full_path, "rb") as f:
        content_bytes = f.read()

    b64_content = base64.b64encode(content_bytes).decode("utf-8")
    
    # Check if file exists to get sha
    url = f"https://api.github.com/repos/{repo}/contents/{rel_path}"
    sha = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            sha = data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"Check error on {rel_path}: {e}")

    payload = {
        "message": f"Add {rel_path} for iOS IPA build",
        "content": b64_content
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Uploaded: {rel_path} -> HTTP {resp.status}")
    except Exception as e:
        print(f"Failed to upload {rel_path}: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode())

print("Upload complete!")

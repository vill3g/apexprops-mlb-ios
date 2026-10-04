import os
import re
import json
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_DIR = os.path.join(REPO_ROOT, "static")

from backend.main import app

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

def test_task1_favicon_route_200(client):
    """Task 1: GET /favicon.ico must return 200 OK with image/x-icon media type."""
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert "icon" in resp.headers.get("content-type", "").lower()

def test_task2_login_html_asset_integrity():
    """Task 2: login.html logo and favicon links point to existing assets, no missing SVGs/ICOs."""
    fpath = os.path.join(STATIC_DIR, "login.html")
    assert os.path.isfile(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    assert "favicon.svg" not in content
    assert "app_icon.ico" not in content
    assert '<img src="./assets/icon.png"' in content
    assert '<link rel="icon" type="image/x-icon" href="./favicon.ico">' in content

def test_task3_trades_html_asset_integrity():
    """Task 3: trades.html favicon and icon links point to existing assets."""
    fpath = os.path.join(STATIC_DIR, "trades.html")
    assert os.path.isfile(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    assert "favicon.svg" not in content
    assert "app_icon.ico" not in content
    assert '<link rel="icon" type="image/x-icon" href="./favicon.ico">' in content
    assert '<link rel="icon" type="image/png" sizes="192x192" href="./assets/icon.png">' in content

def test_task4_manifest_relative_paths():
    """Task 4: manifest.json uses relative ./assets/ paths and all icons exist on disk."""
    fpath = os.path.join(STATIC_DIR, "manifest.json")
    assert os.path.isfile(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    icons = manifest.get("icons", [])
    assert len(icons) > 0
    for icon in icons:
        src = icon.get("src", "")
        assert src.startswith("./assets/"), f"Icon src {src} should be relative (./assets/...)"
        clean_rel = src.lstrip("./")
        disk_path = os.path.join(STATIC_DIR, clean_rel)
        assert os.path.isfile(disk_path), f"Manifest icon {src} missing on disk at {disk_path}"
        assert os.path.getsize(disk_path) > 0

def test_task5_app_js_fallback_status_check():
    """Task 5: app.js checks !res || !res.ok before parsing fallback JSON."""
    fpath = os.path.join(STATIC_DIR, "js", "app.js")
    assert os.path.isfile(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    assert "!tRes || !tRes.ok" in content
    assert "!pRes || !pRes.ok" in content
    assert "!res || !res.ok" in content

def test_task6_service_worker_root_route(client):
    """Task 6: /sw.js serves static/sw.js with Service-Worker-Allowed: / header."""
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert resp.headers.get("service-worker-allowed") == "/"
    assert "javascript" in resp.headers.get("content-type", "").lower()

def test_task7_update_ipa_excludes_ai_avatar():
    """Task 7: update_ipa.py explicitly excludes dead 8.3 MB ai_avatar.gif."""
    fpath = os.path.join(REPO_ROOT, "update_ipa.py")
    assert os.path.isfile(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    assert "ai_avatar.gif" in content
    assert "continue" in content

def test_task8_all_html_local_assets_exist_on_disk():
    """Task 8: Verify all local static assets (images, icons, styles, scripts, data) exist on physical disk."""
    asset_exts = {".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".json", ".woff", ".woff2", ".ttf", ".mp3", ".wav"}
    html_files = ["saas_dashboard.html", "login.html", "trades.html", "admin_mobile.html"]
    for page in html_files:
        fpath = os.path.join(STATIC_DIR, page)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        urls = re.findall(r'(?:src|href)=["\']([^"\']+)["\']', content)
        for u in urls:
            if u.startswith(("http://", "https://", "//", "data:", "javascript:", "#", "mailto:", "${")):
                continue
            clean = u.split("?")[0].split("#")[0]
            ext = os.path.splitext(clean)[1].lower()
            if ext not in asset_exts:
                continue
            # Candidate resolution
            c1 = os.path.join(STATIC_DIR, clean.lstrip("./").removeprefix("static/"))
            c2 = os.path.join(REPO_ROOT, clean.lstrip("/"))
            assert os.path.exists(c1) or os.path.exists(c2), f"Static asset {u} referenced in {page} does not exist on disk"


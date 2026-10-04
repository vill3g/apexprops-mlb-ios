import os
import re
import json
from collections import Counter
from html.parser import HTMLParser
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_DIR = os.path.join(REPO_ROOT, "static")

from backend.main import app

# HTML5 void elements that do not have closing tags
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}

HTML_PAGES = ["saas_dashboard.html", "login.html", "trades.html", "admin_mobile.html"]


class DOMValidator(HTMLParser):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.stack = []  # list of (tag, line, col, elem_id)
        self.errors = []
        self.ids = []  # list of (elem_id, line, col, tag)
        self.settings_drawer_open = None
        self.settings_drawer_close = None
        self.settings_drawer_depth = None
        self.settings_drawer_parent_stack = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        line, col = self.getpos()
        elem_id = attrs_dict.get("id")
        if elem_id:
            self.ids.append((elem_id, line, col, tag))
            if elem_id == "settingsDrawer":
                self.settings_drawer_open = line
                self.settings_drawer_depth = len(self.stack)
                self.settings_drawer_parent_stack = [t[0] for t in self.stack]

        if tag.lower() not in VOID_ELEMENTS:
            self.stack.append((tag.lower(), line, col, elem_id))

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        line, col = self.getpos()

        if tag_lower in VOID_ELEMENTS:
            self.errors.append(f"{self.filename}:{line}:{col} - Void element </{tag_lower}> should not have a closing tag.")
            return

        if not self.stack:
            self.errors.append(f"{self.filename}:{line}:{col} - Stray closing tag </{tag_lower}> with empty tag stack.")
            return

        # Check top of stack
        top_tag, top_line, top_col, top_id = self.stack[-1]
        if top_tag == tag_lower:
            popped = self.stack.pop()
            if popped[3] == "settingsDrawer":
                self.settings_drawer_close = line
            return

        # Check if tag exists anywhere in stack
        stack_tags = [t[0] for t in self.stack]
        if tag_lower in stack_tags:
            idx = len(self.stack) - 1 - stack_tags[::-1].index(tag_lower)
            unclosed = self.stack[idx + 1:]
            unclosed_desc = [f"<{t[0]} id='{t[3]}'> (line {t[1]})" for t in unclosed]
            self.errors.append(
                f"{self.filename}:{line}:{col} - Closing </{tag_lower}> prematurely closed parent while children unclosed: {unclosed_desc}"
            )
            for t in unclosed:
                if t[3] == "settingsDrawer":
                    self.errors.append(f"{self.filename}:{line}:{col} - #settingsDrawer was implicitly closed by </{tag_lower}>!")
            self.stack = self.stack[:idx]
        else:
            self.errors.append(
                f"{self.filename}:{line}:{col} - Stray closing tag </{tag_lower}> (no matching open tag in stack; top is <{top_tag}> from line {top_line})."
            )


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_html_structure_and_no_unclosed_tags():
    """Adversarially challenge HTML tags across all primary templates."""
    for page in HTML_PAGES:
        fpath = os.path.join(STATIC_DIR, page)
        assert os.path.isfile(fpath), f"{page} not found on disk at {fpath}"
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        validator = DOMValidator(page)
        validator.feed(content)

        critical_unclosed = [
            t for t in validator.stack
            if t[0] in {"div", "section", "main", "nav", "header", "footer", "aside", "form", "script", "style", "table", "body", "html"}
        ]
        assert len(critical_unclosed) == 0, (
            f"Unclosed container elements in {page}: {[(t[0], 'line', t[1], 'id', t[3]) for t in critical_unclosed]}"
        )
        assert len(validator.errors) == 0, f"HTML syntax errors in {page}: {validator.errors[:10]}"


def test_settings_drawer_closure_and_hierarchy():
    """Verify #settingsDrawer specifically in saas_dashboard.html opens and explicitly closes."""
    fpath = os.path.join(STATIC_DIR, "saas_dashboard.html")
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    validator = DOMValidator("saas_dashboard.html")
    validator.feed(content)

    assert validator.settings_drawer_open is not None, "#settingsDrawer tag was not found in saas_dashboard.html"
    assert validator.settings_drawer_close is not None, "#settingsDrawer tag was never closed in saas_dashboard.html"
    assert validator.settings_drawer_close > validator.settings_drawer_open, (
        f"#settingsDrawer close line ({validator.settings_drawer_close}) must be after open line ({validator.settings_drawer_open})"
    )


def test_no_duplicate_element_ids():
    """Ensure no duplicate DOM element IDs exist in any HTML template."""
    duplicate_report = {}
    for page in HTML_PAGES:
        fpath = os.path.join(STATIC_DIR, page)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        validator = DOMValidator(page)
        validator.feed(content)

        id_counter = Counter([i[0] for i in validator.ids])
        dupes = {elem_id: cnt for elem_id, cnt in id_counter.items() if cnt > 1}
        if dupes:
            details = {}
            for did, cnt in dupes.items():
                occurrences = [(tag, line) for elem_id, line, col, tag in validator.ids if elem_id == did]
                details[did] = {"count": cnt, "occurrences": occurrences}
            duplicate_report[page] = details

    assert not duplicate_report, f"Duplicate element IDs discovered: {json.dumps(duplicate_report, indent=2)}"


def test_static_asset_fuzzing_physical_disk():
    """Extract all referenced static assets across HTML, CSS, JS, and manifest.json.
    Verify that EVERY extracted asset resolves to a physical non-empty file on disk.
    """
    asset_exts = {
        ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
        ".webp", ".json", ".woff", ".woff2", ".ttf", ".mp3", ".wav"
    }

    scanned_files = []
    for root, dirs, files in os.walk(STATIC_DIR):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in {".html", ".css", ".js", ".json"}:
                scanned_files.append(os.path.join(root, f))

    all_referenced_assets = set()

    for fpath in scanned_files:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        urls = re.findall(r'(?:src|href)=["\']([^"\']+)["\']', content)
        css_urls = re.findall(r'url\([\'"]?([^\'")]+)[\'"]?\)', content)
        if fpath.endswith("manifest.json"):
            try:
                mdata = json.loads(content)
                for icon in mdata.get("icons", []):
                    if "src" in icon:
                        urls.append(icon["src"])
            except Exception:
                pass

        for raw in urls + css_urls:
            raw = raw.strip()
            if raw.startswith(("http://", "https://", "//", "data:", "javascript:", "#", "mailto:", "${")):
                continue
            clean = raw.split("?")[0].split("#")[0]
            ext = os.path.splitext(clean)[1].lower()
            if ext in asset_exts:
                all_referenced_assets.add((clean, os.path.basename(fpath)))

    assert len(all_referenced_assets) > 0, "No static assets found during extraction"

    missing_assets = []
    empty_assets = []

    for rel_path, source_file in all_referenced_assets:
        candidates = [
            os.path.join(STATIC_DIR, rel_path.lstrip("./").removeprefix("static/")),
            os.path.join(STATIC_DIR, rel_path.lstrip("/")),
            os.path.join(REPO_ROOT, rel_path.lstrip("/")),
            os.path.join(STATIC_DIR, "assets", os.path.basename(rel_path)),
            os.path.join(STATIC_DIR, os.path.basename(rel_path)),
        ]
        found_path = None
        for cand in candidates:
            if os.path.isfile(cand):
                found_path = cand
                break

        if not found_path:
            missing_assets.append((rel_path, source_file))
        else:
            size = os.path.getsize(found_path)
            if size == 0:
                empty_assets.append((rel_path, found_path, source_file))

    assert not missing_assets, f"Missing static assets referenced in code: {missing_assets}"
    assert not empty_assets, f"Empty (0-byte) static assets found: {empty_assets}"


def test_fastapi_endpoints_zero_404(client):
    """Verify zero 404s for critical static endpoints and assets via FastAPI TestClient."""
    critical_endpoints = [
        "/favicon.ico",
        "/sw.js",
        "/static/sw.js",
        "/static/saas_dashboard.html",
        "/static/login.html",
        "/static/trades.html",
        "/static/admin_mobile.html",
        "/static/manifest.json",
        "/static/assets/icon.png",
        "/static/assets/apple-touch-icon.png",
        "/static/assets/app_icon_192.png",
        "/static/assets/app_icon_512.png",
        "/static/css/app.css",
        "/static/css/dashboard.css",
        "/static/js/app.js",
        "/static/js/dashboard.js",
        "/static/js/admin_users.js",
    ]

    failures = []
    for ep in critical_endpoints:
        resp = client.get(ep)
        if resp.status_code != 200:
            failures.append((ep, resp.status_code))

    assert not failures, f"Endpoints returned non-200 status codes: {failures}"


def test_capacitor_relative_routing_and_navigation():
    """Adversarially verify that all anchor tags and navigation links avoid absolute paths
    that break Capacitor WKWebView local filesystem routing (capacitor://localhost).
    """
    broken_absolute_links = []

    for page in HTML_PAGES:
        fpath = os.path.join(STATIC_DIR, page)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        a_tags = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>', content, re.IGNORECASE)
        for href in a_tags:
            href_clean = href.strip()
            if href_clean.startswith(("http://", "https://", "#", "javascript:", "mailto:", "tel:", "${")):
                continue
            if href_clean.startswith("/") and not href_clean.startswith("//"):
                broken_absolute_links.append((page, href_clean))

    # Also check JS templates
    admin_users_js = os.path.join(STATIC_DIR, "js", "admin_users.js")
    with open(admin_users_js, "r", encoding="utf-8") as f:
        js_content = f.read()
    js_a_tags = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>', js_content, re.IGNORECASE)
    for href in js_a_tags:
        href_clean = href.strip()
        if href_clean.startswith("/") and not href_clean.startswith("//"):
            broken_absolute_links.append(("js/admin_users.js", href_clean))

    assert not broken_absolute_links, (
        f"Found broken absolute navigation links breaking Capacitor WKWebView: {broken_absolute_links}. "
        f"These must be relative (e.g. './admin_mobile.html' instead of '/admin/mobile', and './saas_dashboard.html')."
    )


def test_capacitor_manifest_icon_relative_paths():
    """Verify manifest.json icons use relative paths and point to existing non-empty files."""
    fpath = os.path.join(STATIC_DIR, "manifest.json")
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    icons = data.get("icons", [])
    assert len(icons) > 0, "No icons in manifest.json"

    for icon in icons:
        src = icon.get("src", "")
        assert not src.startswith("/"), f"Manifest icon {src} is an absolute path; must be relative for Capacitor"
        assert src.startswith("./assets/") or src.startswith("assets/"), f"Icon {src} must point to relative assets/"
        clean_rel = src.lstrip("./")
        disk_path = os.path.join(STATIC_DIR, clean_rel)
        assert os.path.isfile(disk_path), f"Manifest icon {src} does not exist at {disk_path}"
        assert os.path.getsize(disk_path) > 0, f"Manifest icon {src} is empty (0 bytes) at {disk_path}"

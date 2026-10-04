# Explorer Fix 1 Investigation Report: HTML Navigation Links in Capacitor

**Agent**: explorer_fix_1  
**Role**: teamwork_preview_explorer (investigator / synthesizer)  
**Date**: 2026-10-02T19:18:00Z  
**Target Path**: `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_fix_1\handoff.md`  
**Patch Artifact**: `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_fix_1\capacitor_relative_links.patch`  

---

## 1. Observation

### 1.1 Verbatim Adversarial Test Failure
Running `pytest tests/test_challenger2_adversarial.py -v`:
```powershell
python -m pytest tests/test_challenger2_adversarial.py -v
```
**Output**:
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Vill3\Desktop\ShadowTraderAi
plugins: anyio-4.15.1
collected 7 items

tests/test_challenger2_adversarial.py::test_html_structure_and_no_unclosed_tags PASSED [ 14%]
tests/test_challenger2_adversarial.py::test_settings_drawer_closure_and_hierarchy PASSED [ 28%]
tests/test_challenger2_adversarial.py::test_no_duplicate_element_ids PASSED [ 42%]
tests/test_challenger2_adversarial.py::test_static_asset_fuzzing_physical_disk PASSED [ 57%]
tests/test_challenger2_adversarial.py::test_fastapi_endpoints_zero_404 PASSED [ 71%]
tests/test_challenger2_adversarial.py::test_capacitor_relative_routing_and_navigation FAILED [ 85%]
tests/test_challenger2_adversarial.py::test_capacitor_manifest_icon_relative_paths PASSED [100%]

================================== FAILURES ===================================
_______________ test_capacitor_relative_routing_and_navigation ________________

AssertionError: Found broken absolute navigation links breaking Capacitor WKWebView: [('admin_mobile.html', '/saas_dashboard.html'), ('js/admin_users.js', '/trades?user=${u.id}')]. These must be relative (e.g. './admin_mobile.html' instead of '/admin/mobile', and './saas_dashboard.html').
assert not [('admin_mobile.html', '/saas_dashboard.html'), ('js/admin_users.js', '/trades?user=${u.id}')]

=========================== short test summary info ===========================
FAILED tests/test_challenger2_adversarial.py::test_capacitor_relative_routing_and_navigation
=================== 1 failed, 6 passed, 1 warning in 7.94s ====================
```

### 1.2 Exhaustive Audit of All HTML and JS Files in `static/`
An exhaustive AST and regex scan across all 5 HTML files and 5 JS files in `static/` identified the following link behaviors:

| File Path | Line # | Current Code Snippet | Link Type | Status / Issue |
|---|---|---|---|---|
| `static/admin_mobile.html` | 92 | `<a href="/saas_dashboard.html" class="...">` | Absolute Anchor | **FAILS TEST**. Absolute web root path breaks iOS Capacitor WKWebView bundle routing. |
| `static/admin_mobile.html` | 610 | `setTimeout(() => window.location.href = './login.html', 1500);` | Relative Script | PASS (Relative) |
| `static/admin_mobile.html` | 1130 | `window.location.href = './login.html';` | Relative Script | PASS (Relative) |
| `static/index.html` | 5 | `<meta http-equiv="refresh" content="0; url=saas_dashboard.html">` | Relative Meta | PASS (Relative) |
| `static/index.html` | 8 | `window.location.replace("saas_dashboard.html");` | Relative Script | PASS (Relative) |
| `static/login.html` | 49-52 | `<link rel="manifest" href="./manifest.json">`, `./favicon.ico`, etc. | Relative Links | PASS (Relative) |
| `static/login.html` | 559, 594 | `window.location.href = './admin_mobile.html';` | Relative Script | PASS (Relative) |
| `static/login.html` | 630 | `window.location.href = './saas_dashboard.html';` | Relative Script | PASS (Relative) |
| `static/saas_dashboard.html` | 15-28 | `<link ... href="./assets/...">` | Relative Links | PASS (Relative) |
| `static/saas_dashboard.html` | 609-610 | `<link rel="stylesheet" href="./css/dashboard.css">`, `./css/app.css` | Relative Links | PASS (Relative) |
| `static/saas_dashboard.html` | 759 | `onclick="... window.open('/trades' + (id ? '?guest=' + id : ''), '_blank'); return false;"` | Absolute Script | **RUNTIME BUG**. Opens `/trades` which 404s in WKWebView (needs `./trades.html`). |
| `static/saas_dashboard.html` | 6063 | `<a href="./admin_mobile.html" class="...">` | Relative Anchor | PASS (Relative) |
| `static/trades.html` | 7-9 | `<link ... href="./assets/...">` | Relative Links | PASS (Relative) |
| `static/trades.html` | 27 | `<button onclick="window.close()" ...>Close</button>` | Window Close | PASS (No links) |
| `static/js/admin_users.js` | 1382 | `<a href="/trades?user=${u.id}" target="_blank" class="...">` | Absolute Anchor | **FAILS TEST**. Absolute path missing `.html` extension; 404s in Capacitor WKWebView. |

### 1.3 FastAPI Backend Route Parity Check
Testing direct root path requests to FastAPI `backend/routes/ui.py`:
- `GET /admin_mobile.html` -> **HTTP 404** (Only `/admin/mobile` is registered at `ui.py:98`).
- `GET /manifest.json` -> **HTTP 404** (Only mounted at `/static/manifest.json`).

---

## 2. Logic Chain

1. **Capacitor Architecture**:
   - `capacitor.config.json` configures `"webDir": "static"` and `"limitsNavigationsToAppBoundDomains": true`.
   - In iOS Capacitor, all static bundle assets are loaded via the internal scheme `capacitor://localhost/` directly from the filesystem without a dynamic server URL rewrite layer.
   - Any URL referencing an absolute path without a filename extension (such as `/trades`) fails with an immediate 404 / File Not Found error, as the filesystem only contains `trades.html`.

2. **Link Asymmetry between Admin and Dashboard**:
   - In `static/saas_dashboard.html:6063`, Worker M4 established the outbound link using relative pathing: `<a href="./admin_mobile.html">`.
   - However, the reciprocal back button in `static/admin_mobile.html:92` was left as `<a href="/saas_dashboard.html">`.
   - When clicked inside Capacitor WKWebView, this absolute path breaks local bundle navigation. Replacing it with `<a href="./saas_dashboard.html">` establishes bidirectional relative navigation consistency.

3. **Admin User Ledger Routing**:
   - In `static/js/admin_users.js:1382`, the ledger link is constructed as `<a href="/trades?user=${u.id}">`.
   - This fails both requirements: (a) it uses an absolute web root slash (`/`), and (b) it lacks the `.html` extension.
   - Replacing this with `<a href="./trades.html?user=${u.id}">` allows Capacitor WKWebView to resolve the bundled `trades.html` file with the query parameter intact.

4. **Recent Executions Ledger Link in Dashboard**:
   - In `static/saas_dashboard.html:759`, the "View All" link invokes `window.open('/trades' + ..., '_blank')`.
   - While `test_challenger2_adversarial.py` only asserts on `<a>` tags with `href` attributes, executing `window.open('/trades')` at runtime on iOS Capacitor causes a 404 error.
   - Updating this to `window.open('./trades.html' + ..., '_blank')` ensures seamless operation across both iOS native WKWebView and desktop web browsers.

5. **Server Route Parity**:
   - In `backend/routes/ui.py`, adding route decorators `@router.get("/admin_mobile.html")` and `@router.get("/manifest.json")` guarantees that web browser clients requesting either standard web endpoints or relative bundle names receive HTTP 200 responses.

---

## 3. Caveats

- **Web Browser Navigation from `/admin/mobile`**: If a desktop web user accesses `http://localhost:8000/admin/mobile` directly, a relative link `./saas_dashboard.html` would resolve relative to the virtual path `/admin/` (i.e. `/admin/saas_dashboard.html`). Adding `@router.get("/admin_mobile.html")` in `ui.py` eliminates this issue because navigating via `admin_mobile.html` maintains uniform root relativity.
- **Service Worker (`sw.js`) Notification URLs**: `static/sw.js` lines 6, 20, 27 use `url: "/saas_dashboard.html"`. This is specifically for background Web Push API notifications in standard desktop browsers and does not impact Capacitor WKWebView (which uses APNS). It was not flagged by adversarial tests and requires no modification.

---

## 4. Conclusion

Remediation requires 2 mandatory changes to pass `test_challenger2_adversarial.py` and 2 recommended runtime hardening changes:

### 4.1 Mandatory Code Replacements (Fixing Adversarial Test Failures)

#### Change 1: `static/admin_mobile.html` (Line 92)
- **Target File**: `C:\Users\Vill3\Desktop\ShadowTraderAi\static\admin_mobile.html`
- **Line Number**: 92
- **Existing Content**:
```html
                <!-- Back to SaaS Dashboard -->
                <a href="/saas_dashboard.html" class="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white active:scale-95 transition-all py-1 px-2 rounded-lg bg-slate-800/60 border border-slate-700/60">
```
- **Replacement Content**:
```html
                <!-- Back to SaaS Dashboard -->
                <a href="./saas_dashboard.html" class="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white active:scale-95 transition-all py-1 px-2 rounded-lg bg-slate-800/60 border border-slate-700/60">
```

#### Change 2: `static/js/admin_users.js` (Line 1382)
- **Target File**: `C:\Users\Vill3\Desktop\ShadowTraderAi\static\js\admin_users.js`
- **Line Number**: 1382
- **Existing Content**:
```javascript
            <a href="/trades?user=${u.id}" target="_blank" class="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all active:scale-95" title="Open full trade ledger in new tab">
```
- **Replacement Content**:
```javascript
            <a href="./trades.html?user=${u.id}" target="_blank" class="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all active:scale-95" title="Open full trade ledger in new tab">
```

---

### 4.2 Recommended Hardening Changes (Runtime & Backend Parity)

#### Change 3: `static/saas_dashboard.html` (Line 759)
- **Target File**: `C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html`
- **Line Number**: 759
- **Existing Content**:
```html
                        <a href="#" onclick="const t = localStorage.getItem('saas_token'); const id = t ? JSON.parse(atob(t.split('.')[1])).user_id : ''; window.open('/trades' + (id ? '?guest=' + id : ''), '_blank'); return false;" class="text-[9px] font-bold text-kalshi-blue uppercase tracking-wider hover:underline">View All</a>
```
- **Replacement Content**:
```html
                        <a href="#" onclick="const t = localStorage.getItem('saas_token'); const id = t ? JSON.parse(atob(t.split('.')[1])).user_id : ''; window.open('./trades.html' + (id ? '?guest=' + id : ''), '_blank'); return false;" class="text-[9px] font-bold text-kalshi-blue uppercase tracking-wider hover:underline">View All</a>
```

#### Change 4: `backend/routes/ui.py` (Lines 98-107)
- **Target File**: `C:\Users\Vill3\Desktop\ShadowTraderAi\backend\routes\ui.py`
- **Line Number**: 98-107
- **Existing Content**:
```python
@router.get("/admin/mobile")
def get_admin_mobile():
    return FileResponse(
        os.path.join(STATIC_DIR, "admin_mobile.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )
```
- **Replacement Content**:
```python
@router.get("/admin_mobile.html")
@router.get("/admin/mobile")
def get_admin_mobile():
    return FileResponse(
        os.path.join(STATIC_DIR, "admin_mobile.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@router.get("/manifest.json")
def get_manifest():
    return FileResponse(
        os.path.join(STATIC_DIR, "manifest.json"),
        media_type="application/manifest+json"
    )
```

---

## 5. Verification Method

### 5.1 Verification Commands
After applying the changes (or patch `capacitor_relative_links.patch`), execute:

1. **Run Full Adversarial Test Suite**:
   ```powershell
   python -m pytest tests/test_challenger2_adversarial.py -v
   ```
   - **Expected Result**: 7 passed in ~7-8s.
   - Specifically `tests/test_challenger2_adversarial.py::test_capacitor_relative_routing_and_navigation PASSED`.

2. **Run Worker M3 Verification Suite**:
   ```powershell
   python -m pytest tests/test_worker_m3_verification.py -v
   ```
   - **Expected Result**: 8 passed in ~7s.

3. **Verify Route Aliases via TestClient**:
   ```powershell
   python -c "from fastapi.testclient import TestClient; from backend.main import app; c = TestClient(app); assert c.get('/admin_mobile.html').status_code == 200; assert c.get('/manifest.json').status_code == 200; print('Web route aliases OK')"
   ```

### 5.2 Invalidation Conditions
- Any occurrence of an anchor `<a href="/...">` starting with `/` (and not `//`) in `static/*.html` or `static/js/*.js` will cause `test_capacitor_relative_routing_and_navigation` to fail.
- Any navigation in Capacitor WKWebView pointing to an extensionless route like `/trades` without backend rewrite will result in a blank 404 page on device.

# Investigation Handoff Report: JS Navigation and Dynamic Links in Capacitor

**Agent**: explorer_fix_2  
**Role**: teamwork_preview_explorer  
**Date**: 2026-10-02T19:21:00Z  
**Status**: Investigation Complete  

---

## 1. Observation

### 1.1 Automated Adversarial Test Failure
Running the adversarial test suite:
```powershell
& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/test_challenger2_adversarial.py -v
```
Produced:
```
tests/test_challenger2_adversarial.py::test_capacitor_relative_routing_and_navigation FAILED [ 85%]

================================== FAILURES ===================================
_______________ test_capacitor_relative_routing_and_navigation ________________

AssertionError: Found broken absolute navigation links breaking Capacitor WKWebView: [('admin_mobile.html', '/saas_dashboard.html'), ('js/admin_users.js', '/trades?user=${u.id}')]. These must be relative (e.g. './admin_mobile.html' instead of '/admin/mobile', and './saas_dashboard.html').
assert not [('admin_mobile.html', '/saas_dashboard.html'), ('js/admin_users.js', '/trades?user=${u.id}')]
```

### 1.2 Exhaustive Codebase Audit Across All Static JavaScript Files
Scanned all JavaScript files in `static/js/` (`admin_users.js`, `app.js`, `dashboard.js`, `strategy_stats.js`, `lightweight-charts.js`) and `static/sw.js` for `<a>` tags, `.href` assignments, and navigation routes.

#### Finding 1: `static/js/admin_users.js:1382`
- **Location**: `static/js/admin_users.js`, line 1382
- **Current Content**:
```javascript
<a href="/trades?user=${u.id}" target="_blank" class="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all active:scale-95" title="Open full trade ledger in new tab">
```
- **Issue**: Absolute route `/trades?user=${u.id}` breaks iOS Capacitor WKWebView (`capacitor://localhost/`) because there is no root web server translating `/trades` to bundled `trades.html`.

#### Finding 2: `static/admin_mobile.html:92`
- **Location**: `static/admin_mobile.html`, line 92
- **Current Content**:
```html
<a href="/saas_dashboard.html" class="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white active:scale-95 transition-all py-1 px-2 rounded-lg bg-slate-800/60 border border-slate-700/60">
```
- **Issue**: The "Back to SaaS Dashboard" button uses an absolute URL (`/saas_dashboard.html`). In iOS WKWebView local bundle context, leading slash navigates away from the relative app root, failing Capacitor routing.

#### Finding 3: `static/js/app.js:5248`
- **Location**: `static/js/app.js`, line 5248
- **Current Content**:
```javascript
window.switchAsset = function(asset) {
    if (asset === 'FOREX') asset = 'EURUSD';
    if (window.currentAsset === asset) return;
    window.currentAsset = asset;
    
    const tradeListBtn = document.getElementById("btnOpenTradeList");
    if (tradeListBtn) {
        tradeListBtn.href = `/trades?asset=${asset}`;
    }
```
- **Issue**: When switching assets, `tradeListBtn.href` is dynamically assigned `/trades?asset=${asset}` (an absolute URL without `.html` extension), which would break navigation if clicked inside Capacitor WKWebView.

#### Finding 4: Passing Compliant Areas
- `static/js/dashboard.js`: Zero anchor tags or navigation mutations.
- `static/js/strategy_stats.js`: Zero anchor tags or navigation mutations.
- `static/login.html`: All 6 redirects already use relative `./admin_mobile.html` and `./saas_dashboard.html`.
- `static/saas_dashboard.html`: Admin navigation button (line 6063) already uses `./admin_mobile.html`.
- `static/trades.html`: All asset links and icons already use relative `./` paths.

---

## 2. Logic Chain

1. In iOS Capacitor WKWebView, local assets are bundled under `capacitor://localhost/` and served directly from the filesystem without a web server or path-rewriting reverse proxy (Observation 1.1).
2. Any link lacking a `.html` extension (e.g. `/trades` instead of `trades.html`) fails because no file or folder named `trades` exists in the local application bundle (Observation 1.1, 1.2.1, 1.2.3).
3. Any link starting with an absolute web root slash (e.g. `/saas_dashboard.html` or `/trades`) bypasses relative subdirectory resolution in WKWebView (Observation 1.2.1, 1.2.2).
4. `test_challenger2_adversarial.py` line 258 specifically asserts that all anchor tags across all HTML pages and JS templates contain no absolute paths (`assert not broken_absolute_links`).
5. Replacing `admin_users.js:1382` with `./trades.html?user=${u.id}`, `admin_mobile.html:92` with `./saas_dashboard.html`, and `app.js:5248` with `./trades.html?asset=${asset}` will completely satisfy Capacitor WKWebView routing requirements and immediately pass the test suite.

---

## 3. Caveats

- **Web Push Service Worker (`static/sw.js`)**: Lines 6, 20, 27 contain default URLs `/saas_dashboard.html`. Service Workers do not execute within native Capacitor WKWebView apps and are only active in standalone PWA mode. While safe in web PWA mode, worker implementers may optionally normalize these to `./saas_dashboard.html`.
- **Backend Route Aliasing (`backend/routes/ui.py`)**: While web browsers can resolve `/admin/mobile`, adding `@router.get("/admin_mobile.html")` above line 98 ensures consistency when web clients directly access the relative filename URL.
- **Read-Only Explorer Constraint**: In accordance with the Teamwork Explorer protocol, no source files were modified during this investigation.

---

## 4. Conclusion

The failures reported by Challenger 2 are verified and isolated to exactly two primary files, with one secondary dynamic link in `app.js` and an optional route alias in `backend/routes/ui.py`.

### Exact Fix Specifications for Implementer

#### Fix 1: `static/js/admin_users.js`
- **Line**: 1382
- **Target Content**:
```javascript
            <a href="/trades?user=${u.id}" target="_blank" class="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all active:scale-95" title="Open full trade ledger in new tab">
```
- **Replacement Content**:
```javascript
            <a href="./trades.html?user=${u.id}" target="_blank" class="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all active:scale-95" title="Open full trade ledger in new tab">
```

#### Fix 2: `static/admin_mobile.html`
- **Line**: 92
- **Target Content**:
```html
                <a href="/saas_dashboard.html" class="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white active:scale-95 transition-all py-1 px-2 rounded-lg bg-slate-800/60 border border-slate-700/60">
```
- **Replacement Content**:
```html
                <a href="./saas_dashboard.html" class="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white active:scale-95 transition-all py-1 px-2 rounded-lg bg-slate-800/60 border border-slate-700/60">
```

#### Fix 3: `static/js/app.js`
- **Line**: 5248
- **Target Content**:
```javascript
        tradeListBtn.href = `/trades?asset=${asset}`;
```
- **Replacement Content**:
```javascript
        tradeListBtn.href = `./trades.html?asset=${asset}`;
```

#### Fix 4 (Recommended): `backend/routes/ui.py`
- **Line**: 98
- **Target Content**:
```python
@router.get("/admin/mobile")
def get_admin_mobile():
```
- **Replacement Content**:
```python
@router.get("/admin/mobile")
@router.get("/admin_mobile.html")
def get_admin_mobile():
```

---

## 5. Verification Method

To verify these changes after implementation:

1. **Run the Adversarial Test Suite**:
   ```powershell
   & "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/test_challenger2_adversarial.py -v
   ```
   **Expected Result**: All 7 tests pass (7 PASSED, 0 FAILED), specifically:
   - `test_capacitor_relative_routing_and_navigation PASSED`

2. **Run Worker M3 Verification Suite**:
   ```powershell
   & "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/test_worker_m3_verification.py -v
   ```
   **Expected Result**: 8 PASSED, 0 FAILED.

3. **Verify File Contents Directly**:
   - In `static/js/admin_users.js:1382`, verify `href="./trades.html?user=${u.id}"`.
   - In `static/admin_mobile.html:92`, verify `href="./saas_dashboard.html"`.
   - In `static/js/app.js:5248`, verify `tradeListBtn.href = `./trades.html?asset=${asset}``.

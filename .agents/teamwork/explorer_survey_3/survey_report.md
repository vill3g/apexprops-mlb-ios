# Comprehensive Survey Report: Asset & Route Integrity (R3) and Auto Trader Logic & UI Integration (R4)

**Surveyor:** explorer_survey_3  
**Target Project:** ShadowTrader AI (`C:\Users\Vill3\Desktop\ShadowTraderAi`)  
**Date:** 2026-10-02  
**Investigation Mode:** Read-Only Audit & Survey  

---

## Executive Summary

This survey provides an exhaustive audit of two core pillars of the ShadowTrader AI application:
1. **Asset & Route Integrity (R3):** Exhaustive inventory of all static assets (images, icons, splash screens, sounds, fonts, JS/CSS bundles) referenced across HTML, CSS, JS, and Capacitor configs, verifying existence on disk, relative/absolute resolution in standard web browsers vs. the iOS Capacitor webview, and navigation routing.
2. **Auto Trader Logic & UI Integration (R4):** In-depth audit of the Auto Trader backend execution pipeline (order placement, execution loops, runaway prevention guards, API spamming risks, rate limiting, and thread safety) and its frontend UI integration (Dynamic Island glow, toggles, settings synchronization, high-frequency polling storms, and state consistency).

### Key Critical Findings
- **404 Asset Errors:** Broken references to non-existent `./assets/app_icon.ico` and `./assets/favicon.svg` in `login.html`, `trades.html`, and `backend/routes/ui.py` causing 404 network errors, a broken browser favicon, and the brand logo on the login page disappearing completely via `onerror="this.style.display='none'"`.
- **Capacitor Path Breakage:** Absolute asset paths (`/static/assets/...`) and absolute navigation links (`<a href="/admin/mobile">`) break inside the iOS Capacitor WKWebView because Capacitor packages `static/` as the root (`capacitor://localhost/`), where `/admin/mobile` and `/static/` directories do not exist.
- **Flawed Promise Error Handling in Data Fallbacks:** In `app.js`, `fetch('data/top5.json').catch(() => fetch('/static/data/top5.json'))` completely fails because HTTP 404 does NOT reject a JavaScript `fetch()` promise. The fallback never triggers, resulting in unhandled JSON parsing failures.
- **Runaway Loop & API Spamming on Kalshi 429:** In `backend/btc/auto_executor/executor.py` and `saas_broadcaster.py`, when a Kalshi order fails due to an HTTP 429 Rate Limit (or non-ambiguous rejection), `self.last_traded_interval` is NOT recorded. Because the background worker loops every 1 second, the engine immediately re-evaluates the same interval and bombards Kalshi with order requests every second for the entire 15-minute candle duration.
- **Lock Release Race Condition in Backend:** `check_and_execute_rollover()` releases `self._rollover_lock` during `exec_delay` before `last_traded_interval` is assigned, permitting concurrent threads to evaluate the same contract and stall the main worker loop.
- **Frontend Toggle & ID Mismatches:** JavaScript event handlers look for DOM elements `auto-trader-toggle`, `auto-trader-status`, and `header-auto-status` which do NOT exist in the DOM (only `header-auto-toggle` exists in the settings drawer).
- **Dynamic Island Glow Misalignment & Stale State:** The Dynamic Island indicator is positioned at `top: env(safe-area-inset-top, 12px)` (59px on modern iPhones), causing it to render below the physical Dynamic Island cutout, overlapping the header bar and Open Trade PnL text. When 1-Shot Snipe trades execute, the backend clears `one_shot_ai`, but the frontend polling never receives this update, leaving the toggle and glow permanently ON.
- **Client Polling Storm:** The frontend runs 6–8 uncoordinated HTTP intervals per second (`fetchLiveBids` every 800ms, `loadDashboard` every 1000ms, `fetchKalshiData` launching 3 concurrent requests every 1000ms, etc.), with `loadDashboard` continuing uninterrupted even when the mobile app is backgrounded (`document.hidden` not checked).

---

## Part 1: Asset & Route Integrity Survey (R3)

### 1.1 Complete Static Asset Inventory & Disk Verification

We conducted an automated and manual cross-reference of all files in `static/`, comparing every referenced asset against physical disk files in `static/`, `static/assets/`, and root `assets/`.

| Referenced Asset Path | Referenced In (File & Line) | Exists on Disk? | Physical Location / Resolution Status | Risk / Failure Mode |
|---|---|---|---|---|
| `./assets/app_icon.ico` | `static/login.html:51`<br>`static/trades.html:8`<br>`backend/routes/ui.py:40` | **NO (MISSING)** | Checked `static/assets/app_icon.ico` — file does not exist. (`static/favicon.ico` exists at root). | **HTTP 404**. In `ui.py`, `/favicon.ico` returns HTTP 404. Browser tabs show broken favicon. |
| `./assets/favicon.svg` | `static/login.html:50, 292`<br>`static/trades.html:7` | **NO (MISSING)** | Checked `static/assets/favicon.svg` — file does not exist anywhere in repo. | **HTTP 404**. On `login.html:292`, `<img src="./assets/favicon.svg" ... onerror="this.style.display='none'">` fails and disappears. Login page logo is missing. |
| `./favicon.ico` | `static/saas_dashboard.html:17` | **YES** | `static/favicon.ico` (15,611 bytes) | Valid when served from `static/`. |
| `./assets/app_icon_192.png` | `static/saas_dashboard.html:18` | **YES** | `static/assets/app_icon_192.png` (48,996 bytes) | Valid. |
| `/static/assets/apple-touch-icon.png` | `static/saas_dashboard.html:19`<br>`static/manifest.json:23` | **PARTIAL** | Exists at `static/assets/apple-touch-icon.png` (43,466 bytes) | Works on web server. **Fails in Capacitor iOS** where root is `capacitor://localhost/` without `/static/` prefix. |
| `/static/assets/splash_1290x2796.png` | `static/saas_dashboard.html:21` | **PARTIAL** | Exists at `static/assets/splash_1290x2796.png` (1.81 MB) | Works on web server. **Fails in Capacitor iOS** due to leading `/static/`. |
| `/static/assets/splash_1179x2556.png` | `static/saas_dashboard.html:22` | **PARTIAL** | Exists at `static/assets/splash_1179x2556.png` (1.61 MB) | Works on web server. **Fails in Capacitor iOS** due to leading `/static/`. |
| `/static/assets/splash_1170x2532.png` | `static/saas_dashboard.html:23` | **PARTIAL** | Exists at `static/assets/splash_1170x2532.png` (1.59 MB) | Works on web server. **Fails in Capacitor iOS** due to leading `/static/`. |
| `/static/assets/splash_1242x2688.png` | `static/saas_dashboard.html:24` | **PARTIAL** | Exists at `static/assets/splash_1242x2688.png` (1.72 MB) | Works on web server. **Fails in Capacitor iOS** due to leading `/static/`. |
| `/static/assets/splash_828x1792.png` | `static/saas_dashboard.html:25` | **PARTIAL** | Exists at `static/assets/splash_828x1792.png` (985 KB) | Works on web server. **Fails in Capacitor iOS** due to leading `/static/`. |
| `/static/assets/splash_1125x2436.png` | `static/saas_dashboard.html:26` | **PARTIAL** | Exists at `static/assets/splash_1125x2436.png` (1.51 MB) | Works on web server. **Fails in Capacitor iOS** due to leading `/static/`. |
| `/static/assets/splash_750x1334.png` | `static/saas_dashboard.html:27` | **PARTIAL** | Exists at `static/assets/splash_750x1334.png` (767 KB) | Works on web server. **Fails in Capacitor iOS** due to leading `/static/`. |
| `/static/assets/splash_640x1136.png` | `static/saas_dashboard.html:28` | **PARTIAL** | Exists at `static/assets/splash_640x1136.png` (595 KB) | Works on web server. **Fails in Capacitor iOS** due to leading `/static/`. |
| `./assets/splash.png` | `static/saas_dashboard.html:420` | **YES** | `static/assets/splash.png` (736 KB) | Valid across web and Capacitor. |
| `./assets/icon.png` | `static/saas_dashboard.html:473, 503` | **YES** | `static/assets/icon.png` (327 KB) | Valid across web and Capacitor. |
| `./manifest.json` | `static/saas_dashboard.html:15`<br>`static/login.html:49` | **YES** | `static/manifest.json` (628 bytes) | Valid. |
| `./css/dashboard.css` | `static/saas_dashboard.html:507` | **YES** | `static/css/dashboard.css` (275 bytes) | Valid. |
| `./js/lightweight-charts.js` | `static/saas_dashboard.html:309` | **YES** | `static/js/lightweight-charts.js` (163 KB) | Valid. |
| `./js/app.js` | `static/saas_dashboard.html:6340` | **YES** | `static/js/app.js` (263 KB) | Valid. |
| `./js/admin_users.js` | `static/saas_dashboard.html:6341` | **YES** | `static/js/admin_users.js` (118 KB) | Valid. |
| `./js/strategy_stats.js` | `static/saas_dashboard.html:6342` | **YES** | `static/js/strategy_stats.js` (2.35 KB) | Valid. |
| `/static/sw.js` | `static/js/dashboard.js:275` | **YES (ON DISK)** | `static/sw.js` (1.43 KB) | **Scope error**. Service Worker registered from `/static/sw.js` cannot control root `/` or `/saas_dashboard.html`. |
| `https://moneyprinter.ngrok.app/...` | `static/saas_dashboard.html:2059, 2267`<br>`static/js/admin_users.js:905, 906, 1308, 1309` | **EXTERNAL** | Hardcoded ngrok domain for profile pictures. | **Fails offline/LAN**. Fails when ngrok tunnel is down or domain expires. |
| `data/top5.json` | `static/js/app.js:630` | **NO AT RELATIVE PATH** | Exists at `static/data/top5.json`. | **404 Silent Failure**. `fetch('data/top5.json')` returns 404; `.catch(...)` fails to trigger because fetch doesn't reject on 404. |
| `data/props.json` | `static/js/app.js:635` | **NO AT RELATIVE PATH** | Exists at `static/data/props.json`. | **404 Silent Failure**. Same promise catch bug. |
| `data/pitchers.json` | `static/js/app.js:661` | **NO AT RELATIVE PATH** | Exists at `static/data/pitchers.json`. | **404 Silent Failure**. Same promise catch bug. |

---

### 1.2 Route & Navigation Integrity (Web vs iOS Capacitor)

#### Issue 1.2.1: Favicon Route 404 in `backend/routes/ui.py`
- **Location:** `backend/routes/ui.py:37-43`
```python
@router.api_route("/favicon.ico", methods=["GET", "HEAD"])
def serve_root_favicon():
    ico_path = os.path.join(STATIC_DIR, "assets", "app_icon.ico")
    if os.path.exists(ico_path):
        return FileResponse(ico_path, media_type="image/x-icon")
    return Response(status_code=404)
```
- **Root Cause:** The handler joins `STATIC_DIR` with `"assets/app_icon.ico"`. However, the file on disk is `STATIC_DIR/favicon.ico`. Because `STATIC_DIR/assets/app_icon.ico` does not exist, `os.path.exists(ico_path)` evaluates to `False`, and the backend returns `404 Not Found` for every browser favicon request.
- **Fix:** Update path to `os.path.join(STATIC_DIR, "favicon.ico")`.

#### Issue 1.2.2: Hardcoded Absolute Link `<a href="/admin/mobile">` in Capacitor
- **Location:** `static/saas_dashboard.html:6077`
```html
<a href="/admin/mobile" class="...">Admin Console</a>
```
- **Root Cause:** In a standard web browser connected to the server, `/admin/mobile` is handled by FastAPI (`backend/routes/ui.py:98`) which serves `admin_mobile.html`. However, in Capacitor on iOS (`capacitor://localhost/`), navigation occurs within the local file bundle. Capacitor's local web server only maps files that physically exist in the `webDir` (`static/`). There is no file or folder named `admin/mobile`. When tapped inside the iOS app, the WKWebView navigates to `capacitor://localhost/admin/mobile`, returning a file not found error / blank screen.
- **Fix:** Change `href="/admin/mobile"` to `href="./admin_mobile.html"`. In `backend/routes/ui.py`, retain `/admin/mobile` for server routes, but provide client navigation with relative `.html` extensions.

#### Issue 1.2.3: Inconsistent Route Prefixes in Navigation
- **Location:** `static/admin_mobile.html:92`
```html
<a href="/saas_dashboard.html" class="...">Dashboard</a>
```
vs `static/login.html:86, 114`
```javascript
window.location.replace("./saas_dashboard.html");
```
- **Root Cause:** Leading slashes (`/saas_dashboard.html`) assume the root origin is the site root. When packaged inside Capacitor or embedded subdirectories, absolute paths can resolve to the device domain or break relative subpath scoping.
- **Fix:** Standardize all internal page links to use `./` relative paths (`./saas_dashboard.html`, `./login.html`, `./admin_mobile.html`).

#### Issue 1.2.4: Broken Data Fetch Fallback in `app.js`
- **Location:** `static/js/app.js:629-641, 660-670`
```javascript
const tRes = await fetch('data/top5.json').catch(() => fetch('/static/data/top5.json'));
const tData = await tRes.json();
```
- **Root Cause:** In the standard JavaScript Fetch API, HTTP 404 responses do NOT reject the promise—they resolve with `res.ok = false` and `res.status = 404`. Therefore, `.catch(() => fetch('/static/data/top5.json'))` NEVER triggers when `data/top5.json` returns 404. The code proceeds immediately to `await tRes.json()`, which either parses the 404 error payload `{"detail":"Not Found"}` or throws a `SyntaxError: Unexpected token '<'`, leaving `top5Picks` as `undefined` or crashing the caller.
- **Fix:** Implement proper status checking:
```javascript
let tRes = await fetch('./data/top5.json').catch(() => null);
if (!tRes || !tRes.ok) {
    tRes = await fetch('/static/data/top5.json').catch(() => null);
}
if (tRes && tRes.ok) {
    const tData = await tRes.json();
    top5Picks = tData.top_5 || [];
    renderTop5(top5Picks);
}
```

#### Issue 1.2.5: Service Worker Registration Scope Mismatch
- **Location:** `static/js/dashboard.js:275`
```javascript
const registration = await navigator.serviceWorker.register('/static/sw.js');
```
- **Root Cause:** Under the W3C Service Worker specification, a service worker file registered at path `/static/sw.js` has a default maximum scope of `/static/`. It cannot control clients at root `/` or `/saas_dashboard.html` unless served with a specific `Service-Worker-Allowed: /` HTTP header or registered directly from the root `/sw.js`. In `backend/main.py`, there is no route serving `/sw.js` at the root, and FastAPI's `StaticFiles` mount does not inject `Service-Worker-Allowed`.
- **Fix:** Serve `sw.js` via a dedicated FastAPI endpoint at `/sw.js` with `headers={"Service-Worker-Allowed": "/"}` and update registration to `navigator.serviceWorker.register('/sw.js')`.

#### Issue 1.2.6: Startup Race Condition in API Detection (`initApiBackend`)
- **Location:** `static/saas_dashboard.html:34-75`
```javascript
(async function initApiBackend() {
    ...
    const res = await originalFetch(localUrl + "/api/health", { signal: controller.signal, mode: "no-cors" }).catch(e => null);
    ...
    window.fetch = async function() { ... };
})();
```
- **Root Cause:** `initApiBackend` is an asynchronous IIFE that awaits a network ping with a 1200ms timeout before patching `window.fetch`. Synchronous scripts or early deferred scripts (such as `app.js` or inline modules) that initiate `fetch("/api/...")` during the first 1200ms execute using the unpatched global `fetch` with an empty `window.API_BASE_URL`. In Capacitor, these early requests go to `capacitor://localhost/api/...` which results in an immediate network error.
- **Fix:** Override `window.fetch` synchronously before beginning the async ping, using a deferred promise or queuing early requests until backend URL resolution completes.

---

## Part 2: Auto Trader Logic & UI Integration Survey (R4)

### 2.1 Backend Auto Trader Execution Logic

The Auto Trader backend operates via two primary entry points in `backend/worker.py`:
1. `AutoExecutor.check_and_execute_rollover()` (`backend/btc/auto_executor/executor.py:600`) — Master/Admin single-user trade execution at the 15-minute candle boundary.
2. `SaasBroadcasterMixin.evaluate_and_execute_saas_users()` (`backend/btc/auto_executor/saas_broadcaster.py:335`) — Multi-tenant execution for registered SaaS users.

#### Finding 2.1.1: Runaway Execution Loop & Kalshi API Spamming on HTTP 429
- **Files & Lines:**
  - `backend/btc/auto_executor/executor.py:653-656, 1147, 1228-1240`
  - `backend/btc/auto_executor/saas_broadcaster.py:400-402, 963-964, 1094-1096`
  - `backend/worker.py:61-90`
- **Observed Code:**
In `backend/worker.py:61-90`:
```python
while True:
    for asset in ["BTC", "ETH", "GOLD"]:
        ae = get_auto_executor(asset)
        ae.check_and_execute_rollover()
        ae.evaluate_and_execute_saas_users()
    time.sleep(1)
```
In `backend/btc/auto_executor/executor.py:653-656`:
```python
current_interval_id = active_m.get("ticker") or active_m.get("event_ticker", "")
if not current_interval_id or current_interval_id == self.last_traded_interval:
    logger.debug(f"[AutoExecutor] Skipping because interval is last_traded_interval: {current_interval_id}")
    return None
```
In `backend/btc/auto_executor/executor.py:1147` & `1228-1240`:
```python
if order_res.get("success", False):
    ...
    self.last_traded_interval = current_interval_id
else:
    if order_res.get("ambiguous"):
        self.last_traded_interval = current_interval_id
    else:
        logger.error(f"[AutoExecutor] Order failed: {order_res.get('error')}")
    return None
```
- **Mechanism of Failure (Logic Chain):**
  1. The worker loop executes every 1 second.
  2. `check_and_execute_rollover()` checks `if current_interval_id == self.last_traded_interval`.
  3. At rollover, conviction criteria are met, and `kalshi_trader.place_order()` is called.
  4. Kalshi returns HTTP 429 ("Too Many Requests") or rejects the order.
  5. `order_res.get("success")` is `False`, and `order_res.get("ambiguous")` is `False`.
  6. The `else` block logs the error, but **NEVER updates `self.last_traded_interval`**.
  7. Exactly 1 second later, the worker loops again. `current_interval_id == self.last_traded_interval` is still `False`.
  8. The engine re-evaluates the market, re-runs ML inference, and **submits another order to Kalshi**.
  9. This repeats every single second for the remaining 14+ minutes of the 15-minute interval.
  10. **Result:** An active rate-limit runaway loop that floods the Kalshi REST API with 60 order requests per minute while the account is already throttled, risking account suspension.
- **Multi-Tenant Parallel in `saas_broadcaster.py`:**
  In `saas_broadcaster.py:963`, if a live order fails:
  ```python
  if not res.get('success'):
      if res.get('ambiguous'): ...
      else: inflight_orders.clear(user['id'], current_interval_id, side)
      return
  ```
  `_user_last_traded_cache[(user['id'], self.asset)]` is at line 1095, which is never reached. `evaluate_and_execute_saas_users()` checks every 4 seconds (`(now_ts - self._last_saas_eval_time) < 4.0`), meaning failed users are re-evaluated and re-ordered every 4 seconds.
- **Risk Severity:** **CRITICAL**. High probability of API bans and server CPU saturation.
- **Fix:** Record failed attempts with an exponential backoff / interval failure marker:
```python
else:
    if order_res.get("ambiguous") or "429" in str(order_res.get("error")) or "Rejected" in str(order_res.get("error")):
        # Mark interval as attempted to halt runaway retries
        self.last_traded_interval = current_interval_id
        self._record_interval_failure(current_interval_id, order_res.get("error"))
```

---

#### Finding 2.1.2: Lock Release Race Condition & Main Thread Stall via `execDelay`
- **File & Lines:** `backend/btc/auto_executor/executor.py:1056-1068`
```python
exec_delay = int(self.ai_settings.get("execDelay", 0))
if exec_delay > 0:
    logger.info(f"[AutoExecutor] Delaying execution by {exec_delay}s (lock released during wait)...")
    self._rollover_lock.release()
    lock_held = False
    try:
        time.sleep(exec_delay)
    finally:
        lock_held = self._rollover_lock.acquire(blocking=True, timeout=10)
        if not lock_held:
            logger.error("[AutoExecutor] Could not re-acquire rollover lock after exec_delay sleep; aborting trade.")
            return None
```
- **Mechanism of Failure:**
  1. `worker.py` runs `check_and_execute_rollover()` synchronously on the worker thread.
  2. If a user sets `execDelay = 5`, `time.sleep(5)` blocks the worker thread for 5 full seconds. During this window, `ETH` and `GOLD` rollover checks are frozen, `settle_saas_trades()` is delayed, and `evaluate_and_execute_saas_users()` cannot run.
  3. When `self._rollover_lock.release()` is called, the lock is freed **before `self.last_traded_interval` is set**.
  4. If an external API request (e.g. from `/api/engine/btc/trade/manual` or another thread) invokes `check_and_execute_rollover()` during this 5-second sleep, it passes all gates and enters execution for the identical interval.
- **Fix:** Do not execute synchronous `time.sleep()` within the main worker loop. Offload delayed orders to a background `threading.Timer` or schedule queue, and set an `inflight_interval` flag before releasing locks.

---

#### Finding 2.1.3: Concurrency Bypass for Paper Trading Orders
- **File & Lines:** `backend/btc/auto_executor/executor.py:1098-1107`
```python
intent_key = None
if not dry_run:
    intent_key = order_intents.account_key_for_executor(getattr(self, '_guest_id', None))
    if not order_intents.claim(intent_key, current_interval_id, side):
        ...
        return None
```
- **Mechanism of Failure:**
  `dry_run` is set to `True` for paper mode (`dry_run = (self.mode == "PAPER")`). SQLite-backed `order_intents.claim()` is explicitly bypassed for paper trading. If two requests arrive in close succession (or during `execDelay`), multiple paper orders execute for the exact same interval.
- **Fix:** Extend `order_intents` claim verification to paper trading using a distinct namespace (`intent_key = f"paper:{intent_key}"`).

---

### 2.2 Auto Trader Frontend UI Integration

#### Finding 2.2.1: Disconnected DOM Element IDs in Auto Trader Toggles
- **File & Lines:** `static/saas_dashboard.html:1320-1326, 1590-1593, 5344`
```javascript
// In toggleAutoTrader():
const autoToggle = document.getElementById('auto-trader-toggle');
const autoStatus = document.getElementById('auto-trader-status');
const headerToggle = document.getElementById('header-auto-toggle');
const headerStatus = document.getElementById('header-auto-status');

if(autoToggle) autoToggle.checked = enabled;
if(headerToggle) headerToggle.checked = enabled;
```
- **Observed DOM Structure:**
  In `saas_dashboard.html:5344` (inside Settings sheet):
  `<input type="checkbox" id="header-auto-toggle" ...>`
  Search for `id="auto-trader-toggle"` in DOM: **0 matches (Does not exist)**.
  Search for `id="auto-trader-status"` in DOM: **0 matches (Does not exist)**.
  Search for `id="header-auto-status"` in DOM: **0 matches (Does not exist)**.
- **Impact:**
  - The toggle inside the settings drawer is named `header-auto-toggle` despite being in the drawer, while `auto-trader-toggle` does not exist.
  - The status labels `auto-trader-status` and `header-auto-status` fail silently (`document.getElementById` returns `null`).
  - Meanwhile, the actual header has `<span id="nav-auto-badge">AUTO OFF</span>` (line 497), but `toggleAutoTrader()` **never updates `nav-auto-badge`**.
- **Fix:** Correct the DOM ID references: in `toggleAutoTrader()`, update `nav-auto-badge` immediately:
```javascript
const navBadge = document.getElementById('nav-auto-badge');
if (navBadge) {
    navBadge.innerText = enabled ? 'AUTO ON' : 'AUTO OFF';
    navBadge.className = enabled ? 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 leading-none shadow-sm' : 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-700 leading-none shadow-sm';
}
```

---

#### Finding 2.2.2: Dynamic Island Glow Positioning & State Sync Bug
- **File & Lines:** `static/saas_dashboard.html:424-429, 445-465, 984-998`
```html
<div id="dynamic-island" class="fixed top-0 left-1/2 -translate-x-1/2 z-[9999] pointer-events-none" style="top: env(safe-area-inset-top, 12px);">
    <div id="dynamic-island-pill" class="relative flex items-center gap-1.5 px-3 py-1 rounded-full bg-black border border-white/10 transition-all duration-500 opacity-0" style="min-width:80px; justify-content:center;">
        <span id="di-dot" class="w-2 h-2 rounded-full bg-emerald-400 shrink-0" style="box-shadow:0 0 8px 2px rgba(52,211,153,0.8);"></span>
        <span id="di-label" class="text-[10px] font-black text-emerald-300 tracking-widest uppercase">AUTO ON</span>
    </div>
</div>
```
- **Defects Identified:**
  1. **Safe Area Miscalculation:** Modern iPhones with Dynamic Island (14 Pro through 16) report `env(safe-area-inset-top)` as `59px`. The physical Dynamic Island cutout occupies the vertical slice from `11px` to `48px`. Setting `top: env(safe-area-inset-top, 12px)` positions the glowing pill at `59px`—**directly below the notch in the middle of the main header**, overlapping the `nav-live-pnl-container` (Open Trade PnL) element. To sit inside/around the physical cutout, `top: max(8px, calc(env(safe-area-inset-top, 0px) * 0.18))` or a calibrated offset (`top: 11px`) is required.
  2. **Setting Toggle Desynchronization:** In `window.toggleDynamicIslandSetting(enabled)` (line 985), toggling the setting to `true` saves `localStorage.setItem('di_enabled', 'true')`, but **never calls `updateDynamicIsland()` with the current trading state**. If Auto Trader was already enabled, the glow pill remains at `opacity: 0` until a future reload.
  3. **1-Shot Snipe Mode Desync:** When 1-Shot Snipe mode fires, the backend executes the trade and resets `one_shot_ai = 0` / `oneShotAiStartTrade = False` in the database. However, the frontend polling loop (`loadDashboard()`) fetches `/api/auth/dashboard_stats`, which does not return `one_shot_ai`. Consequently, the frontend never learns that the 1-shot trade completed: the toggle remains checked and the Dynamic Island glow remains active indefinitely.

---

#### Finding 2.2.3: Hardcoded `BTC` in `loadConfig()` Wiping Active Asset Toggles
- **File & Lines:** `static/saas_dashboard.html:1342, 1583`
In `toggleAutoTrader(enabled)`:
```javascript
const curA = (window.currentAsset || 'BTC').toLowerCase();
const res = await fetch(`/api/engine/${curA}/trade/toggle?enabled=${enabled}`, ...);
```
In `loadConfig()`:
```javascript
const res = await fetch('/api/engine/btc/trade/config', ...); // HARDCODED BTC!
```
- **Mechanism of Failure:**
  When a user switches to `ETH` or `GOLD` via the asset selector and toggles Auto Trader, the POST request correctly toggles `/api/engine/eth/trade/toggle`. However, when `loadConfig()` runs (e.g. on error recovery or drawer open), it unconditionally queries `/api/engine/btc/trade/config`. If `BTC` Auto Trader is OFF while `ETH` is ON, `loadConfig()` receives `c.enabled = false` from BTC and **overwrites the UI toggles, flipping the ETH UI toggle back to OFF**.
- **Fix:** Update `loadConfig()` to use dynamic asset resolution:
```javascript
const curA = (window.currentAsset || 'BTC').toLowerCase();
const res = await fetch(`/api/engine/${curA}/trade/config`, ...);
```

---

#### Finding 2.2.4: Discrepancy Between `GET /trade/config` and `GET /trade/ai_settings`
- **File & Lines:** `backend/routes/engine.py:700-733, 800-806`
In `api_btc_trade_config_get` (line 705):
```python
guest_id = None if is_owner else (_get_guest_id(request) if request else None)
ex = get_auto_executor(asset, guest_id=guest_id)
# For authenticated registered SaaS users, guest_id is None!
# This returns the MASTER AutoExecutor's ai_settings!
```
In `api_btc_trade_ai_settings_get` (line 804):
```python
target_id = str(user_id) if user_id else guest_id
return JSONResponse(get_auto_executor(asset, guest_id=target_id).ai_settings)
```
- **Impact:** When a registered user fetches `/trade/config`, they receive the global Master executor's settings. When they fetch `/trade/ai_settings`, they receive their isolated user executor's settings. Any UI component querying `/trade/config` gets desynchronized from `/trade/ai_settings`.
- **Fix:** In `api_btc_trade_config_get`, resolve `target_id = str(user_id) if user_id else guest_id` so registered users consistently receive their own configuration.

---

#### Finding 2.2.5: Client Polling Storm & Background Battery Drain
- **File & Lines:** `static/saas_dashboard.html:1933, 2875-2877, 4320, 4380, 4804` and `static/js/app.js:438, 592, 1372, 4955, 4995, 5420`
- **Active Periodic Timers in Single Session:**
  1. `setInterval(fetchLiveBids, 800)` — every 800ms
  2. `setInterval(loadDashboard, 1000)` — every 1000ms
  3. `setInterval(fetchKalshiData, 1000)` — every 1000ms (dispatches 3 parallel sub-fetches: `/kalshi`, `/countdown`, `/ticker`)
  4. `_live1sTimer = setInterval(..., 1000)` in `app.js` — every 1000ms
  5. `chartRefreshInterval = setInterval(fetchChartData, 1500)` in `app.js` — every 1500ms
  6. `pollKalshiTradingStatus = setInterval(..., 1500)` in `app.js` — every 1500ms
  7. `pollGlobalTicker = setInterval(..., 1500)` in `app.js` — every 1500ms
  8. `fetchBattleTape = setInterval(..., 8000)` — every 8s
  9. `fetchDailyQuests = setInterval(..., 12000)` — every 12s
- **Cumulative Traffic:** ~7 to 9 HTTP requests per second continuously.
- **Background Drain:** While `app.js` lines check `if (document.hidden) return`, `loadDashboard()` in `saas_dashboard.html:1933` has **NO visibility check**. When an iPhone user locks their phone or switches apps, the webview continues issuing `/api/auth/dashboard_stats` requests, causing thermal load, battery drain, and excessive server log generation.
- **Fix:**
  - Consolidate polling into a single coordinated 1.5s ticker loop.
  - Wrap all dashboard fetches with `if (document.hidden || !window.isTabActive) return;`.

---

## Part 3: Actionable Fix Specifications Matrix

| ID | Component | File Path & Lines | Defect Summary | Recommended Concrete Fix |
|---|---|---|---|---|
| **F-01** | Assets | `backend/routes/ui.py:40`<br>`static/login.html:51`<br>`static/trades.html:8` | Missing `./assets/app_icon.ico` causing 404 on `/favicon.ico` | Point `ico_path` to `os.path.join(STATIC_DIR, "favicon.ico")`. Update HTML `<link rel="icon">` to `./favicon.ico`. |
| **F-02** | Assets | `static/login.html:50, 292`<br>`static/trades.html:7` | Missing `./assets/favicon.svg` causing broken logo and 404 | Change image source on `login.html:292` to `./assets/logo.png` or `./assets/icon.png`. Remove non-existent `.svg` link. |
| **F-03** | Routing | `static/saas_dashboard.html:6077` | `<a href="/admin/mobile">` fails inside Capacitor | Change to `<a href="./admin_mobile.html">`. |
| **F-04** | Assets / PWA | `static/saas_dashboard.html:19, 21-28`<br>`static/manifest.json:11, 17, 23` | Absolute `/static/assets/...` paths fail in Capacitor iOS | Change to relative `./assets/...` paths across all link and manifest tags. |
| **F-05** | Service Worker | `static/js/dashboard.js:275`<br>`backend/main.py` | Scope mismatch for `/static/sw.js` | Add root endpoint `@app.get("/sw.js")` with `Service-Worker-Allowed: /` header; register via `/sw.js`. |
| **F-06** | Data Fetch | `static/js/app.js:630, 635, 661` | `.catch(...)` fails to catch 404 response in `fetch` | Replace `.catch()` with explicit `if (!res.ok)` check before parsing JSON. |
| **F-07** | Backend Auto Trader | `backend/btc/auto_executor/executor.py:1228-1240`<br>`backend/btc/auto_executor/saas_broadcaster.py:963` | Runaway loop on Kalshi HTTP 429 spamming orders every second | Mark `self.last_traded_interval = current_interval_id` on non-retryable/rate-limit errors with exponential backoff. |
| **F-08** | Backend Auto Trader | `backend/btc/auto_executor/executor.py:1056-1068` | `execDelay` lock release permits duplicate executions | Keep lock held or flag interval as pending before sleep; avoid blocking main worker thread. |
| **F-09** | Backend Auto Trader | `backend/btc/auto_executor/executor.py:1098` | Paper orders bypass `order_intents.claim` | Apply `order_intents.claim` to paper orders to prevent duplicate simultaneous executions. |
| **F-10** | Frontend UI | `static/saas_dashboard.html:1320-1326, 1610` | Disconnected DOM IDs and header badge not updating | Update `nav-auto-badge` directly inside `toggleAutoTrader()`. |
| **F-11** | Frontend UI | `static/saas_dashboard.html:424` | Dynamic Island positioned at 59px overlapping header | Adjust top positioning to align cleanly with physical notch. |
| **F-12** | Frontend UI | `static/saas_dashboard.html:1583` | `loadConfig()` hardcodes `btc`, overriding other asset toggles | Change `/api/engine/btc/trade/config` to `/api/engine/${curA}/trade/config`. |
| **F-13** | Backend Routes | `backend/routes/engine.py:707, 804` | Config endpoint desync between registered user and master | Ensure `api_btc_trade_config_get` inspects `user_id` when fetching executor config. |
| **F-14** | Performance / Polling | `static/saas_dashboard.html:1933, 2875` | 6–8 requests/sec polling storm and background drain | Add `if (document.hidden) return;` to `loadDashboard()` and coalesce polling loops. |

---

## Part 4: Conclusion & Architecture Synthesis

The survey reveals that while the core ML prediction and risk-management algorithms (Kelly criterion, loss analyzers, candlestick detectors) are mathematically sophisticated, the operational reliability of the system is compromised by:
1. **Packaging & Path Assumptions:** Absolute paths (`/static/...`, `/admin/mobile`) designed for standard HTTP servers conflict directly with Capacitor's local webview bundling on iOS.
2. **Error Boundary Omissions:** The execution loop in `executor.py` and `saas_broadcaster.py` assumes that any failed order placement is safe to retry on the next 1-second tick, turning upstream rate limits (Kalshi 429) into destructive runaway loops.
3. **Frontend State Cohesion:** The dashboard UI uses multiple overlapping timers and mismatched DOM IDs that lead to state drift between the frontend controls and the backend state.

Implementing the 14 targeted fixes documented above will eliminate all 404 network errors, ensure full iOS Capacitor compatibility, safeguard against API runaway loops, and provide seamless, battery-friendly state synchronization.

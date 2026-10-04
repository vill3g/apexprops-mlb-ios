# Handoff Report: Explorer Survey 3

**Agent:** explorer_survey_3  
**Working Directory:** `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_3`  
**Report Type:** Hard Handoff (Investigation & Survey Complete)  
**Date:** 2026-10-02  
**Detailed Companion Report:** `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_3\survey_report.md`  

---

## 1. Observation

Direct observations and evidence from code analysis and disk verification:

1. **Missing Favicon and Brand Logo Assets:**
   - In `backend/routes/ui.py:40-43`:
     ```python
     ico_path = os.path.join(STATIC_DIR, "assets", "app_icon.ico")
     if os.path.exists(ico_path):
         return FileResponse(ico_path, media_type="image/x-icon")
     return Response(status_code=404)
     ```
     `static/assets/app_icon.ico` does not exist on disk. `static/favicon.ico` exists at `15,611 bytes`. Therefore `/favicon.ico` unconditionally returns `404 Not Found`.
   - In `static/login.html:50, 292`:
     ```html
     <link rel="icon" type="image/svg+xml" href="./assets/favicon.svg">
     ...
     <img src="./assets/favicon.svg" alt="Kalshi AI Logo" class="brand-logo" onerror="this.style.display='none'">
     ```
     `static/assets/favicon.svg` does not exist anywhere in the repository. The brand logo `<img>` fires `onerror` and hides itself on every login page load.
   - In `static/trades.html:7-8`:
     ```html
     <link rel="icon" type="image/svg+xml" href="./assets/favicon.svg">
     <link rel="alternate icon" href="./assets/app_icon.ico">
     ```
     Both referenced icon files do not exist on disk.

2. **Capacitor Absolute Path and Route Failures:**
   - In `static/saas_dashboard.html:6077`:
     ```html
     <a href="/admin/mobile" class="...">Admin Console</a>
     ```
     In iOS Capacitor (`capacitor://localhost/`), there is no directory or file `admin/mobile`. Clicking this link navigates to `capacitor://localhost/admin/mobile`, returning a 404/blank screen. The file is `admin_mobile.html`.
   - In `static/saas_dashboard.html:19, 21-28`:
     `<link rel="apple-touch-icon" sizes="180x180" href="/static/assets/apple-touch-icon.png">`
     `<link rel="apple-touch-startup-image" ... href="/static/assets/splash_1290x2796.png">`
     Leading `/static/` fails in Capacitor WKWebView where assets reside under `capacitor://localhost/assets/...`.

3. **Silent Data Fetch Fallback Failure:**
   - In `static/js/app.js:630, 635, 661`:
     ```javascript
     const tRes = await fetch('data/top5.json').catch(() => fetch('/static/data/top5.json'));
     const tData = await tRes.json();
     ```
     `fetch('data/top5.json')` returns HTTP 404 from FastAPI because `/data` is not mounted at root. In JavaScript Fetch API, HTTP 404 does NOT reject the promise; `.catch(...)` never runs. `tRes.json()` parses the 404 response body, leaving `top5Picks` as `undefined` or throwing `SyntaxError`.

4. **Runaway Loop & API Spamming on Kalshi HTTP 429:**
   - In `backend/worker.py:61-90`:
     The loop iterates over `["BTC", "ETH", "GOLD"]`, calling `ae.check_and_execute_rollover()` every 1 second (`time.sleep(1)`).
   - In `backend/btc/auto_executor/executor.py:653-656, 1147, 1228-1240`:
     ```python
     if current_interval_id == self.last_traded_interval:
         return None
     ...
     order_res = kalshi_trader.place_order(...)
     if order_res.get("success", False):
         self.last_traded_interval = current_interval_id
     else:
         if order_res.get("ambiguous"):
             self.last_traded_interval = current_interval_id
         else:
             logger.error(f"[AutoExecutor] Order failed: {order_res.get('error')}")
         return None
     ```
     When Kalshi throttles orders with HTTP 429 (Too Many Requests), `order_res.get("success")` is `False` and `ambiguous` is `False`. `self.last_traded_interval` is NOT set. One second later, the worker re-evaluates the market, re-runs ML conviction, and sends another order to Kalshi. This repeats every second for the entire 15-minute interval.
   - Similarly, in `backend/btc/auto_executor/saas_broadcaster.py:963-964, 1094-1096`:
     If a live order fails, line 964 executes `return` without updating `_user_last_traded_cache`. Every 4 seconds, `evaluate_and_execute_saas_users()` retries the failed user against Kalshi.

5. **Lock Release Concurrency Hole:**
   - In `backend/btc/auto_executor/executor.py:1056-1068`:
     If `execDelay > 0`, `self._rollover_lock.release()` is called and `time.sleep(exec_delay)` freezes the main worker thread for up to several seconds while leaving `self.last_traded_interval` unset, allowing concurrent executions of the same contract.

6. **Frontend State Desynchronization and Polling Storm:**
   - In `static/saas_dashboard.html:1320-1326`: `toggleAutoTrader()` references non-existent elements `auto-trader-toggle`, `auto-trader-status`, `header-auto-status`. It fails to update `nav-auto-badge` (line 497).
   - In `static/saas_dashboard.html:1583`: `loadConfig()` hardcodes `/api/engine/btc/trade/config`, wiping toggles when viewing `ETH` or `GOLD`.
   - In `backend/btc/auto_executor/executor.py:1216` & `saas_broadcaster.py:874`: `one_shot_ai` is reset to 0 in the backend upon execution, but frontend `dashboard_stats` polling never returns `one_shot_ai`, leaving the 1-Shot Snipe toggle and Dynamic Island glow stuck ON in the UI.
   - In `static/saas_dashboard.html:1933, 2875`: 7–9 HTTP requests are dispatched every second. `loadDashboard()` runs every 1000ms with no `document.hidden` check, polling continuously in the background on mobile.

---

## 2. Logic Chain

1. From **Observation 1**, `app_icon.ico` and `favicon.svg` do not exist anywhere in the filesystem. When referenced in HTML `<link>` and `<img>` tags and the FastAPI `/favicon.ico` handler, browsers make HTTP requests that fail with status 404. On the login page, the logo image tag has `onerror="this.style.display='none'"`, causing the visual branding to collapse and disappear.
2. From **Observation 2**, Capacitor serves web assets via WKWebView at origin `capacitor://localhost/` directly from the `static/` directory specified by `webDir`. Paths with leading `/static/` resolve to `capacitor://localhost/static/...` which do not exist in the packaged root. Links pointing to `/admin/mobile` expect a server-side route rather than a local HTML file. On web, FastAPI routes `/admin/mobile` to `admin_mobile.html`, but on native iOS Capacitor, the request fails with a 404 because Capacitor acts as a static file server.
3. From **Observation 3**, the ECMAScript Fetch specification dictates that `.catch()` only handles network rejection (DNS failure, offline, aborted request), not HTTP 4xx/5xx responses. Because `fetch('data/top5.json')` returns a 404 response object, the fallback chained in `.catch()` never executes, and subsequent attempts to parse the payload as JSON fail.
4. From **Observation 4**, the background worker loop runs synchronously every 1 second in `worker.py`. The only gate preventing repeated orders on the same 15-minute contract is `current_interval_id == self.last_traded_interval`. Because this variable is only updated on order success or ambiguous timeout, any rate limit (HTTP 429) or non-ambiguous rejection leaves the variable unset. Consequently, the loop treats the interval as untraded on every subsequent 1-second tick, causing a persistent runaway loop that floods Kalshi's API with order placement requests.
5. From **Observation 5**, releasing `_rollover_lock` during `execDelay` before marking the interval as traded creates a race window where another thread or manual execution can evaluate and submit orders for the same contract.
6. From **Observation 6**, the mismatch between element IDs in JavaScript and the HTML DOM, combined with hardcoded `btc` in `loadConfig()` and the omission of `one_shot_ai` in `dashboard_stats`, results in frontend UI states that drift out of sync with the backend.

---

## 3. Caveats

- **Network Mode:** The survey was conducted in read-only analysis mode without modifying project source code.
- **Hardware Device Testing:** iOS WKWebView behavior was verified by static analysis of `capacitor.config.json`, WebKit App-Bound Domains specifications, and local file resolution rules rather than deploying to a physical iPhone via Xcode.
- **Live Kalshi Credentials:** Testing was conducted with simulation/audit inspection of Kalshi client handlers; live order submissions were not executed against live capital.
- **Scope Limit:** Audit was constrained to R3 (Asset & Route Integrity) and R4 (Auto Trader Logic & UI Integration). Backend ML weights and ML training mathematics (R1/R2) were evaluated strictly in the context of their integration into execution loops.

---

## 4. Conclusion

The ShadowTrader AI codebase contains high-value algorithmic components, but exhibits critical vulnerabilities in its asset delivery, routing, and execution safety boundaries:
1. **Zero-404 Integrity Failure:** The app currently triggers multiple 404 errors on load due to non-existent icon files (`app_icon.ico`, `favicon.svg`) and misconfigured route paths in `ui.py`.
2. **Capacitor Incompatibility:** Absolute paths and extensionless server routes break inside iOS Capacitor WKWebView.
3. **Severe Runaway API Loop Risk:** The Auto Trader backend lacks rate-limit cooldown handling, resulting in aggressive 1-second order retry loops when Kalshi returns HTTP 429.
4. **UI State Desynchronization:** Broken DOM references, asset hardcoding in `loadConfig()`, and missing visibility guards in high-frequency polling cause UI toggles and Dynamic Island indicators to fall out of sync with backend states.

A comprehensive matrix of 14 specific fixes has been documented in `survey_report.md` to guide the implementation phase.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Missing Static Assets:**
   ```powershell
   Test-Path "C:\Users\Vill3\Desktop\ShadowTraderAi\static\assets\app_icon.ico" # Returns False
   Test-Path "C:\Users\Vill3\Desktop\ShadowTraderAi\static\assets\favicon.svg"  # Returns False
   ```
2. **Inspect Favicon Route in `ui.py`:**
   Inspect `backend/routes/ui.py:40-43` to confirm `ico_path = os.path.join(STATIC_DIR, "assets", "app_icon.ico")` points to non-existent file.
3. **Inspect Runaway Loop in `executor.py`:**
   Inspect `backend/btc/auto_executor/executor.py:1228-1240` to confirm that `self.last_traded_interval` is only assigned when `order_res.get("success")` is True or `order_res.get("ambiguous")` is True, omitting failure cases.
4. **Inspect DOM Elements in `saas_dashboard.html`:**
   Search for `id="auto-trader-toggle"` in `static/saas_dashboard.html` to confirm 0 matches while line 1320 calls `document.getElementById('auto-trader-toggle')`.
5. **Inspect Hardcoded BTC in `loadConfig()`:**
   Inspect `static/saas_dashboard.html:1583` to confirm `fetch('/api/engine/btc/trade/config')` hardcodes `btc`.

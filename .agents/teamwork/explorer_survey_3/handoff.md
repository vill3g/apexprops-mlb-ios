# Handoff Report: Frontend JS, State, Performance & UX Survey
**Agent**: `explorer_survey_3`  
**Recipient**: `parent` (ID: `269a1b7a-33d9-4136-b7da-906e573af819`) / Lead SWE  
**Date**: 2026-10-07  
**Working Directory**: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_3`  

---

## 1. Observation
1. **File Locations & Roles**:
   - `static/js/app.js` (5,671 lines, last modified 10/7/2026) is the active script loaded by `saas_dashboard.html` line 8550 (`<script src="./js/app.js?v=1791400000"></script>`) and targeted by `tests/test_frontend_contracts.py` (line 15: `JS_PATH = os.path.join(STATIC_DIR, "js", "app.js")`).
   - `static/app.js` (5,598 lines, last modified 10/3/2026) is an older unreferenced root copy missing sports trade filtering.
   - `static/saas_dashboard.html` (8,714 lines) contains the primary UI markup and inline JavaScript orchestrating `selectUniverse`, `setAutoTradingUniverse`, `openSettings`, `closeSettings`, `saveUserConfig`, and `populateUserSettings`.
2. **Single Shared Settings Drawer**:
   - `static/saas_dashboard.html` line 6989 to line 8408 defines a single container `<div id="settingsDrawer">`.
   - Lines 231460–232100 in `window.selectUniverse` morph this single drawer by rewriting `#settings-drawer-title`, `#settings-universe-badge`, `#settings-drawer-subtitle`, and toggling classes `.finance-only-setting` and `.sports-only-setting`.
3. **Tab Switch Stutter & Flicker**:
   - When switching to Financial, `selectUniverse` invokes `selectDashboardAsset('BTC')` (lines 289260–289350), which executes `showChartLoader()`, resets HUD counters (`#exec-strike`, `#exec-spot`, `#kalshi-yes`, `#kalshi-no`) to `$--,---` and `--%`, and awaits network requests before calling `hideChartLoader()`.
   - When switching to Sports, `selectUniverse` invokes `filterSportsEvents('ALL')` (lines 241550–241650), which wipes `#sports-events-container` with an `animate-pulse` loading string and queries `/api/engine/sports/events?t=${Date.now()}` with `cache: 'no-store'`.
   - Toggling `#lw-chart-container` to `display: none` / `display: block` causes the TradingView canvas to lose its computed dimensions without an explicit resize.
   - `window.renderTradesContainer` (line 184704) lacks dirty-checking and recreates 15 DOM cards via `container.innerHTML = ...` on every 1-second poll.
   - Redundant 1-second timers exist: `setInterval(init, 1000)` (calls `loadConfig` and `loadDashboard`), `setInterval(loadDashboard, 1000)` (calls `loadDashboard` again), and `setInterval(fetchKalshiData, 1000)`.
4. **Universe "BOTH" Memory Overwrite Bug**:
   - Backend verification: `POST /api/auth/user/config` with `{"trading_universe": "BOTH"}` succeeds (HTTP 200), persists to `users` table, and returns `"trading_universe": "BOTH"` on `GET /api/auth/dashboard_stats`.
   - In `static/saas_dashboard.html` line 237894 (inside `selectUniverse`):
     ```javascript
     if (window.lastDashboardStats) {
         window.lastDashboardStats.trading_universe = universe;
         // ...
     }
     ```
     When the user clicks "SPORTS" or "MARKETS" tab, `selectUniverse` overwrites `trading_universe` in `lastDashboardStats` with `'SPORTS'` or `'FINANCIAL'`, destroying `'BOTH'` in memory.
   - When `populateUserSettings(window.lastDashboardStats)` runs (on interval or drawer open), it reads the corrupted `trading_universe` and resets `setAutoTradingUniverse` away from `"BOTH"`.
   - If the user saves settings, it persists `'FINANCIAL'` or `'SPORTS'` to the server, erasing `"BOTH"`.
5. **Control Inventory**:
   - Settings drawer contains 70+ controls: Financial-only (asset toggles, ATR, Kelly, second entry, stop loss, take profit, trailing stop, daily risk, AI style, ML hyperparameters), Sports-only (sports trade size, leagues, markets, price corridor, mid-game TP, live toggle, confidence/edge sliders), and Common (Paper/Live mode, Auto Trader master switch, Auto Universe selector with "BOTH", API keys, sound, sign out).

---

## 2. Logic Chain
1. *From Observation 1 & 2*: Because `saas_dashboard.html` contains only one `<div id="settingsDrawer">` that toggles CSS visibility classes, Requirement R1 ("two distinct, independently toggleable UI components: one strictly for Financial and one strictly for Sports") is violated and requires splitting the markup into `financialSettingsDrawer` and `sportsSettingsDrawer`.
2. *From Observation 3*: Because `selectDashboardAsset('BTC')` calls `showChartLoader()` and blanks HUD numbers, and `filterSportsEvents` clears `innerHTML` for an animated loader on every tab switch, the UI stutters and flickers. Retaining cached chart/events and updating data silently in the background will eliminate this lag.
3. *From Observation 4*: Because line 237894 mutates `window.lastDashboardStats.trading_universe = universe`, any tab switch mutates the user's configured universe in client memory. Subsequent polling or drawer interactions re-populate settings using this corrupted value, destroying `"BOTH"`. Removing this line and maintaining `window.configuredTradingUniverse` separately fixes the root cause.
4. *From Observation 4 & 5*: Because users can open settings from either universe tab, rendering the Auto-Trading Universe 3-way toggle `[ Crypto ] [ Sports ] [ Both ]` in BOTH drawers (using synchronized class queries) satisfies Requirement R2 and ensures `"BOTH"` is visible and editable across both menus without resetting or hiding it.

---

## 3. Caveats
- No backend code changes were made (read-only investigation).
- Tests in `tests/test_r2_r5_multi_universe_and_timestamps.py` include one failure in `test_route_effective_user_id_prioritizes_both_and_all` due to mock active user key structure; this is unrelated to frontend tab switching.
- Browser WKWebView touch gestures (Capacitor iOS) rely on `touchmove` and `touchstart` listeners; both separated drawers must register independent swipe-to-close handlers.

---

## 4. Conclusion
The frontend UI refactor required for R1, R2, and R3 is well-defined and straightforward:
1. **R1**: Replace `<div id="settingsDrawer">` in `static/saas_dashboard.html` with two distinct HTML drawers: `financialSettingsDrawer` (containing only Financial groups) and `sportsSettingsDrawer` (containing only Sports groups), routed via `openFinancialSettings()`, `openSportsSettings()`, and `openSettings()`.
2. **R2**: Delete `window.lastDashboardStats.trading_universe = universe;` in `selectUniverse`. Embed the Auto-Trading Universe control with `[ Both ]` in both drawers, synchronized via `setAutoTradingUniverse`.
3. **R3**: Suppress `showChartLoader()` and HUD element blanking on tab switches, render cached sports events immediately, add dirty-checking to `window.renderTradesContainer`, and deduplicate 1s intervals.

---

## 5. Verification Method
1. **Pytest Suite**:
   ```bash
   python -m pytest tests/test_frontend_contracts.py tests/test_r2_r5_multi_universe_and_timestamps.py tests/test_r3_r4_ui_and_rate_limits.py
   ```
2. **DOM Separation Inspection**:
   Verify `saas_dashboard.html` contains:
   - `<div id="financialSettingsDrawer"`
   - `<div id="sportsSettingsDrawer"`
   - No duplicate IDs for shared controls (use classes like `.btn-auto-univ-both`, `.auto-universe-label-badge`).
3. **"BOTH" End-to-End Persistence Check**:
   - Submit `POST /api/auth/user/config` with `{"trading_universe": "BOTH"}`.
   - Load `saas_dashboard.html` and confirm `[ Both ]` is highlighted in both Financial and Sports settings drawers.
   - Switch back and forth between "SPORTS" and "MARKETS" tabs 5 times.
   - Open settings in both tabs and verify `[ Both ]` remains selected and `window.configuredTradingUniverse` remains `'BOTH'`.

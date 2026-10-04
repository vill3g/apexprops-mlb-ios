# Frontend UI/UX, iOS Smoothness & Architecture Survey Report

**Explorer**: `explorer_survey_2`  
**Date**: October 2, 2026  
**Scope**: Frontend UI/UX, iOS smoothness, HTML structure, JavaScript runtime/performance, CSS/safe-area insets, Capacitor configuration, and static assets.

---

## Executive Summary

A comprehensive investigation was conducted across the ShadowTrader AI frontend code, including `static/saas_dashboard.html`, `static/login.html`, `static/trades.html`, `static/admin_mobile.html`, JavaScript modules (`app.js`, `dashboard.js`, `admin_users.js`, `strategy_stats.js`), stylesheets (`app.css`, `dashboard.css`), iOS Capacitor configuration (`capacitor.config.json`, `update_ipa.py`), and test contracts (`tests/test_frontend_contracts.py`).

The investigation revealed **several high-severity architectural and runtime issues**:
1. **Critical DOM Nesting Bug**: `<div id="settingsDrawer">` in `saas_dashboard.html` (line 5288) is **never closed**, trapping 1,065 lines of trailing markup, modals (`updateAlertModal`), and script tags inside a hidden overlay container.
2. **Dual Polling Loop Storm**: `saas_dashboard.html`'s inline scripts and `static/js/app.js` run separate, uncoordinated polling loops simultaneously in the same tab, firing **7 to 8 HTTP requests per second**, leading to severe battery drain, network radio contention, and triggering API 429 rate limits.
3. **Missing iOS Home Indicator Safe Area Insets**: `saas_dashboard.html` uses `env(safe-area-inset-bottom)` **zero times**. Critical action buttons (e.g. modal dismiss buttons and Sign Out) collide directly with the iOS Home Indicator swipe bar.
4. **Auto Trader UI / Backend Desynchronization**: `toggleAutoTrader()` queries obsolete DOM IDs (`auto-trader-toggle`, `auto-trader-status`, `header-auto-status`) that do not exist, and fails to update the main header's `nav-auto-badge` on toggle.
5. **Capacitor Configuration Double Inset Bug**: `capacitor.config.json` sets `"contentInset": "always"`, forcing native UIScrollView to inset content while CSS also applies safe-area padding, resulting in awkward double-padding in WKWebView.
6. **Static Asset 404s**: Referenced icons (`./assets/favicon.svg` and `./assets/app_icon.ico`) in `login.html` and `trades.html` do not exist on disk, producing continuous 404 console errors.
7. **Corrupted Glassmorphism Classes**: Multiple Tailwind classes have been truncated to orphan tokens (e.g., `-2xl`, `-xl`, `-sm` instead of `backdrop-blur-*`), stripping blur effects on iOS Safari.
8. **Unlinked Stylesheet**: `app.css` (41 KB, 1,189 lines of responsive iOS rules) is completely unlinked in `saas_dashboard.html`.

---

## 1. HTML Structural Integrity & DOM Nesting

### 1.1 Unclosed `<div id="settingsDrawer">` (CRITICAL)
- **File**: `static/saas_dashboard.html`
- **Location**: Line 5288 to 6353
- **Observation**:
  - Line 5288 opens `<div id="settingsDrawer" class="fixed inset-0 z-[200] hidden">`.
  - Inside it, `#settingsPanel` is opened at line 5293, and inner content containers are opened at line 5319 and 5851.
  - At lines 6094, 6096, 6097, three closing `</div>` tags appear:
    - Line 6094 closes inner container (opened at 5851).
    - Line 6096 closes `<div class="flex-1 overflow-y-auto...">` (opened at 5319).
    - Line 6097 closes `<div id="settingsPanel">` (opened at 5293).
  - The matching closing tag for `<div id="settingsDrawer">` is **completely missing**.
  - As a result, lines 6099 through 6352 (the dropdown script, `<div id="updateAlertModal">`, update scripts, swipe scripts, and external `<script src="...">` tags) are nested inside `#settingsDrawer` until the browser automatically closes it at `</body>` (line 6353).
- **Impact**:
  - Whenever `#settingsDrawer` has the `hidden` class (`display: none`), child modals such as `#updateAlertModal` may be suppressed or mispositioned.
  - Click event delegation checking `e.target.closest('#settingsDrawer')` (lines 3924, 3997) matches clicks on `#updateAlertModal` and other trailing elements.
  - Violates HTML5 structural compliance and breaks DOM tree hierarchies.
- **Remediation**:
  Insert the missing `</div>` immediately following line 6097 before the `<script>` at line 6099.

### 1.2 Invalid Void Tag Syntax in `<head>`
- **File**: `static/saas_dashboard.html`
- **Lines**: 5-7
```html
5:     <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
6:     <meta http-equiv="Pragma" content="no-cache" />
7:     <meta http-equiv="Expires" content="0" />
```
- **Observation**: Self-closing XML slashes (`/>`) on standard HTML void elements triggers HTML parser warnings and explicit closing tag misinterpretations.
- **Remediation**: Standardize to `<meta http-equiv="..." content="...">` without trailing slashes.

### 1.3 Corrupted Tailwind CSS Utility Tokens
- **File**: `static/saas_dashboard.html`
- **Lines**: 531, 656, 1011, 1660, 5299
- **Observation**:
  - Line 531: `<div id="profileDropdown" class="... bg-[#0c0c10]/95 -2xl border ...">`
  - Line 656: `<div id="chart-loader" class="... bg-transparent/80 -sm ...">`
  - Line 1011: `toast.className = '... border -xl ...'`
  - Line 1660: `toast.className = '... shadow-[0_10px_40px_rgba(0,0,0,0.5)] -xl ...'`
  - Line 5299: `<div class="... bg-black/40 -xl ...">`
- **Root Cause**: An automated script or search-and-replace stripped `backdrop-blur` from `backdrop-blur-2xl`, `backdrop-blur-xl`, and `backdrop-blur-sm`, leaving orphan suffixes.
- **Impact**: In Safari/WebKit, elements completely lose the `-webkit-backdrop-filter` property, breaking the intended frosted glass aesthetic.
- **Remediation**: Restore `backdrop-blur-2xl`, `backdrop-blur-xl`, and `backdrop-blur-sm`.

### 1.4 Broken FontAwesome References in Obsolete Modal
- **File**: `static/saas_dashboard.html`
- **Lines**: 6218, 6226, 6238, 6245, 6252, 6259
- **Observation**: `#updateAlertModal` contains tags like `<i class="fas fa-rocket text-blue-400 text-lg"></i>` and `<i class="fas fa-times text-lg"></i>`. FontAwesome is not imported anywhere in the HTML.
- **Impact**: Icons render as blank invisible squares or broken glyphs.
- **Remediation**: Remove the redundant `#updateAlertModal` or replace with inline SVG icons consistent with `#updateAnnouncementModal`.

### 1.5 Duplicate Update Modal Elements
- **File**: `static/saas_dashboard.html`
- **Observation**:
  - Modal 1: `#updateAnnouncementModal` (lines 5245–5285) — Modern SVG icons, dynamic data loading from `/api/auth/updates`.
  - Modal 2: `#updateAlertModal` (lines 6212–6275) — Hardcoded text ("God-Tier 6-Pillar Blueprint"), broken FontAwesome icons, stored in `v3.0_god_tier_alert`.
- **Impact**: Two different modals compete to show update announcements, increasing DOM bloat and confusion.
- **Remediation**: Retire the obsolete `#updateAlertModal` and consolidate all update notifications into `#updateAnnouncementModal`.

---

## 2. Frontend JavaScript Runtime, Performance & Polling

### 2.1 Dual Polling Loop Storm (HIGH SEVERITY)
- **Files**: `static/saas_dashboard.html` (lines 772–4818) & `static/js/app.js` (lines 592, 1372, 4955, 4995, 5420)
- **Observation**:
  `saas_dashboard.html` registers:
  1. `fetchLiveBids()` every 800ms (`/api/engine/<asset>/kalshi/trades`)
  2. `loadDashboard()` every 1,000ms (`/api/auth/dashboard_stats`)
  3. `fetchKalshiData()` every 1,000ms (3 concurrent requests: `/kalshi`, `/countdown`, `/ticker`)
  4. `fetchChartData()` every 15,000ms (`/api/engine/<asset>/chart`)
  
  At line 6350, `saas_dashboard.html` imports `app.js`, which starts:
  5. `window._live1sTimer` every 1,000ms calling `pollBtcLive1s()` (`/api/engine/<asset>/live`)
  6. `window.chartRefreshInterval` every 1,500ms calling `fetchChartData()` (`/api/engine/<asset>/chart`)
  7. `window.pollKalshiTradingStatusId` every 3,000ms calling `pollKalshiTradingStatus()` (`/api/engine/<asset>/kalshi`)
  8. `window.pollGlobalTickerId` every 15,000ms calling `pollGlobalTicker()` (3 concurrent requests)
  9. `window.matrixTelemetryIntervalId` every 2,000ms
  10. Live WebSocket to `wss://ws-feed.exchange.coinbase.com`
- **Root Cause**: `app.js` was the JavaScript file for the legacy `main_index.html`. When `saas_dashboard.html` was created with its own inline JS, `app.js` was still imported at the bottom of the page, running both legacy and new polling loops in parallel.
- **Impact**:
  - **7 to 8 HTTP requests per second** continuously fire from a single client tab.
  - Causes severe battery drain, high device temperature, and network thread starvation on iOS mobile devices.
  - Can quickly trigger rate limits (429) from the backend or Kalshi API.
- **Remediation**:
  - Remove redundant polling loops in `app.js` when running on `saas_dashboard.html`, or consolidate all polling into a single throttled ticker loop.
  - Throttling recommendation: Set live trade bids to 2,000ms, dashboard stats to 3,000ms, and chart data to 5,000ms–15,000ms.

### 2.2 Global `fetch` Overwrite Race Condition
- **Files**: `static/saas_dashboard.html` (lines 31–75) & `static/js/app.js` (lines 1–17)
- **Observation**:
  - Line 31 of `saas_dashboard.html` has an async IIFE `initApiBackend()` that awaits a network ping with a 1,200ms timeout before setting `window.fetch`.
  - While this ping is resolving, `app.js` loads and wraps `window.fetch` to intercept `X-Refreshed-Token`.
  - When `initApiBackend()` finishes its 1,200ms ping, it unconditionally executes `window.fetch = async function() { ... return originalFetch(resource, config); }`.
- **Impact**: Overwrites `app.js`'s token refresh interceptor, causing session extension tokens (`X-Refreshed-Token`) to be discarded.
- **Remediation**: Harmonize the fetch wrapper into a single utility that handles both API base URL prefixing and token refresh headers synchronously without overwriting.

### 2.3 Hardcoded LAN IP & Dangerous Ngrok Fallback
- **File**: `static/saas_dashboard.html` (lines 43–65) & `static/login.html` (lines 15–31)
- **Observation**:
  ```javascript
  const localUrl = "http://192.168.1.194:8058";
  const remoteUrl = "https://moneyprinter.ngrok.app";
  ```
- **Root Cause**: Hardcoded IP `192.168.1.194` is tested when accessing via `localhost` or `127.0.0.1`. If the local server is on any other network or machine, the ping fails and falls back to `https://moneyprinter.ngrok.app`.
- **Impact**:
  - Local developers running on `localhost:8058` have their traffic rerouted to the remote ngrok tunnel after a 1.2s delay.
  - Hardcoded `moneyprinter.ngrok.app` also appears in `admin_users.js` (lines 905, 1308) and `saas_dashboard.html` (lines 2059, 2267) for avatars. If the ngrok tunnel is expired or offline, avatars fail to render.
- **Remediation**: Use relative URLs when `window.location.origin` is available, and use `window.location.origin` as `API_BASE_URL` on localhost/LAN.

### 2.4 Token Key Inconsistency in `openSettings()`
- **File**: `static/saas_dashboard.html`
- **Line**: 132
- **Observation**:
  ```javascript
  const token = localStorage.getItem('token');
  if (token) {
      fetch('/api/auth/dashboard_stats', ...)
  ```
  Everywhere else in the app uses `'saas_token'`. Because `'token'` is not set, this block never executes, preventing settings data from being refreshed when the drawer is opened.
- **Remediation**: Change to `localStorage.getItem('saas_token')`.

### 2.5 Console 403 Errors for Non-Admin Users
- **File**: `static/js/admin_users.js`
- **Lines**: 5918–5921
- **Observation**: `admin_users.js` attaches a `DOMContentLoaded` event listener that immediately fires `fetchAdminUsers(false)` and `fetchAdminTickets(true)` on every page load.
- **Impact**: For any non-admin user, these requests fail with `403 Forbidden`, logging red errors to the console.
- **Remediation**: Only execute `fetchAdminUsers` and `fetchAdminTickets` when the admin modal is explicitly opened by an authorized user (`user.role === 'admin'`).

### 2.6 Passive Event Listener Violation Causing Scroll Jank
- **File**: `static/saas_dashboard.html`
- **Line**: 3977
- **Observation**: `window.addEventListener('touchmove', ..., { passive: false });` attached globally for pull-to-refresh.
- **Impact**: Disables iOS Safari threaded compositor scrolling, causing frame drops and touch delay across the entire webview.
- **Remediation**: Move touch listeners to the pull-to-refresh container itself or only attach the non-passive touchmove listener dynamically when `isAtTop()` is true and a pull gesture has started.

### 2.7 Dead Swipe Handler Referencing Invalid ID
- **File**: `static/saas_dashboard.html`
- **Line**: 6328
- **Observation**: `const settingsPanel = document.getElementById("settings-panel");`
  The DOM ID is `settingsPanel` (camelCase). Line 6328 evaluates to `null`.
- **Remediation**: Remove lines 6324–6348 as the swipe-to-close behavior is already implemented at lines 216–300 (`initSettingsSwipeToClose`).

---

## 3. Auto Trader UI & Backend State Synchronization (R4)

### 3.1 Nonexistent DOM IDs in `toggleAutoTrader` and `loadConfig`
- **File**: `static/saas_dashboard.html`
- **Lines**: 1320–1323, 1590–1593
- **Observation**:
  ```javascript
  const autoToggle = document.getElementById('auto-trader-toggle');     // null
  const autoStatus = document.getElementById('auto-trader-status');     // null
  const headerToggle = document.getElementById('header-auto-toggle');   // exists (L5344)
  const headerStatus = document.getElementById('header-auto-status');   // null
  ```
  Neither `auto-trader-toggle`, `auto-trader-status`, nor `header-auto-status` exist in the DOM.
- **Impact**: State updates fail silently; text indicators are never updated.
- **Remediation**: Clean up obsolete ID queries and ensure the actual toggle (`header-auto-toggle`) and status indicators (`settings-auto-status`) are properly wired.

### 3.2 Header Auto Badge Desynchronization
- **File**: `static/saas_dashboard.html`
- **Observation**:
  - The main header features `#nav-auto-badge` (line 497), displaying `AUTO OFF` or `AUTO ON`.
  - `loadConfig()` (line 1610) updates `#nav-auto-badge` when fetching config.
  - However, `toggleAutoTrader(enabled)` (line 1317) **does not update `#nav-auto-badge`**!
- **Impact**: When the user flips the Auto Trader switch in the settings drawer, the badge in the top navigation continues to show `AUTO OFF` until a separate asynchronous `loadConfig()` completes.
- **Remediation**: Add immediate optimistic updating of `#nav-auto-badge` inside `toggleAutoTrader(enabled)`.

### 3.3 Dynamic Island Glow Sync
- **File**: `static/saas_dashboard.html`
- **Lines**: 446–465, 5665
- **Observation**:
  - `di-toggle` has `checked` hardcoded in HTML (line 5665).
  - If the user previously disabled Dynamic Island in localStorage (`di_enabled === 'false'`), `di-toggle.checked` in the DOM remains `true` until settings is opened.
  - On initial page load, `updateDynamicIsland()` is only called once `loadConfig()` resolves.
- **Remediation**: Read `localStorage.getItem('di_enabled')` on DOM ready and sync `di-toggle.checked` immediately.

### 3.4 Hardcoded BTC in `loadConfig()`
- **File**: `static/saas_dashboard.html`
- **Line**: 1583
- **Observation**: `loadConfig()` fetches `/api/engine/btc/trade/config` directly, ignoring `window.currentAsset`.
- **Impact**: Switching to ETH or GOLD and opening settings still loads BTC's auto trading configuration.
- **Remediation**: Use `/api/engine/${(window.currentAsset || 'BTC').toLowerCase()}/trade/config`.

---

## 4. iOS Safe Area, Viewport & Layout Smoothness (R2)

### 4.1 Complete Absence of `env(safe-area-inset-bottom)` in `saas_dashboard.html`
- **File**: `static/saas_dashboard.html`
- **Observation**: Across 6,372 lines, `env(safe-area-inset-bottom)` is used **0 times**.
- **Impacted Elements**:
  1. `<main>` container (line 612): Uses static `pb-12` (48px) without bottom safe area padding.
  2. Sticky footer in `#updateAnnouncementModal` (line 5278): "Got It, Dismiss" button is pinned directly to the bottom edge without safe area inset. On iPhone 14/15/16 Pro, the button sits directly underneath the iOS Home Indicator (34px), causing tap/swipe conflicts.
  3. Sticky footer in `#tradeDetailsModal` (line 5233): "Close" button collides with the Home Indicator.
  4. Settings Drawer bottom (line 6084): "Sign Out" button has static `pb-6` (24px), leaving insufficient clearance above the Home Indicator.
- **Remediation**:
  - Add helper utility classes in CSS:
    ```css
    .pb-safe { padding-bottom: max(env(safe-area-inset-bottom, 0px), 16px); }
    .bottom-safe { bottom: env(safe-area-inset-bottom, 0px); }
    ```
  - Apply `padding-bottom: calc(1rem + env(safe-area-inset-bottom, 0px))` to all sticky footers and the `<main>` container.

### 4.2 Incomplete iOS Viewport Configuration in `trades.html`
- **File**: `static/trades.html`
- **Lines**: 5, 19, 32
- **Observation**:
  - Line 5 lacks `viewport-fit=cover`.
  - Header at line 19 lacks `padding-top: env(safe-area-inset-top)`.
  - Pull-to-refresh indicator at line 32 uses hardcoded `top: 3.5rem`.
- **Impact**: On iOS devices with a notch or Dynamic Island, the header content is obscured by the status bar.
- **Remediation**: Add `viewport-fit=cover` and safe area insets to header and pull-to-refresh.

### 4.3 Unlinked `app.css` Stylesheet
- **File**: `static/css/app.css` vs `static/saas_dashboard.html`
- **Observation**: `static/css/app.css` (41,672 bytes) contains comprehensive iOS safe area definitions (`--sat`, `--sab`, `.pb-safe`, `html, body { overflow: hidden; height: 100dvh; }`, and iPhone 17 media queries). However, `saas_dashboard.html` **never links `app.css`**! The only linked stylesheet is `dashboard.css` (275 bytes, line 611).
- **Impact**: All of the custom iOS safe area and responsiveness styling implemented in `app.css` is completely inactive.
- **Remediation**: Review and link `app.css` in `<head>` (or merge essential safe-area utilities into `saas_dashboard.html`).

---

## 5. iOS Capacitor Wrapper & Native Configuration

### 5.1 `contentInset: "always"` in `capacitor.config.json`
- **File**: `capacitor.config.json`
- **Lines**: 9–12
```json
"ios": {
  "contentInset": "always",
  "limitsNavigationsToAppBoundDomains": true
}
```
- **Observation**: In Capacitor iOS WKWebView, `"contentInset": "always"` tells `WKWebView.scrollView` to automatically adjust its content insets for the status bar and home indicator.
- **Impact**: When the web application also sets `viewport-fit=cover` and uses `env(safe-area-inset-top)` in CSS, the webview is pushed down twice (**double inset bug**), creating an unwanted gap above the header.
- **Remediation**: Change `"contentInset": "always"` to `"contentInset": "automatic"` or `"never"`.

### 5.2 `limitsNavigationsToAppBoundDomains: true` Risk
- **File**: `capacitor.config.json`
- **Line**: 11
- **Observation**: Restricts all webview navigations and API requests to domains declared under `WKAppBoundDomains` in the native `Info.plist`.
- **Impact**: If `Info.plist` does not explicitly declare the API domain or ngrok tunnel, all network requests are silently blocked by iOS WebKit with a security violation.
- **Remediation**: Set to `false` unless `WKAppBoundDomains` is actively maintained in the native project.

### 5.3 App Name Inconsistency
- **Observation**:
  - `capacitor.config.json` (line 3): `"appName": "ShadowTrade AI"`
  - `update_ipa.py` (lines 23–24): `pl['CFBundleDisplayName'] = 'Kalshi_AiTrader'`
- **Remediation**: Synchronize display name across `capacitor.config.json` and `update_ipa.py`.

### 5.4 8.3 MB Unused Asset Packaged into IPA
- **File**: `static/ai_avatar.gif` (8,312,831 bytes)
- **Observation**: `ai_avatar.gif` is no longer used by `saas_dashboard.html` (which now uses `assets/icon.png`). However, `update_ipa.py` copies the entire `static/` folder into the IPA bundle.
- **Impact**: The iOS application bundle size is bloated by over 8 MB of dead assets.
- **Remediation**: Exclude large unused files or remove `static/ai_avatar.gif` in favor of `ai_avatar_opt.gif` (483 KB).

---

## 6. Static Asset Integrity (404 Scan)

### 6.1 Missing Icon Assets (404 Errors)
A programmatic scan of all referenced asset paths against files on disk revealed **5 missing static files**:
1. `static/login.html`:
   - Line 50: `<link rel="icon" type="image/svg+xml" href="./assets/favicon.svg">` → `favicon.svg` does not exist on disk.
   - Line 51: `<link rel="alternate icon" href="./assets/app_icon.ico">` → `app_icon.ico` does not exist on disk.
   - Line 292: `href="./assets/favicon.svg"` → does not exist on disk.
2. `static/trades.html`:
   - Line 7: `<link rel="icon" type="image/svg+xml" href="./assets/favicon.svg">` → does not exist on disk.
   - Line 8: `<link rel="alternate icon" href="./assets/app_icon.ico">` → does not exist on disk.
- **Remediation**: Point icon references to existing files: `./favicon.ico` or `./assets/app_icon.png`.

### 6.2 Unused External Script
- **File**: `static/saas_dashboard.html`
- **Line**: 413: `<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>`
- **Observation**: The full TradingView chart widget is never constructed; the app exclusively uses `lightweight-charts.js`.
- **Remediation**: Remove `tv.js` to eliminate ~200KB of network overhead and render-blocking script execution.

---

## 7. Contract Test Failures (`tests/test_frontend_contracts.py`)

Executing `pytest tests/test_frontend_contracts.py` resulted in **6 test failures**:
1. `TestCountdownTimer::test_countdown_dom_elements_exist`:
   - Fixture loads `index.html` (which is a 14-line redirect page) instead of `saas_dashboard.html`.
2. `TestModalSwipeDismissContracts::test_modal_card_ids_exist`
3. `TestModalSwipeDismissContracts::test_swipe_pill_handles_exist`
4. `TestModalSwipeDismissContracts::test_attach_swipe_to_dismiss_wired`
5. `TestModalSwipeDismissContracts::test_escape_key_listener_registered`
6. `TestModalSwipeDismissContracts::test_modal_reset_styles_on_open`
   - These tests look for legacy modal IDs (`tradeDetailsModalCard`, `regimeModalCard`, `styleModalCard`, `swipe-pill`) that were present in `main_index.html` but replaced during the SaaS dashboard redesign.
- **Remediation**: Update test fixtures and expectations to target `saas_dashboard.html` and the current active modal structure.

---

## Priority Action Matrix

| Priority | Issue | Location | Recommended Action |
|:---:|:---|:---|:---|
| **P0** | Unclosed `<div id="settingsDrawer">` | `saas_dashboard.html:5288` | Close `<div>` at line 6097 before trailing scripts/modals |
| **P0** | Dual Polling Loop Storm | `saas_dashboard.html` & `app.js` | Deduplicate intervals; throttle live requests to 2s–3s |
| **P0** | Missing Bottom Safe Area Insets | `saas_dashboard.html:5233, 5278, 6084` | Add `env(safe-area-inset-bottom)` to sticky footers and main |
| **P1** | Auto Trader UI Element ID Mismatch | `saas_dashboard.html:1320, 1590` | Update queries to `header-auto-toggle`; sync `nav-auto-badge` |
| **P1** | Capacitor Double Inset Bug | `capacitor.config.json:10` | Change `"contentInset": "always"` to `"automatic"` |
| **P1** | Static Asset 404s | `login.html:50`, `trades.html:7` | Replace missing `favicon.svg`/`app_icon.ico` with existing assets |
| **P2** | Corrupted Glassmorphism Classes | `saas_dashboard.html:531, 656, 5299` | Restore `backdrop-blur-*` prefix |
| **P2** | Global Fetch Overwrite Race | `saas_dashboard.html:31` & `app.js:1` | Consolidate `fetch` wrapper cleanly |
| **P2** | Unused `tv.js` and fontawesome | `saas_dashboard.html:413, 6218` | Remove unused external script and clean up dead modal |
| **P2** | Update Outdated Contract Tests | `tests/test_frontend_contracts.py` | Align tests with `saas_dashboard.html` architecture |

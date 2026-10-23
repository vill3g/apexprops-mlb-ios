# Survey Report: Frontend JS, State, Performance & UX Architecture
**Author**: `explorer_survey_3`  
**Date**: 2026-10-07  
**Scope**: `static/app.js`, `static/js/app.js`, `static/saas_dashboard.html`, Frontend State, Settings Drawers Decoupling (R1), Multi-Universe "BOTH" Persistence (R2), and UI/UX Optimization (R3).

---

## Executive Summary
This survey investigates the frontend architecture of ShadowTrader AI, focusing on the UI refactor required to:
1. Decouple the shared settings drawer in `static/saas_dashboard.html` into two dedicated, independently toggleable UI drawers for Financials and Sports (**Requirement R1**).
2. Guarantee end-to-end persistence and display consistency for the `"BOTH"` auto-trading universe setting across both menus and tab transitions (**Requirement R2**).
3. Eliminate UI stutter, flicker, and lag during tab transitions and background polling cycles, while ensuring all form controls, sliders, and toggles reliably persist to the backend (**Requirement R3**).

Our inspection identified the exact root causes of UI flicker and lag, uncovered the bug causing `"BOTH"` to be wiped from memory on tab switches, inventoried all 70+ form controls across both domains, and designed a drop-in architectural blueprint for implementation.

---

## 1. Asset & Script Inventory: `static/app.js` vs `static/js/app.js` vs `saas_dashboard.html`

### 1.1 Script Roles and Relationships
- **`static/js/app.js` (5,671 lines, Active Source of Truth)**:
  - Included by `saas_dashboard.html` line 8550 (`<script src="./js/app.js?v=1791400000"></script>`) and `index.html`.
  - Tested directly by test suites (`tests/test_frontend_contracts.py` sets `JS_PATH = os.path.join(STATIC_DIR, "js", "app.js")`).
  - Contains core trading utilities: `renderKalshiTradesList` (lines 3530–3650, which filters by `window.currentUniverse === 'SPORTS'`), `window.switchAsset`, `initTradingViewChart`, `saveKalshiSettings`, DraftKings slip builders, and modal helpers.
- **`static/app.js` (5,598 lines, Legacy Artifact)**:
  - Stale copy in the root `static/` folder from October 3, 2026, missing recent sports filtering patches in `renderKalshiTradesList`.
  - *Recommendation*: While `static/js/app.js` is the loaded and tested file, ensure `static/app.js` is updated or mirrored to avoid developer confusion.
- **`static/saas_dashboard.html` (8,714 lines, Main Web Interface)**:
  - Contains primary SaaS dashboard logic in extensive inline `<script>` blocks (lines 40–55, 6777–8410, 8411–8714).
  - Drives `selectUniverse`, `setAutoTradingUniverse`, `openSettings`, `closeSettings`, `saveUserConfig`, `populateUserSettings`, `renderTradesContainer`, `loadDashboard`, and `loadSportsEvents`.

---

## 2. Tab Switching Logic & Performance / Stuttering Audit

### 2.1 Current Tab Switching Flow (`selectUniverse`)
When switching tabs (via the top dropdown `#universe-dropdown` or drawer pills `#btn-universe-fin-settings` / `#btn-universe-sports-settings`), `window.selectUniverse(universe)` executes:

```javascript
window.selectUniverse = function(universe) {
    window.currentUniverse = universe;
    localStorage.setItem('preferred_universe', universe);
    document.body.classList.toggle('universe-sports', universe === 'SPORTS');
    // ... toggles DOM classes .finance-only-setting and .sports-only-setting ...
```

### 2.2 Root Causes of UI Stutter, Flicker, and Lag

#### Issue 1: Blocking Loading Spinner and DOM Blanking on Switch to Financial
- **Location**: `static/saas_dashboard.html` lines 289260–289350 (`selectDashboardAsset('BTC')` called via `selectUniverse('FINANCIAL')`).
- **Mechanism**:
  ```javascript
  showChartLoader(); // Displays full opacity overlay with spinner
  // Blanks out HUD counters:
  if (strikeEl) strikeEl.textContent = '$--,---';
  if (spotEl) spotEl.textContent = '$--,---';
  if (yesBid) yesBid.textContent = '--%';
  if (noBid) noBid.textContent = '--%';
  if (cdEl) cdEl.textContent = '--:--';
  if (bidsBox) bidsBox.innerHTML = '';
  // Blocks on network:
  await Promise.allSettled([
      fetchChartData(true),
      fetchKalshiData(true),
      scheduleNextLiveBids(0)
  ]);
  hideChartLoader();
  ```
- **Consequence**: Every single time the user clicks back to the Financial tab, the chart is hidden behind a spinner and all live metrics are wiped to dashes for 200–500ms, creating severe visual stutter and perceived latency, even though candle and contract data already exist in memory.
- **Fix**: When switching tabs, check if `window.currentAsset` already has cached chart data and an instantiated `lwChart`. If so:
  1. Do NOT call `showChartLoader()`.
  2. Do NOT blank strike, spot, or bids HUD elements.
  3. Keep the existing chart visible, call `lwChart.timeScale().fitContent()` or resize immediately.
  4. Perform background data refreshes silently.

#### Issue 2: Flash of Empty / Loading State on Switch to Sports
- **Location**: `static/saas_dashboard.html` lines 241550–241650 (`filterSportsEvents('ALL')` and `renderSportsEvents()`).
- **Mechanism**:
  - `loadSportsEvents` always fires `fetch('/api/engine/sports/events?t=' + Date.now(), { cache: 'no-store' })`.
  - `renderSportsEvents` wipes `container.innerHTML = '<div ... animate-pulse>Loading ALL AI picks...</div>'`.
  - When data returns, it wipes `container.innerHTML = ''` again and rebuilds all event cards.
- **Consequence**: Every tab click to Sports produces an animated loading flash and DOM rebuild, even if picks were fetched seconds ago.
- **Fix**: Render immediately from `window.__sportsEventsCache` without clearing the container or showing the pulsating loader. Refresh in the background; only re-render if events or odds have changed.

#### Issue 3: HTML5 Canvas Invalidation on `display: none`
- **Location**: `static/saas_dashboard.html` lines 236240–237850.
- **Mechanism**: Setting `#lw-chart-container` to `display: none` and then `display: block` causes the TradingView Lightweight Charts canvas to lose its computed dimensions.
- **Fix**: In `selectUniverse('FINANCIAL')`, after making `#lw-chart-container` visible, immediately dispatch `requestAnimationFrame(() => { if (lwChart) lwChart.applyOptions({ width: container.clientWidth, height: container.clientHeight }); });`.

#### Issue 4: Trade Container Reconstruction on Every Polling Cycle
- **Location**: `static/saas_dashboard.html` lines 184704–185200 (`window.renderTradesContainer`).
- **Mechanism**: Every second, `loadDashboard()` runs and unconditionally wipes `#tradesContainer` with `container.innerHTML = ...`, generating 15 trade cards from raw strings.
- **Fix**: Introduce a signature/dirty cache key (matching `_lastKalshiTradesKey` in `app.js`). If `trades.length`, trade statuses, and PnL values haven't changed, skip DOM reconstruction.

#### Issue 5: Duplicate and Redundant 1-Second Polling Timers
- **Location**: `static/saas_dashboard.html` lines 215411, 219993, 396641.
- **Mechanism**:
  - `setInterval(init, 1000)` calls `loadConfig()` (GET `/trade/config`) and `loadDashboard()` (GET `/dashboard_stats`).
  - `setInterval(loadDashboard, 1000)` calls `loadDashboard()` a SECOND time every 1s.
  - `setInterval(fetchKalshiData, 1000)` calls GET `/trade/kalshi_market` every 1s.
- **Consequence**: The frontend bombards the local Python server with 4–6 HTTP requests every second on a single thread.
- **Fix**: Remove the duplicate `setInterval(loadDashboard, 1000)` call, and throttle `loadConfig()` to run every 10–15s or only on user interaction, since config does not change every second.

---

## 3. Investigation of Multi-Universe "BOTH" Persistence (R2)

### 3.1 Backend Behavior (Verified via Live Test)
- Running `POST /api/auth/user/config` with payload `{"trading_universe": "BOTH"}` returns `200 {"success": True}`.
- SQLite table `users` successfully updates `trading_universe = 'BOTH'`.
- Subsequent `GET /api/auth/dashboard_stats` accurately returns `"trading_universe": "BOTH"`.
- Backend constraints: `VALID_TRADING_UNIVERSES = {"FINANCIAL", "SPORTS", "BOTH", "ALL"}`.
- **Conclusion**: The backend natively and correctly handles `"BOTH"`.

### 3.2 The Critical Frontend Bug: Memory Overwrite on Tab Switch
In `static/saas_dashboard.html` at line 237894 (inside `selectUniverse`):
```javascript
if (window.lastDashboardStats) {
    window.lastDashboardStats.trading_universe = universe; // ⚠️ CRITICAL BUG!
    if (typeof window.renderTradesContainer === 'function') window.renderTradesContainer(window.lastDashboardStats);
    // ...
}
```
**Why this breaks "BOTH"**:
1. User configures auto-trading universe to `"BOTH"`. Backend stores `"BOTH"`.
2. When the user clicks the "SPORTS" or "MARKETS" tab in the UI, `selectUniverse(universe)` is called with `'SPORTS'` or `'FINANCIAL'`.
3. Line 237894 overwrites `window.lastDashboardStats.trading_universe = universe`, changing `'BOTH'` in memory to `'SPORTS'` or `'FINANCIAL'`.
4. Subsequent calls to `populateUserSettings(window.lastDashboardStats)` (which occur on every `loadDashboard` tick and whenever settings open) read `s.trading_universe` and call `setAutoTradingUniverse('SPORTS')` or `'FINANCIAL'`.
5. This deselects `"BOTH"` in the UI!
6. If `saveUserConfig()` is triggered (or auto-saves on blur), it reads `window.lastDashboardStats.trading_universe` and writes `'SPORTS'` or `'FINANCIAL'` back to the database, permanently wiping the user's `"BOTH"` selection.

### 3.3 The Incomplete Tab Handling in `openSettings` and `populateUserSettings`
- In `openSettings()`:
  ```javascript
  selectUniverse(window.currentUniverse || (window.lastDashboardStats && window.lastDashboardStats.trading_universe) || 'FINANCIAL');
  ```
  If `lastDashboardStats.trading_universe` is `'BOTH'`, calling `selectUniverse('BOTH')` evaluates `universe === 'SPORTS'` as false and falls into the financial branch, hiding all sports controls and setting titles to "Financials Settings".
- In `populateUserSettings()`:
  ```javascript
  if (!window.currentUniverse || force) {
      const viewTab = (tu === 'SPORTS') ? 'SPORTS' : 'FINANCIAL';
      if (typeof selectUniverse === 'function') selectUniverse(viewTab);
  }
  ```
  When `tu === 'BOTH'`, defaulting `viewTab` to `'FINANCIAL'` is fine for initial view, but must NOT alter `window.configuredTradingUniverse`.

---

## 4. Architectural Plan for Decoupled Settings Drawers (R1 & R2)

### 4.1 Requirement R1 Goal
Replace the single morphing drawer (`#settingsDrawer`) with **two distinct, independently toggleable UI components**:
1. `financialSettingsDrawer`: Strictly for crypto, forex, capital guard, ML models, and chart settings.
2. `sportsSettingsDrawer`: Strictly for sports betting, leagues, market types, prop sizing, edge thresholds, and mid-game TP.

### 4.2 Control Inventory & Separation Mapping

| Category | Control ID | Financial Drawer | Sports Drawer | Notes |
|---|---|:---:|:---:|---|
| **Trading Mode** | `btn-mode-paper-settings`, `btn-mode-live-settings` | ✅ | ✅ | Paper vs Live toggle in both drawers |
| **Auto-Trader Toggle** | `header-auto-toggle` / `sports-header-auto-toggle` | ✅ | ✅ | Auto trading master toggle in both |
| **Auto Universe ("BOTH")** | `btn-auto-univ-crypto`, `btn-auto-univ-sports`, `btn-auto-univ-both` | ✅ | ✅ | **Must exist in BOTH menus** |
| **Universe Badge** | `auto-universe-label-badge` | ✅ | ✅ | Synchronized display across both |
| **Asset Selection** | `asset-btc-toggle`, `asset-eth-toggle`, `asset-gold-toggle`, etc. (10 assets) | ✅ | ❌ | Strictly Financial |
| **Financial Risk** | `trade-size-dollars`, `kelly-criterion-toggle`, `atr-risk-toggle` | ✅ | ❌ | Strictly Financial |
| **Entries & Stops** | `second-entry-toggle`, `second-entry-max-ask`, `stop-loss-pct`, `stop-loss-toggle`, `take-profit-pct`, `take-profit-toggle`, `trailing-stop-toggle`, `trailing-stop-activation-pct`, `trailing-stop-distance-pct` | ✅ | ❌ | Strictly Financial |
| **Financial Caps** | `max-daily-risk`, `max-daily-trades` | ✅ | ❌ | Strictly Financial |
| **AI Strategy** | `trading-style`, `signal-source`, `one-shot-toggle`, `one-click-toggle`, `force-trade-toggle`, `technical-force-toggle` | ✅ | ❌ | Strictly Financial |
| **Chart & UI** | `settings-chart-type`, `settings-chart-timeframe`, `toggle-trade-exec-panel` | ✅ | ❌ | Strictly Financial |
| **ML Parameters** | `model-choice`, `train-window`, `reg-c`, `class-weight`, `xgb-estimators`, `xgb-max-depth`, `xgb-learning-rate` | ✅ | ❌ | Strictly Financial |
| **Sports Trade Size** | `sports-trade-size-dollars`, `sports-wager-dollars` | ❌ | ✅ | Strictly Sports |
| **Sports Kelly** | `sports-kelly-toggle` | ❌ | ✅ | Strictly Sports |
| **Price Corridor** | `sports-min-price`, `sports-max-price` | ❌ | ✅ | Strictly Sports |
| **Mid-Game TP** | `sports-tp-pct`, `sports-tp-toggle` | ❌ | ✅ | Strictly Sports |
| **Sports Caps** | `sports-max-daily-risk`, `sports-max-daily-trades`, `sports-max-open-trades` | ❌ | ✅ | Strictly Sports |
| **Live Games Toggle**| `sports-include-live-toggle` | ❌ | ✅ | Strictly Sports |
| **Sports AI Sliders**| `sports-conf-slider`, `sports-edge-slider` | ❌ | ✅ | Strictly Sports |
| **Sports Leagues** | `input.sports-league-toggle` (NFL, MLB, NPB/KBO, SOC, UFC, TEN, NHL) | ❌ | ✅ | Strictly Sports |
| **Sports Markets** | `input.sports-market-toggle` (GAME, SPREAD, TOTAL, PROP, INNING) | ❌ | ✅ | Strictly Sports |
| **Kalshi Keys** | `kalshi-key`, `kalshi-priv` | ✅ | ✅ | Available in both or linked |
| **Audio & Push** | `settings-sound-toggle`, `ios-notify-toggle` | ✅ | ✅ | Available in both |
| **Wallet Transfer** | `transfer-direction`, `transfer-amount`, `transfer-btn` | ✅ | ❌ | Financial wallet |
| **Admin Console** | `admin-console-group` | ✅ | ❌ | Visible to role=admin |
| **Sign Out** | `logout()` button | ✅ | ✅ | In both drawers |

### 4.3 Markup Architecture
In `static/saas_dashboard.html`:
```html
<!-- FINANCIAL SETTINGS DRAWER -->
<div id="financialSettingsDrawer" class="fixed inset-0 z-[200] hidden">
    <div id="financialSettingsBackdrop" class="absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0 transition-opacity duration-300" onclick="closeFinancialSettings()"></div>
    <div id="financialSettingsPanel" class="absolute right-0 top-0 bottom-0 w-full sm:w-[440px] max-w-[95vw] bg-[#0c101a]/95 border-l border-white/[0.08] shadow-[0_0_60px_rgba(0,0,0,0.95)] flex flex-col transform translate-x-full transition-transform duration-300 ease-out select-none">
        <!-- Header with Financials Badge -->
        <!-- Content containing ONLY Financial groups -->
    </div>
</div>

<!-- SPORTS SETTINGS DRAWER -->
<div id="sportsSettingsDrawer" class="fixed inset-0 z-[200] hidden">
    <div id="sportsSettingsBackdrop" class="absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0 transition-opacity duration-300" onclick="closeSportsSettings()"></div>
    <div id="sportsSettingsPanel" class="absolute right-0 top-0 bottom-0 w-full sm:w-[440px] max-w-[95vw] bg-[#0c101a]/95 border-l border-white/[0.08] shadow-[0_0_60px_rgba(0,0,0,0.95)] flex flex-col transform translate-x-full transition-transform duration-300 ease-out select-none">
        <!-- Header with Sports Badge -->
        <!-- Content containing ONLY Sports groups -->
    </div>
</div>
```

*Note on backward compatibility*: Maintain aliases `settingsDrawer = financialSettingsDrawer` or provide a wrapper so any legacy reference to `document.getElementById('settingsDrawer')` safely resolves.

### 4.4 Drawer Opening and Closing Controller
```javascript
window.openFinancialSettings = function() {
    closeSportsSettings();
    const drawer = document.getElementById('financialSettingsDrawer');
    const panel = document.getElementById('financialSettingsPanel');
    const backdrop = document.getElementById('financialSettingsBackdrop');
    if (!drawer || !panel) return;
    drawer.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => {
        panel.classList.remove('translate-x-full');
        panel.classList.add('translate-x-0');
        if (backdrop) {
            backdrop.classList.remove('opacity-0');
            backdrop.classList.add('opacity-100');
        }
    });
    window.isSettingsOpen = true;
    if (typeof populateUserSettings === 'function' && window.lastDashboardStats) {
        populateUserSettings(window.lastDashboardStats, false);
    }
};

window.openSportsSettings = function() {
    closeFinancialSettings();
    const drawer = document.getElementById('sportsSettingsDrawer');
    const panel = document.getElementById('sportsSettingsPanel');
    const backdrop = document.getElementById('sportsSettingsBackdrop');
    if (!drawer || !panel) return;
    drawer.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => {
        panel.classList.remove('translate-x-full');
        panel.classList.add('translate-x-0');
        if (backdrop) {
            backdrop.classList.remove('opacity-0');
            backdrop.classList.add('opacity-100');
        }
    });
    window.isSettingsOpen = true;
    if (typeof populateUserSettings === 'function' && window.lastDashboardStats) {
        populateUserSettings(window.lastDashboardStats, false);
    }
};

window.openSettings = function(universe) {
    const target = universe || window.currentUniverse || 'FINANCIAL';
    if (target === 'SPORTS') {
        window.openSportsSettings();
    } else {
        window.openFinancialSettings();
    }
};

window.closeSettings = function() {
    window.closeFinancialSettings();
    window.closeSportsSettings();
};
```

---

## 5. Universal "BOTH" Handling Specification (R2)

### 5.1 Setting State Flow
1. **User Interaction**:
   - The Auto-Trading Universe 3-way toggle `[ Crypto ]` `[ Sports ]` `[ Both ]` is present in both `financialSettingsDrawer` and `sportsSettingsDrawer`.
   - Clicking `[ Both ]` in either drawer calls `window.setAutoTradingUniverse('BOTH')`.
2. **`window.setAutoTradingUniverse` Implementation**:
   ```javascript
   window.setAutoTradingUniverse = function(univ, skipSave = false) {
       const raw = (univ || 'CRYPTO').toUpperCase();
       const normalized = (raw === 'FINANCIAL' || raw === 'CRYPTO') ? 'CRYPTO' : raw;
       window.configuredTradingUniverse = normalized;

       // Select all matching button controls in both drawers
       const activeClass = "flex-1 py-1.5 text-[10px] font-bold tracking-wider rounded-lg transition-all text-white bg-cyan-500/25 border border-cyan-500/40 shadow-sm flex items-center justify-center gap-1 cursor-pointer";
       const activeBothClass = "flex-1 py-1.5 text-[10px] font-bold tracking-wider rounded-lg transition-all text-white bg-emerald-500/25 border border-emerald-500/40 shadow-sm flex items-center justify-center gap-1 cursor-pointer";
       const inactiveClass = "flex-1 py-1.5 text-[10px] font-bold tracking-wider rounded-lg transition-all text-gray-400 hover:text-white border border-transparent flex items-center justify-center gap-1 cursor-pointer";

       document.querySelectorAll('.btn-auto-univ-crypto').forEach(b => b.className = (normalized === 'CRYPTO') ? activeClass : inactiveClass);
       document.querySelectorAll('.btn-auto-univ-sports').forEach(b => b.className = (normalized === 'SPORTS') ? activeClass : inactiveClass);
       document.querySelectorAll('.btn-auto-univ-both').forEach(b => b.className = (normalized === 'BOTH' || normalized === 'ALL') ? activeBothClass : inactiveClass);

       document.querySelectorAll('.auto-universe-label-badge').forEach(badge => {
           if (normalized === 'CRYPTO') {
               badge.innerText = 'CRYPTO';
               badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-cyan-500/15 text-cyan-400 border border-cyan-500/30';
           } else if (normalized === 'SPORTS') {
               badge.innerText = 'SPORTS';
               badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-400 border border-amber-500/30';
           } else if (normalized === 'BOTH' || normalized === 'ALL') {
               badge.innerText = 'BOTH';
               badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30';
           }
       });

       if (!skipSave && typeof saveConfig === 'function') {
           saveConfig();
       }
   };
   ```
3. **`saveUserConfig` Implementation**:
   ```javascript
   const payload = {
       // ... other fields ...
       trading_universe: (window.configuredTradingUniverse === 'CRYPTO' ? 'FINANCIAL' : (window.configuredTradingUniverse || 'FINANCIAL')),
       // ...
   };
   ```
4. **`selectUniverse` Decoupling Fix**:
   - **DELETE**: `window.lastDashboardStats.trading_universe = universe;`.
   - Replace with:
     ```javascript
     // Pure client-side view switch; do NOT mutate configured trading_universe
     window.currentUniverse = universe;
     ```
5. **`populateUserSettings` Consistency**:
   - When `s.trading_universe` arrives from `/api/auth/dashboard_stats`:
     ```javascript
     if (s.trading_universe !== undefined) {
         const tu = String(s.trading_universe).toUpperCase();
         setAutoTradingUniverse(tu, true); // Updates buttons and badges in both menus
     }
     ```
   - Does NOT touch `window.currentUniverse` if already active, preserving whatever tab the user is viewing.

---

## 6. Form Controls, Event Listeners, and Race Condition Audit

### 6.1 Sliders and Synchronized Readouts
- **`#sports-conf-slider`**:
  - Bound via `oninput="document.getElementById('sports-conf-val').innerText = this.value + '.0%'; saveUserConfig();"`.
  - Works correctly, but input event triggers high-frequency `saveUserConfig()` calls.
  - *Recommendation*: Debounce `saveUserConfig` on slider drag (e.g. 300ms) while keeping DOM readout update immediate.
- **`#sports-edge-slider`**:
  - Bound via `oninput="document.getElementById('sports-edge-val').innerText = '+' + this.value + '.0%'; saveUserConfig();"`.
  - Also benefits from debounced save.
- **`#train-window`**:
  - Bound via `oninput="document.getElementById('train-win-val').innerText=this.value"`. Readout syncs properly.

### 6.2 Naming Collisions and ID Disambiguation
- When replicating shared controls across two drawers:
  - Do NOT duplicate HTML `id` attributes.
  - Use classes for multi-element synchronizers: `.btn-auto-univ-crypto`, `.btn-auto-univ-sports`, `.btn-auto-univ-both`, `.auto-universe-label-badge`.
  - Or use distinct IDs: `header-auto-toggle-fin` and `header-auto-toggle-sports`, with a shared `toggleAutoTrader(enabled)` that updates both checkboxes.

### 6.3 Race Conditions in `populateUserSettings` vs User Edits
In `populateUserSettings(s, force = false)`:
```javascript
const isSettingsOpen = window.isSettingsOpen;
const isFocusInSettings = document.activeElement && (
    document.getElementById('financialSettingsDrawer')?.contains(document.activeElement) ||
    document.getElementById('sportsSettingsDrawer')?.contains(document.activeElement)
);

if (!force && window.userSettingsPopulated && (isSettingsOpen || isFocusInSettings)) {
    return; // Prevents background polling from overwriting user input while editing
}
```
This guard protects against background polling collisions and must be maintained across both drawers.

---

## 7. Actionable Implementation Checklist

### For the SWE Implementer:
- [ ] **Step 1: HTML Structure (`saas_dashboard.html`)**:
  - Refactor lines 6989–8408 into `<div id="financialSettingsDrawer">` and `<div id="sportsSettingsDrawer">`.
  - Place Financial-only groups in `financialSettingsDrawer`.
  - Place Sports-only groups in `sportsSettingsDrawer`.
  - Place synchronized controls (Auto Trader toggle, Trading Mode, Auto Universe selector with "BOTH", API keys, Sign Out) in both.
- [ ] **Step 2: Drawer Controller (`saas_dashboard.html`)**:
  - Implement `openFinancialSettings()`, `closeFinancialSettings()`, `openSportsSettings()`, `closeSportsSettings()`.
  - Update `openSettings()` to route to the drawer matching the active tab.
  - Bind swipe-to-close listeners to both panels.
- [ ] **Step 3: Decouple Tab Switching & Fix "BOTH" Bug**:
  - Remove line 237894 `window.lastDashboardStats.trading_universe = universe;`.
  - Update `setAutoTradingUniverse` to query `.btn-auto-univ-*` across both drawers.
  - Ensure "BOTH" highlights cleanly in emerald on both menus.
- [ ] **Step 4: Performance & Stutter Optimization (`saas_dashboard.html` & `app.js`)**:
  - Eliminate `showChartLoader()` and HUD element blanking in `selectDashboardAsset` during tab transitions.
  - Render sports events immediately from cache when swapping to Sports.
  - Add dirty-checking cache to `window.renderTradesContainer`.
  - Deduplicate 1-second interval timer registrations.
  - In `selectUniverse('FINANCIAL')`, call `lwChart.timeScale().fitContent()` to resize the canvas smoothly without recreating it.
- [ ] **Step 5: Automated Verification**:
  - Run `python -m pytest tests/test_frontend_contracts.py tests/test_r2_r5_multi_universe_and_timestamps.py tests/test_r3_r4_ui_and_rate_limits.py`.
  - Execute end-to-end test verifying `"BOTH"` persistence across settings API and reload cycles.

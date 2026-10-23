# Frontend Survey Report: Decoupling Financial & Sports Settings Drawers

**Explorer**: explorer_survey_1  
**Date**: 2026-10-07  
**Target Codebase**: `static/saas_dashboard.html`, `static/js/app.js`, `static/css/mobile-polish.css`, `backend/auth/routes.py`, `backend/database/models.py`  
**Mission**: Comprehensive survey of the settings drawer architecture and recommendations to decouple the shared drawer into dedicated Financial and Sports Universe settings drawers with seamless "BOTH" universe persistence.

---

## 1. Executive Summary

In `static/saas_dashboard.html`, a single shared settings drawer (`#settingsDrawer`, lines 6989–8408) currently attempts to serve both the Financial (crypto/forex) and Sports universes. It uses dynamic CSS class toggling (`.finance-only-setting` vs `.sports-only-setting`) and JS DOM mutations within `window.selectUniverse()` to show/hide sections on tab switches. 

This survey identified:
1. **Structural Flaws & DOM Inconsistencies**: An unclosed `<div>` in the Sports Market Types section (line 7502) distorts the HTML parse tree, causing subsequent elements to nest erroneously.
2. **Hidden Runtime Error in Settings Saving**: In `saveUserConfig()`, line 1709 references `sportsActivePropsStr`, which is **never defined or collected**, throwing an uncaught `ReferenceError: sportsActivePropsStr is not defined` whenever settings are saved.
3. **Tab-Switching Overhead**: Every time the user swaps between Financial and Sports tabs, `selectUniverse()` queries and modifies 50+ DOM elements inside the closed drawer, causing UI stutter and lag.
4. **Clean Decoupling Blueprint**: A complete separation into `<div id="financialSettingsDrawer">` and `<div id="sportsSettingsDrawer">`, with unified state synchronization for common controls (such as the Auto-Trading Universe "BOTH" selector, Paper/Live mode, and audio/notification toggles), eliminates DOM thrashing, isolates universe configurations, and satisfies all acceptance criteria in `ORIGINAL_REQUEST.md`.

---

## 2. Current Architecture & Anatomy of `#settingsDrawer`

### 2.1 DOM Structure (Lines 6989–8408)
- **Root Overlay**: `<div id="settingsDrawer" class="fixed inset-0 z-[200] hidden">`
- **Backdrop**: `<div id="settingsBackdrop" class="absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0 transition-opacity duration-300" onclick="closeSettings()"></div>`
- **Slide-Over Panel**: `<div id="settingsPanel" class="absolute right-0 top-0 bottom-0 w-full sm:w-[440px] max-w-[95vw] bg-[#0c101a]/95 border-l border-white/[0.08] shadow-[0_0_60px_rgba(0,0,0,0.95)] flex flex-col transform translate-x-full transition-transform duration-300 ease-out select-none">`
- **Swipe-to-Close Edge Bar**: Subtle bar for mobile swipe gestures.
- **Top Bar**:
  - Title: `<h2 id="settings-drawer-title">Financials Settings</h2>`
  - Universe Badge: `<span id="settings-universe-badge">📈 FINANCIALS</span>`
  - Status Badge: `<span id="settings-status-badge">Auto-Saved</span>`
  - Subtitle: `<span id="settings-drawer-subtitle">Algorithmic risk limits & parameters...</span>`
  - Close Button: `<button onclick="closeSettings()">`
- **Scrollable Container**: `<div class="flex-1 overflow-y-auto hide-scrollbar px-4 py-4 space-y-6">`

### 2.2 Complete Element Inventory by Section

#### Section 1: Account, Environment & Auto-Trading (Lines 7025–7083)
| Element Description | ID / Selector | Type | Event Handler | Scope |
|---|---|---|---|---|
| Paper Sandbox Button | `btn-mode-paper-settings` | `<button>` | `setTradingMode('PAPER')` | Shared |
| Live Real $ Button | `btn-mode-live-settings` | `<button>` | `setTradingMode('LIVE')` | Shared |
| Financials Menu Pill | `btn-universe-fin-settings` | `<button>` | `selectUniverse('FINANCIAL')` | Shared (Obsolete in decoupled) |
| Sports Menu Pill | `btn-universe-sports-settings` | `<button>` | `selectUniverse('SPORTS')` | Shared (Obsolete in decoupled) |
| Auto Execution Toggle | `header-auto-toggle` | `<input type="checkbox">` | `toggleAutoTrader(this.checked)` | Shared |
| Auto-Universe Container | `auto-trading-universe-container` | `<div>` | N/A | Shared |
| Auto-Universe Badge | `auto-universe-label-badge` | `<span>` | N/A | Shared |
| Auto-Universe Crypto | `btn-auto-univ-crypto` | `<button>` | `setAutoTradingUniverse('CRYPTO')` | Shared |
| Auto-Universe Sports | `btn-auto-univ-sports` | `<button>` | `setAutoTradingUniverse('SPORTS')` | Shared |
| Auto-Universe Both | `btn-auto-univ-both` | `<button>` | `setAutoTradingUniverse('BOTH')` | Shared |

#### Section 2: Financial Active Assets (Lines 7084–7172)
*Container: `<div id="finance-asset-settings" class="finance-only-setting">`*
| Asset | Input ID | Class | Value | Handler |
|---|---|---|---|---|
| BTC | `asset-btc-toggle` | `asset-toggle` | `BTC` | `saveUserConfig()` |
| ETH | `asset-eth-toggle` | `asset-toggle` | `ETH` | `saveUserConfig()` |
| GOLD | `asset-gold-toggle` | `asset-toggle` | `GOLD` | `saveUserConfig()` |
| SOL | `asset-sol-toggle` | `asset-toggle` | `SOL` | `saveUserConfig()` |
| DOGE | `asset-doge-toggle` | `asset-toggle` | `DOGE` | `saveUserConfig()` |
| EUR/USD | `asset-eurusd-toggle` | `asset-toggle` | `EURUSD` | `saveUserConfig()` |
| GBP/USD | `asset-gbpusd-toggle` | `asset-toggle` | `GBPUSD` | `saveUserConfig()` |
| USD/JPY | `asset-usdjpy-toggle` | `asset-toggle` | `USDJPY` | `saveUserConfig()` |
| AUD/USD | `asset-audusd-toggle` | `asset-toggle` | `AUDUSD` | `saveUserConfig()` |
| NDQ | `asset-ndq-toggle` | `asset-toggle` | `NDQ` | `saveUserConfig()` |

#### Section 3: Financial Capital & Risk Protection (Lines 7179–7418)
*Container: `<div id="finance-risk-settings" class="finance-only-setting">`*
| Control Name | Element ID | Type | Handler |
|---|---|---|---|
| Trade Size ($) | `trade-size-dollars` | `<input type="number">` | `saveUserConfig()` |
| Kelly Criterion Sizing | `kelly-criterion-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| Dynamic ATR Risk Toggle | `atr-risk-toggle` | `<input type="checkbox">` | `saveUserConfig(); refreshAtrReadout(true);` |
| ATR Mult Readout | `atr-mult-readout` | `<span>` | N/A |
| Multi-Entry DCA Toggle | `second-entry-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| Multi-Entry Max Ask (¢) | `second-entry-max-ask` | `<input type="number">` | `saveUserConfig()` |
| Stop Loss Pct (%) | `stop-loss-pct` | `<input type="number">` | `saveUserConfig()` |
| Stop Loss Toggle | `stop-loss-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| AI Stop Loss Rec | `sl-recommendation`, `sl-rec-value` | `<span>` | `fetchTpSlRecommendations()` |
| Dip Re-entry Toggle | `reentry-after-stoploss-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| Take Profit Target (%) | `take-profit-pct` | `<input type="number">` | `saveUserConfig()` |
| Take Profit Toggle | `take-profit-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| AI Take Profit Rec | `tp-recommendation`, `tp-rec-value` | `<span>` | `fetchTpSlRecommendations()` |
| Trailing Stop Toggle | `trailing-stop-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| Trailing Stop Activation | `trailing-stop-activation-pct` | `<input type="number">` | `saveUserConfig()` |
| Trailing Stop Gap | `trailing-stop-distance-pct` | `<input type="number">` | `saveUserConfig()` |
| Daily Loss Cap ($) | `max-daily-risk` | `<input type="number">` | `saveUserConfig()` |
| Daily Trade Limit | `max-daily-trades` | `<input type="number">` | `saveUserConfig()` |

#### Section 4: Sports Universe Settings (Lines 7419–7874)
*Container: `<div id="sports-risk-settings" class="hidden sports-only-setting">`*
| Control Name | Element ID / Selector | Type | Values / Handler |
|---|---|---|---|
| Active Leagues (7) | `.sports-league-toggle` | `<input type="checkbox">` | `NFL`, `MLB`, `NHL`, `SOC`, `UFC`, `TEN`, `NPB/KBO` |
| Market Types (5) | `.sports-market-toggle` | `<input type="checkbox">` | `GAME`, `SPREAD`, `TOTAL`, `PROP`, `INNING` |
| Player Props (9) | `.sports-prop-toggle` | `<input type="checkbox">` | `ANYTIME_TD`, `PASSING_YDS`, `RUSHING_YDS`, `RECEIVING_YDS`, `HOME_RUNS`, `STRIKEOUTS`, `HITS_RUNS_RBIS`, `TOTAL_BASES`, `OTHER` |
| Sports Trade Size ($) | `sports-trade-size-dollars` | `<input type="number">` | `saveUserConfig()` |
| Sports Wager Hidden | `sports-wager-dollars` | `<input type="hidden">` | Fallback value sync |
| Kelly / Edge-Scaled Sizing | `sports-kelly-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| Price Corridor Min (¢) | `sports-min-price` | `<input type="number">` | `saveUserConfig()` |
| Price Corridor Max (¢) | `sports-max-price` | `<input type="number">` | `saveUserConfig()` |
| Mid-Game Take-Profit (%) | `sports-tp-pct` | `<input type="number">` | `saveUserConfig()` |
| Mid-Game Take-Profit Toggle | `sports-tp-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| Max Daily Risk ($) | `sports-max-daily-risk` | `<input type="number">` | `saveUserConfig()` |
| Max Daily Wagers | `sports-max-daily-trades` | `<input type="number">` | `saveUserConfig()` |
| Max Open Bets | `sports-max-open-trades` | `<input type="number">` | `saveUserConfig()` |
| Include Live In-Progress | `sports-include-live-toggle` | `<input type="checkbox">` | `saveUserConfig(); renderSportsEvents();` |
| Minimum Pick Confidence | `sports-conf-slider`, `sports-conf-val` | `<input type="range">` | Range 50–95%, `saveUserConfig()` |
| Minimum Edge | `sports-edge-slider`, `sports-edge-val` | `<input type="range">` | Range 0–25%, `saveUserConfig()` |

#### Section 5: Wallet Operations (Lines 7876–7931)
*Container: `<div class="finance-only-setting">`*
| Control Name | Element ID | Type | Handler |
|---|---|---|---|
| Refresh Balances Button | N/A | `<button>` | `refreshWalletBalances()` |
| Main Wallet Balance | `wallet-main-bal` | `<span>` | N/A |
| Crypto Wallet Balance | `wallet-crypto-bal` | `<span>` | N/A |
| Transfer Direction | `transfer-direction` | `<select>` | `main_to_crypto` / `crypto_to_main` |
| Transfer Amount | `transfer-amount` | `<input type="number">` | N/A |
| Transfer Button | `transfer-btn` | `<button>` | `executeWalletTransfer()` |
| Status Message | `transfer-status` | `<div>` | N/A |

#### Section 6: AI Strategy & Signal Controls (Lines 8018–8153)
*Container: `<div class="finance-only-setting">`*
| Control Name | Element ID | Type | Handler / Options |
|---|---|---|---|
| Trading Strategy Style | `trading-style` | `<select>` + Custom Dropdown | `AUTO`, `PREDICTION`, `SNIPER`, `MOMENTUM_SURFER`, `AMBUSH`, `CHOP`, `CAPITAL_GUARD` |
| Signal Intelligence Source | `signal-source` | `<select>` + Custom Dropdown | `AUTO`, `BLEND`, `AI_ONLY`, `CHART_ONLY` |
| 1-Shot Snipe Mode | `one-shot-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| 1-Click Trade Execution | `one-click-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| Force Trade on PASS | `force-trade-toggle` | `<input type="checkbox">` | `saveUserConfig()` |
| Bypass Technical Vetoes | `technical-force-toggle` | `<input type="checkbox">` | `saveUserConfig()` |

#### Section 7: Interface & Charting (Lines 8155–8217)
*Container: `<div class="finance-only-setting">`*
| Control Name | Element ID | Type | Handler |
|---|---|---|---|
| Chart Type | `settings-chart-type` | `<select>` | `line` / `candle`, `window.updateChartSettings()` |
| Historical Timeframe | `settings-chart-timeframe` | `<select>` | `1m`, `5m`, `15m`, `1d`, `window.updateChartSettings()` |
| Trade Execution Panel | `toggle-trade-exec-panel` | `<input type="checkbox">` | `window.toggleTradeExecutionPanel(this.checked)` |

#### Section 8: Machine Learning & Hyperparameters (Lines 8218–8348)
*Container: `<div class="finance-only-setting">`*
| Control Name | Element ID | Type | Handler / Range |
|---|---|---|---|
| AI Model Choice | `model-choice` | `<select>` + Custom Dropdown | `Swarm`, `RL_DQN`, `RL_PRICED`, `XGBOOST`, `LOGISTIC_REGRESSION` |
| Lookback Window | `train-window`, `train-win-val` | `<input type="range">` | 30 to 4000 candles |
| Regularization C | `reg-c` | `<input type="number">` | 0.1 to 10.0 |
| Class Weighting | `class-weight` | `<select>` + Custom Dropdown | `balanced` vs `none` |
| XGB Estimators | `xgb-estimators` | `<input type="number">` | 10 to 1000 trees |
| XGB Max Depth | `xgb-max-depth` | `<input type="number">` | 1 to 10 depth |
| XGB Learning Rate | `xgb-learning-rate` | `<input type="number">` | 0.01 to 1.00 |

#### Section 9: Credentials, Updates, Audio, Notifications & Destructive (Lines 7933–8015, 8349–8408)
| Control Name | Element ID | Type | Handler / Action | Scope |
|---|---|---|---|---|
| Audio Sound Effects Toggle | `settings-sound-toggle` | `<input type="checkbox">` | `toggleSound(this.checked)` | Shared |
| Audio Status Text | `settings-sound-status` | `<span>` | N/A | Shared |
| Audio Test Chime Preview | N/A | `<button>` | `soundEngine.init(); soundEngine.play('order_fill');` | Shared |
| Push Notifications Toggle | `ios-notify-toggle` | `<input type="checkbox">` | `window.toggleIosNotifications(this.checked)` | Shared |
| Updates Modal Button | N/A | `<button>` | `openUpdateModal(); closeSettings();` | Shared |
| Updates Indicator Dot | `settings-updates-dot` | `<span>` | N/A | Shared |
| Kalshi Key ID | `kalshi-key` | `<input type="text">` | N/A | Financial |
| Kalshi RSA PEM Key | `kalshi-priv` | `<textarea>` | N/A | Financial |
| Save Keys Button | N/A | `<button>` | `saveKeys()` | Financial |
| Admin Console Link | `admin-console-group` | `<a>` | `./admin_mobile.html` | Shared |
| Sign Out Button | N/A | `<button>` | `logout()` | Shared |

---

## 3. Critical Bugs Discovered

### Bug A: Unclosed `<div>` in Market Types
- **Location**: `saas_dashboard.html`, line 7502.
- **Cause**: The section `<div class="bg-[#131b2c]...">` opened two child `<div>`s (`bg` container and `grid`), but only closed two tags (`</div></div>` at lines 7553-7554), leaving the outer wrapper unclosed.
- **Impact**: In strict DOM parsing, the net tag balance of the drawer is `382 <div` vs `381 </div`. This causes all subsequent elements (Player Props, Wallet Operations, Sound, Push Notifications) to be treated as children of the open section.

### Bug B: Uncaught `ReferenceError: sportsActivePropsStr is not defined`
- **Location**: `saas_dashboard.html`, line 1709 in `saveUserConfig()`.
- **Code**:
  ```javascript
  sports_market_types: sportsMarketTypesStr,
  sports_active_props: sportsActivePropsStr // <-- Throws ReferenceError!
  ```
- **Cause**: `activeSportsMarketTypes` is collected at lines 1646-1651, but `sportsActivePropsStr` is never collected before line 1709.
- **Impact**: When any sports setting is saved, the configuration payload creation crashes immediately, preventing settings from persisting to the backend!

---

## 4. Decoupling Blueprint: Financial vs Sports Drawers

To fulfill **Requirement R1**, the single shared drawer is separated into two dedicated, top-level drawers in `static/saas_dashboard.html`:
1. `<div id="financialSettingsDrawer">` — Dedicated Financial Universe Settings Drawer
2. `<div id="sportsSettingsDrawer">` — Dedicated Sports Universe Settings Drawer

### 4.1 Component Breakdown Matrix

| Section / Capability | Financial Drawer | Sports Drawer | Notes |
|---|:---:|:---:|---|
| **Theme / Accent** | Cyan (`cyan-500`) | Amber (`amber-500`) | Visual distinction per universe |
| **Drawer Header** | "Financials Settings" + 📈 | "Sports Universe Settings" + 🏈 | Clear header and swipe bar |
| **Trading Mode (Paper/Live)** | Included | Included | Synced across both menus |
| **Auto Execution Switch** | Included (`header-auto-toggle`) | Included (`sports-header-auto-toggle`) | Synced with backend `ai_enabled` |
| **Auto-Trading Universe** | CRYPTO / SPORTS / BOTH | CRYPTO / SPORTS / BOTH | Synced via `setAutoTradingUniverse()` |
| **Active Assets** | BTC, ETH, SOL, etc. | None | Strictly crypto/forex |
| **Active Leagues** | None | NFL, MLB, NHL, SOC, UFC, etc. | Strictly sports leagues |
| **Market Types & Props** | None | Winners, Spreads, Totals, Props | Strictly sports markets |
| **Trade Sizing** | `trade-size-dollars` | `sports-trade-size-dollars` | Independent universe sizing |
| **Risk / Circuit Breaker** | Financial Stop Loss, TP, Trailing Stop | Sports Max Wagers, Mid-Game TP | Separate risk engines |
| **AI Controls** | Conviction, Regime, 1-Shot, Kelly | Confidence slider, Edge slider, Kelly | Universe-specific model parameters |
| **Machine Learning** | Ensemble, XGB, Reg-C, Depth | None | Financial ML tuning |
| **Wallet Operations** | Main & Crypto transfer | None | Financial exchange wallet |
| **Exchange Keys** | Kalshi API Key & RSA PEM | None | Financial order credentials |
| **Audio & Sounds** | Included | Included | Sound cues toggle |
| **Push Notifications** | Included | Included | Mobile notifications |
| **Updates & Sign Out** | Included | Included | Common system utilities |

### 4.2 DOM Structure & Identifiers

#### Financial Drawer DOM Skeleton:
```html
<!-- Financial Universe Settings Drawer -->
<div id="financialSettingsDrawer" class="fixed inset-0 z-[200] hidden">
    <div id="financialSettingsBackdrop" class="absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0 transition-opacity duration-300" onclick="closeSettings()"></div>
    <div id="financialSettingsPanel" class="absolute right-0 top-0 bottom-0 w-full sm:w-[440px] max-w-[95vw] bg-[#0c101a]/95 border-l border-white/[0.08] shadow-[0_0_60px_rgba(0,0,0,0.95)] flex flex-col transform translate-x-full transition-transform duration-300 ease-out select-none">
        <!-- Header -->
        <div class="flex items-center justify-between px-5 pb-4 border-b border-white/[0.08] bg-black/40 backdrop-blur-xl shrink-0 cursor-grab active:cursor-grabbing">
            <div class="flex flex-col">
                <div class="flex items-center gap-2">
                    <h2 class="text-white font-bold tracking-tight text-base">Financials Settings</h2>
                    <span class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 flex items-center gap-1">📈 FINANCIALS</span>
                    <span class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">Auto-Saved</span>
                </div>
                <span class="text-[10px] text-gray-400 font-medium">Algorithmic risk limits & crypto trading parameters • Swipe right to close</span>
            </div>
            <button onclick="closeSettings()" class="w-8 h-8 flex items-center justify-center bg-white/10 hover:bg-white/20 text-gray-300 hover:text-white rounded-full transition-all">✕</button>
        </div>
        <!-- Scrollable content strictly containing Sections 1, 2, 3, 5, 6, 7, 8, 9 -->
    </div>
</div>
```

#### Sports Drawer DOM Skeleton:
```html
<!-- Sports Universe Settings Drawer -->
<div id="sportsSettingsDrawer" class="fixed inset-0 z-[200] hidden">
    <div id="sportsSettingsBackdrop" class="absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0 transition-opacity duration-300" onclick="closeSettings()"></div>
    <div id="sportsSettingsPanel" class="absolute right-0 top-0 bottom-0 w-full sm:w-[440px] max-w-[95vw] bg-[#0c101a]/95 border-l border-white/[0.08] shadow-[0_0_60px_rgba(0,0,0,0.95)] flex flex-col transform translate-x-full transition-transform duration-300 ease-out select-none">
        <!-- Header -->
        <div class="flex items-center justify-between px-5 pb-4 border-b border-white/[0.08] bg-black/40 backdrop-blur-xl shrink-0 cursor-grab active:cursor-grabbing">
            <div class="flex flex-col">
                <div class="flex items-center gap-2">
                    <h2 class="text-white font-bold tracking-tight text-base">Sports Universe Settings</h2>
                    <span class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1">🏈 SPORTS</span>
                    <span class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">Auto-Saved</span>
                </div>
                <span class="text-[10px] text-gray-400 font-medium">Sports AI edge, wager sizing & pick controls • Swipe right to close</span>
            </div>
            <button onclick="closeSettings()" class="w-8 h-8 flex items-center justify-center bg-white/10 hover:bg-white/20 text-gray-300 hover:text-white rounded-full transition-all">✕</button>
        </div>
        <!-- Scrollable content strictly containing Sports Sections 1 (Mode/Auto), 4 (Leagues, Markets, Props, Wager, Risk, AI Intelligence) & Common Utilities -->
    </div>
</div>
```

---

## 5. Interaction, Gestures, and Animation Mechanics

### 5.1 Open & Close Mechanics
```javascript
function openSettings(universe) {
    const targetUniv = universe || window.currentUniverse || 'FINANCIAL';
    const isSports = (targetUniv === 'SPORTS');
    
    // Select the appropriate drawer and panel
    const drawer = document.getElementById(isSports ? 'sportsSettingsDrawer' : 'financialSettingsDrawer');
    const panel = document.getElementById(isSports ? 'sportsSettingsPanel' : 'financialSettingsPanel');
    const backdrop = document.getElementById(isSports ? 'sportsSettingsBackdrop' : 'financialSettingsBackdrop');
    
    // Close the opposite drawer if open
    const otherDrawer = document.getElementById(isSports ? 'financialSettingsDrawer' : 'sportsSettingsDrawer');
    if (otherDrawer && !otherDrawer.classList.contains('hidden')) {
        closeSettings();
    }
    
    window.isSettingsOpen = true;
    window.activeSettingsDrawer = isSports ? 'SPORTS' : 'FINANCIAL';
    
    // Synchronize UI data
    if (typeof populateUserSettings === 'function' && window.lastDashboardStats) {
        populateUserSettings(window.lastDashboardStats, false);
    }
    
    if (drawer) drawer.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            if (panel) {
                panel.classList.remove('translate-x-full');
                panel.classList.add('translate-x-0');
            }
            if (backdrop) {
                backdrop.classList.remove('opacity-0');
                backdrop.classList.add('opacity-100');
            }
        });
    });
}

function closeSettings() {
    window.isSettingsOpen = false;
    ['financial', 'sports'].forEach(prefix => {
        const drawer = document.getElementById(`${prefix}SettingsDrawer`);
        const panel = document.getElementById(`${prefix}SettingsPanel`);
        const backdrop = document.getElementById(`${prefix}SettingsBackdrop`);
        if (panel) {
            panel.classList.remove('translate-x-0');
            panel.classList.add('translate-x-full');
        }
        if (backdrop) {
            backdrop.classList.remove('opacity-100');
            backdrop.classList.add('opacity-0');
        }
        if (drawer && !drawer.classList.contains('hidden')) {
            setTimeout(() => { drawer.classList.add('hidden'); }, 300);
        }
    });
    document.body.style.overflow = '';
}
```

### 5.2 Swipe Gestures & Mobile CSS Compatibility
In `static/css/mobile-polish.css`, selectors currently target `#settingsDrawer` and `#settingsPanel`. These should be extended:
```css
#settingsDrawer,
#financialSettingsDrawer,
#sportsSettingsDrawer,
#tradeDetailsModal {
  z-index: 1000 !important;
}

#financialSettingsDrawer .overflow-y-auto,
#sportsSettingsDrawer .overflow-y-auto,
#financialSettingsPanel,
#sportsSettingsPanel {
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}

#financialSettingsPanel,
#sportsSettingsPanel {
  transition-timing-function: cubic-bezier(0.32, 0.72, 0, 1);
}
```

The gesture listeners in `initSettingsSwipeToClose()` should be attached to both panels so that horizontal swiping dismisses either drawer with native 60fps fluidity.

---

## 6. Auto-Trading Universe "BOTH" Persistence (Requirement R2)

### 6.1 Backend Contract Verification
- Database Schema (`backend/database/models.py` line 410):
  `VALID_TRADING_UNIVERSES = {"FINANCIAL", "SPORTS", "BOTH", "ALL"}`
- User Config Route (`backend/auth/routes.py` lines 67–75, 1631–1635):
  Accepts and validates `trading_universe: "BOTH"`, calling `update_user_trading_universe(user_id, "BOTH")`.
- Auto-Executors (`saas_broadcaster.py:177`, `sports_bridge/executor.py:350`):
  Both engines evaluate trades if `trading_universe in ('FINANCIAL', 'BOTH', 'ALL')` and `('SPORTS', 'BOTH', 'ALL')` respectively.

### 6.2 Dual-Drawer Frontend Sync Pattern
In both the Financial Drawer and the Sports Drawer:
- Include the explicit segmented control for Auto-Trading Universe (`CRYPTO`, `SPORTS`, `BOTH`).
- In `setAutoTradingUniverse(univ, skipSave = false)`:
  - Normalize input (`'BOTH'` stays `'BOTH'`).
  - Update segmented button active styles in **both** Financial and Sports drawer controls.
  - Update universe badge in **both** drawers to display `BOTH` with emerald green styling.
  - When saving via `saveUserConfig()`, post `trading_universe: window.configuredTradingUniverse`.
  - When `populateUserSettings(stats)` runs, it calls `setAutoTradingUniverse(stats.trading_universe, true)`, ensuring `'BOTH'` is immediately reflected in both menus.

---

## 7. Tab Switching UI/UX Optimization (Requirement R3)

### 7.1 Root Cause of Current Tab Lag
In `static/saas_dashboard.html`:
Lines 3780–3865 inside `window.selectUniverse(universe)` perform heavy DOM queries:
- `document.querySelectorAll('.finance-only-setting').forEach(...)`
- `document.querySelectorAll('.sports-only-setting').forEach(...)`
- Rewriting drawer title text, subtitle innerHTML, universe badge classes, and segmented button classes on **every** tab switch.

### 7.2 Optimization Strategy
With decoupled drawers:
1. **Zero Drawer Re-layout on Tab Switch**: `selectUniverse()` completely stops querying or altering settings drawer DOM elements.
2. **Instant Viewport Toggle**: Tab switching only toggles the active dashboard view (the chart vs sports events container and the asset pill bar).
3. **No Dynamic Class Flickering**: Eliminating repeated `.classList.add('hidden')` and `.classList.remove('hidden')` loops avoids browser style recalculation and layout thrashing, resulting in instantaneous, stutter-free 60fps tab switching.

---

## 8. Summary of Proposed Changes for Implementers

1. **HTML (`static/saas_dashboard.html`)**:
   - Replace lines 6988–8408 with two strictly decoupled drawer containers: `#financialSettingsDrawer` and `#sportsSettingsDrawer`.
   - Remove obsolete "Show settings for: Financials Menu / Sports Menu" selector pills.
   - Fix the unclosed `<div>` in the Sports Market Types section.
   - Provide distinct IDs or synchronized class targets for shared controls (Paper/Live mode buttons, auto-trader toggle, auto-trading universe selector).
2. **JavaScript (`static/saas_dashboard.html` / `static/js/app.js`)**:
   - Update `openSettings(universe)` to route to the correct drawer based on parameter or active tab.
   - Update `closeSettings()` to handle closing either active drawer.
   - Update `initSettingsSwipeToClose()` to bind touch and mouse events to both panels.
   - In `saveUserConfig()`, fix the bug by collecting `sportsActivePropsStr` before building `configPayload`.
   - In `setAutoTradingUniverse()`, update the segmented control active states across both drawers.
   - In `window.selectUniverse()`, strip out all settings drawer DOM manipulation to eliminate tab switching lag.
3. **CSS (`static/css/mobile-polish.css`)**:
   - Add `#financialSettingsDrawer`, `#sportsSettingsDrawer`, `#financialSettingsPanel`, and `#sportsSettingsPanel` to all modal, z-index, overscroll, and cubic-bezier rules.

---
*End of Survey Report*

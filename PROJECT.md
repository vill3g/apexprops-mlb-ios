# Project: ShadowTrader AI Audit & Remediation

## Architecture
- **Supervision & Process Model**: `server_watchdog.py` supervises `launch_desktop.py` (which launches `backend/worker.py` and `uvicorn backend.main:app` on port 8058) and `ngrok`.
- **Backend Core**: FastAPI application in `backend/main.py` routing to modular endpoints in `backend/routes/` and `backend/auth/`.
- **Trading Engine**: `backend/btc/auto_executor/` (including `executor.py` and `saas_broadcaster.py`) executing 15-minute interval evaluations, Kalshi order placements via `kalshi_trader.py`, and trade settlement via `saas_settler.py`.
- **Frontend Dashboard**: `static/saas_dashboard.html` with auxiliary pages `login.html`, `trades.html`, `admin_mobile.html`, and scripts `static/js/app.js`, `dashboard.js`, `admin_users.js`.
- **Mobile Packaging**: iOS Capacitor wrapper configured via `capacitor.config.json` serving bundled assets from `static/`.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Kalshi 429 Retry Fix | Fix `@retry` in `kalshi_trader.py` to inspect HTTP status and retry on 429 with exponential backoff across all trading methods | M1 | explorer_1 |
| 2 | Settlement 429 Storm Elimination | Add per-ticker backoff/negative caching in `saas_settler.py` for unresolved contracts | M1 | explorer_1 |
| 3 | Raw Features List Crash Fix | Fix `'list' object has no attribute 'get'` in `saas_broadcaster.py` and `executor.py` | M1 | explorer_1 |
| 4 | Desktop Launcher Venv Fallback | Fix `launch_desktop.py` hardcoded `.venv` path to fall back to `sys.executable` | M1 | explorer_1 |
| 5 | Worker Log Flooding & Mutex Collision | Throttle worker loop logging in `worker.py` and prevent mutex collision in `server_watchdog.py` | M1 | explorer_1 |
| 6 | Forex Paper State Log Guard | Guard negative paper balance in `backend/forex/auto_executor.py` against spamming warnings | M1 | explorer_1 |
| 7 | Indicator Import Re-export | Re-export `add_all_indicators` in `backend/btc/auto_executor/__init__.py` | M1 | explorer_1 |
| 8 | Robust API Exception Boundaries | Broaden fragile 8-exception tuples in API routes to gracefully catch and return 500s | M1 | explorer_1 |
| 9 | Settings Drawer Unclosed Div | Close `<div id="settingsDrawer">` at line 6097 in `saas_dashboard.html` | M2 | explorer_2 |
| 10 | iOS Bottom Safe Area Insets | Add `env(safe-area-inset-bottom)` to sticky modal buttons, drawer, and main container | M2 | explorer_2 |
| 11 | Corrupted Tailwind Classes Restoration | Restore `-2xl`, `-xl`, `-sm` to `backdrop-blur-*` in `saas_dashboard.html` | M2 | explorer_2 |
| 12 | Retire Obsolete Update Modal | Remove duplicate `#updateAlertModal` with broken FontAwesome icons in `saas_dashboard.html` | M2 | explorer_2 |
| 13 | iOS Safe Area Stylesheet Integration | Link and integrate responsive safe area rules from `app.css` into `saas_dashboard.html` | M2 | explorer_2 |
| 14 | Trades Viewport & Safe Area | Add `viewport-fit=cover` and safe area insets to `trades.html` | M2 | explorer_2 |
| 15 | Capacitor Content Inset Normalization | Set `"contentInset": "automatic"` in `capacitor.config.json` to eliminate double safe area gap | M2 | explorer_2 |
| 16 | Missing Favicon & Icon 404s | Resolve missing `./assets/app_icon.ico` and `./assets/favicon.svg` to existing `favicon.ico`/icons | M3 | explorer_3 |
| 17 | Favicon Backend Route 404 Fix | Point `/favicon.ico` in `backend/routes/ui.py` to `favicon.ico` on disk | M3 | explorer_3 |
| 18 | Capacitor WKWebView Relative Routing | Change absolute navigation links (`/admin/mobile`) to relative (`./admin_mobile.html`) | M3 | explorer_3 |
| 19 | Capacitor Relative Asset Paths | Convert `/static/assets/...` in HTML and manifest to relative `./assets/...` | M3 | explorer_3 |
| 20 | Fetch Fallback Status Validation | Fix promise `.catch()` in `app.js` with explicit `res.ok` check for offline data fallbacks | M3 | explorer_3 |
| 21 | Service Worker Root Scope Route | Mount root `/sw.js` in FastAPI with `Service-Worker-Allowed: /` header | M3 | explorer_3 |
| 22 | Bundle Size Optimization | Exclude 8.3 MB dead `ai_avatar.gif` in `update_ipa.py` | M3 | explorer_3 |
| 23 | Auto Trader Runaway 429 Loop Fix | Mark `self.last_traded_interval` and backoff on 429/rejections in `executor.py` and `saas_broadcaster.py` | M4 | explorer_3 |
| 24 | Execution Delay Non-Blocking Lock Fix | Ensure interval is flagged inflight and worker thread is not stalled during `execDelay` | M4 | explorer_3 |
| 25 | Paper Mode Order Intents Claim | Extend `order_intents.claim` to paper trading to prevent duplicate interval executions | M4 | explorer_3 |
| 26 | Auto Trader UI Toggle & Badge Sync | Clean up obsolete toggle IDs and immediately update `nav-auto-badge` in `toggleAutoTrader` | M4 | explorer_3 |
| 27 | Dynamic Island Position & 1-Shot Sync | Calibrate Dynamic Island top offset and sync state when 1-shot snipe executes | M4 | explorer_3 |
| 28 | Dynamic Asset Config Resolution | Update `loadConfig()` to query `/api/engine/${curA}/trade/config` instead of hardcoded `btc` | M4 | explorer_3 |
| 29 | Trade Config User Consistency | Fix `api_btc_trade_config_get` to respect `user_id` matching `api_btc_trade_ai_settings_get` | M4 | explorer_3 |
| 30 | Client Polling Storm Consolidation | Deduplicate polling loops between `saas_dashboard.html` and `app.js`, add `document.hidden` check | M4 | explorer_2/3 |
| 31 | E2E Testing Suite & Contract Realignment | Create comprehensive E2E test suite covering Tiers 1-4 and realign outdated contract tests | M5 | all |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Stability & Kalshi 429 Resilience | Features 1-8: `kalshi_trader.py`, `saas_settler.py`, `saas_broadcaster.py`, `executor.py`, `launch_desktop.py`, `worker.py`, `server_watchdog.py`, `indicators` | None | PLANNED |
| M2 | Frontend HTML/CSS Structure & iOS Smoothness | Features 9-15: `saas_dashboard.html`, `trades.html`, `capacitor.config.json`, safe area CSS | None | PLANNED |
| M3 | Asset & Route Integrity (Zero 404s) | Features 16-22: `ui.py`, `login.html`, `trades.html`, `app.js`, `manifest.json`, `update_ipa.py`, `main.py` | M2 | PLANNED |
| M4 | Auto Trader Logic & UI State Synchronization | Features 23-30: `executor.py`, `saas_broadcaster.py`, `saas_dashboard.html`, `engine.py`, polling deduplication | M1, M2 | PLANNED |
| M5 | E2E Testing Track & Final Verification | Feature 31: Test harness, E2E test suite (Tiers 1-4), adversarial verification (Tier 5) | M1, M2, M3, M4 | PLANNED |

---

## Interface Contracts

### Frontend Dashboard ↔ Backend API
- `GET /api/engine/{asset}/trade/config`: Returns `{ enabled: bool, mode: str, ... }` for the active asset and requesting user session.
- `POST /api/engine/{asset}/trade/toggle?enabled={bool}`: Toggles trading for the active asset and returns `{ success: bool, enabled: bool }`.
- `GET /api/auth/dashboard_stats`: Returns account statistics, open positions, and current trading state.
- `GET /api/health`: Returns `{ status: "ok" }`.

### AutoExecutor ↔ KalshiTrader
- `kalshi_trader.get_market_result(ticker)`: Must return `{ "success": bool, "result": "yes"|"no"|"", "error": str }`. Must retry on HTTP 429 with exponential backoff up to 3 attempts.
- `kalshi_trader.place_order(...)`: Must return `{ "success": bool, "order_id": str, "error": str, "ambiguous": bool }`. Must not trigger runaway execution loops on rejection.

---

## Code Layout
- Backend Source:
  - `backend/main.py`: Main FastAPI entrypoint
  - `backend/worker.py`: Background worker singleton loop
  - `backend/saas_settler.py`: Trade settlement engine
  - `backend/routes/`: Specialized API routers (`ui.py`, `engine.py`, `trading.py`, etc.)
  - `backend/btc/`: Kalshi clients and auto execution engines (`kalshi_trader.py`, `auto_executor/`)
- Frontend Source:
  - `static/saas_dashboard.html`: Core SaaS web app
  - `static/login.html`: Authentication view
  - `static/trades.html`: Mobile trade ledger
  - `static/admin_mobile.html`: Mobile admin console
  - `static/js/`: Client JavaScript (`app.js`, `admin_users.js`, `dashboard.js`)
  - `static/css/`: Stylesheets (`dashboard.css`, `app.css`)
  - `static/assets/`: Icons, logos, and splash screens
- Testing:
  - `tests/`: Pytest test suite and test fixtures

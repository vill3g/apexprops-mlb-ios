# ShadowTrader AI — Test Infrastructure & E2E Test Suite Architecture

## Overview
This document specifies the end-to-end (E2E) testing infrastructure, methodology, execution commands, and architectural hierarchy for the ShadowTrader AI codebase. The testing suite provides opaque-box verification of system stability, error resilience, frontend integrity, and trading execution pipelines based on acceptance criteria defined in `ORIGINAL_REQUEST.md` and `PROJECT.md`.

---

## 1. Test Architecture & Environment

### Test Framework
- **Core Runner**: Pytest 9.1.1 (running under Python 3.12.10 x64)
- **API Client**: `fastapi.testclient.TestClient` / `starlette.testclient.TestClient`
- **Asynchronous Engine**: `anyio` (SelectorEventLoop on Windows)
- **Parser & AST Engines**: Python `html.parser`, `json`, `sqlite3`, `re`

### Isolation & Non-Destructive Operation
- **Database Sandboxing**: Governed by `tests/conftest.py`, setting `USERS_DB_PATH` and `USERS_DATA_DIR` into an isolated temporary directory (`tempfile.mkdtemp(prefix="kalshi_tests_")`). Zero writes occur against production `users.db` or root user profiles.
- **Seeded Test Entities**: Two baseline users (`seed_trader_one`, `seed_trader_two`) are automatically initialized for multi-user session verification.
- **Deterministic Mocking**: External broker network hops (`BASE_URL = https://external-api.kalshi.com`) and tunnel daemons (`ngrok`) are safely intercepted and simulated using standard `unittest.mock` fixtures, ensuring test stability without external network dependencies.

---

## 2. Test Hierarchy (Tiers 1–4)

The test suite in `tests/test_audit_e2e_suite.py` is organized into four distinct architectural tiers:

### Tier 1: Feature Coverage (>=5 Tests per Core Feature)
1. **Backend Health & Watchdog Supervisor (5 tests)**
   - `test_backend_health_check_endpoint`: Verifies `GET /api/health` returns status `ok`, version, and service identification.
   - `test_backend_engine_root_endpoint`: Validates `GET /api/engine/` lists supported asset engines (`BTC`, `ETH`, `GOLD`, `NDQ`).
   - `test_server_watchdog_single_instance_mutex`: Confirms the Windows named mutex `KalshiAITraderWatchdogLock` prevents conflicting duplicate supervisors.
   - `test_server_watchdog_command_construction`: Asserts `run_server()` selects valid python interpreters and enforces the `--no-browser` headless argument.
   - `test_security_middleware_rate_limiting`: Verifies that `SecurityMiddleware` blocks runaway bursts exceeding 5000 req/min with HTTP 429 without crashing.

2. **Kalshi 429 Rate Limit Handling (5 tests)**
   - `test_kalshi_trader_market_result_429_graceful`: Asserts `get_market_result` intercepts HTTP 429 and returns a structured error dictionary rather than throwing an unhandled exception.
   - `test_kalshi_trader_market_quote_429_graceful`: Verifies `get_market_quote` intercepts HTTP 429 and returns `{ "success": False, "error": ... }`.
   - `test_kalshi_trader_balance_429_handled`: Validates `get_balance` safely catches HTTP 429 rate limit responses, returning zeroed balance without raising an exception.
   - `test_kalshi_trader_active_15m_market_fallback_on_429`: Verifies `get_active_15m_market` falls back cleanly to synthetic or returns None under 429 pressure.
   - `test_kalshi_trader_close_position_429_handled`: Confirms `close_position` handles 429 rejection payloads gracefully without process crash.

3. **Static Asset Zero 404s (5 tests)**
   - `test_static_css_assets_exist`: Asserts all `<link rel="stylesheet">` tags in `saas_dashboard.html`, `login.html`, and `trades.html` resolve to existing files on disk.
   - `test_static_js_assets_exist`: Asserts all client scripts referenced via `<script src="...">` exist on disk.
   - `test_static_images_and_icons_exist`: Validates all local `<img src>` and `<link rel="icon">` references in `saas_dashboard.html` exist on disk.
   - `test_manifest_icons_exist`: Verifies all icons declared in `static/manifest.json` exist on disk and possess non-zero byte size.
   - `test_fastapi_serves_static_assets`: Verifies FastAPI's `/static` mount returns 200 OK for critical CSS and JS assets via `TestClient`.

4. **HTML Structural Integrity (5 tests)**
   - `test_saas_dashboard_html_syntax`: Parses `saas_dashboard.html` with Python's standard `HTMLParser` to ensure no fatal hierarchy defects.
   - `test_saas_dashboard_critical_drawers_closed`: Ensures `#settingsDrawer` and modals in `saas_dashboard.html` have balanced closing `</div>` tags.
   - `test_saas_dashboard_unique_element_ids`: Validates that primary control and container element IDs in `saas_dashboard.html` are unique.
   - `test_login_and_trades_html_structural_tags`: Ensures `login.html` and `trades.html` possess well-formed `<head>`, `<body>`, and meta configurations.
   - `test_viewport_meta_fit_cover`: Asserts that `viewport-fit=cover` is present across all core pages for iOS safe-area compliance.

5. **Auto Trader Logic & Toggle Synchronization (5 tests)**
   - `test_autotrader_config_get`: Confirms `GET /api/engine/btc/trade/config` delivers valid `enabled`, `mode`, and threshold states.
   - `test_autotrader_toggle_post`: Verifies `POST /api/engine/btc/trade/toggle?enabled=true` enables the execution engine.
   - `test_autotrader_toggle_sync_state`: Verifies toggling execution immediately synchronizes with the configuration state returned by the server.
   - `test_autotrader_mode_switch`: Verifies trading mode switching (`PAPER` vs `LIVE`) updates executor configuration correctly.
   - `test_autotrader_status_reflection`: Validates `GET /api/engine/btc/trade/status` delivers comprehensive telemetry (balance, pnl, open trades).

---

### Tier 2: Boundary & Corner Cases (7 Tests)
- `test_boundary_empty_config_payload`: POST `/api/engine/btc/trade/config` with empty `{}` handles gracefully without unhandled 500 server crashes.
- `test_boundary_kalshi_network_timeout`: `KalshiTrader.get_market_result` handles `requests.exceptions.Timeout` returning `{ "success": False, "error": ... }`.
- `test_boundary_invalid_asset_rejected`: Querying an unsupported asset like `UNKNOWN_XYZ` is cleanly rejected with HTTP 404.
- `test_boundary_missing_auth_token_rejected`: Endpoints requiring token validation reject requests missing valid credentials with HTTP 401.
- `test_boundary_malformed_toggle_query`: `POST /api/engine/btc/trade/toggle?enabled=notabool` returns HTTP 422 Unprocessable Entity.
- `test_boundary_order_invalid_count_rejected`: `KalshiTrader.place_order` with zero or negative contract counts is cleanly rejected.
- `test_boundary_order_invalid_side_rejected`: `KalshiTrader.place_order` with invalid side (e.g. `side="MAYBE"`) is rejected with an error message.

---

### Tier 3: Cross-Feature Interactions (5 Tests)
- `test_cross_autotrader_toggle_db_user_sync`: Toggling auto-trader through the API updates both executor memory and user records in SQLite.
- `test_cross_rate_limit_during_trading_loop`: Simulated 429 during `AutoExecutor` background evaluation does not bubble unhandled exceptions into the worker.
- `test_cross_frontend_asset_url_routing`: HTML relative paths (`./assets/...`, `/static/assets/...`) are verified to map to real files accessible via FastAPI.
- `test_cross_multi_asset_executor_isolation`: Independent executor instances for BTC vs ETH maintain isolated states and configurations.
- `test_cross_risk_limit_suppression`: Exceeding max daily risk limits properly suppresses trade submission in `AutoExecutor`.

---

### Tier 4: Real-World Scenarios (5 Tests)
- `test_real_world_lifespan_startup_and_shutdown`: FastAPI `lifespan` context manager completes startup hooks (socket exception handler, self-healing reconciler) and shutdown cleanly.
- `test_real_world_simulated_15m_candle_evaluation`: Simulated 15m candle evaluation with synthetic OHLCV data executes pattern detection and conviction calculation.
- `test_real_world_simulated_repeated_429_resilience`: Repeated 429 rate limit responses simulate backoff and recovery without leaking exceptions or crashing the runtime process.
- `test_real_world_static_directory_scan`: Complete recursive scan of `static/` directory verifying all files exist, are readable, have valid non-zero size, and have no corrupted headers.
- `test_real_world_paper_trading_roundtrip`: Paper order placement followed by status check reflects trade execution and state transitions without external broker access.

---

## 3. Test Runner Commands

### Standard Execution
To run the full E2E test suite:
```powershell
& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/test_audit_e2e_suite.py
```

### Verbose Execution with Timing Breakdown
```powershell
& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -v --durations=10 tests/test_audit_e2e_suite.py
```

### Focused Tier Execution
```powershell
# Tier 1 only
& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -v -k "tier1" tests/test_audit_e2e_suite.py

# Tier 2 only
& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -v -k "tier2" tests/test_audit_e2e_suite.py

# Tier 3 only
& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -v -k "tier3" tests/test_audit_e2e_suite.py

# Tier 4 only
& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -v -k "tier4" tests/test_audit_e2e_suite.py
```

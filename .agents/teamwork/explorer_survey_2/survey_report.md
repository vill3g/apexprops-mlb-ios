# Explorer Survey Report: Backend Database Schemas, Settings Storage, & Universe Persistence

**Survey Agent**: `explorer_survey_2`  
**Working Directory**: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_2`  
**Date**: October 7, 2026  
**Target Project**: `kalshi-ai-trader` / ShadowTrader AI  
**Focus**: Backend Database Schemas, User Settings Storage, Authentication, API Endpoints, and `trading_universe` ("BOTH") Persistence

---

## 1. Executive Summary

This investigation analyzed the backend architecture of the ShadowTrader AI / Kalshi AI Trader platform regarding the `trading_universe` configuration, specifically evaluating how the value `"BOTH"` (and related values `"FINANCIAL"`, `"SPORTS"`, `"ALL"`) is stored, validated, updated via API, and consumed by the execution engines.

### Key Takeaways
1. **Database Schema & Enums**: The SQLite schema in `backend/data/users.db` natively stores `trading_universe` as a `TEXT DEFAULT 'FINANCIAL'` column on the `users` table. The backend codebase defines `VALID_TRADING_UNIVERSES = {"FINANCIAL", "SPORTS", "BOTH", "ALL"}` (`backend/database/models.py:410`).
2. **API Acceptance**: `POST /api/auth/user/config` and its Pydantic model `UserConfigRequest` properly accept and validate `"BOTH"` (and `"ALL"`), normalizing inputs to uppercase.
3. **Execution Engine Multi-Tenant Support**: Both the financial auto-executor (`backend/btc/auto_executor/saas_broadcaster.py`) and the sports auto-executor (`backend/sports_bridge/executor.py`) correctly include users whose `trading_universe` is set to `"BOTH"` or `"ALL"`, allowing simultaneous multi-universe execution.
4. **CRITICAL DEFECTS IDENTIFIED — Silent Overwrites of "BOTH"**:
   - **Defect A (`backend/routes/engine.py:706`)**: Toggling auto-trading on any sports asset (`POST /api/engine/{asset}/trade/toggle?enabled=...`) hardcodes `update_user_trading_universe(user_id, "SPORTS")`. Any user configured with `"BOTH"` who toggles auto-trading while viewing sports has their universe immediately and irreversibly overwritten to `"SPORTS"`. *(Empirically verified in test execution)*.
   - **Defect B (`backend/routes/engine.py:916`)**: Updating user parameters via `POST /api/engine/{asset}/trade/config` (for non-sports assets like BTC) calls `update_user_config` without passing `trading_universe`. Because `update_user_config` defaults `trading_universe: str = "FINANCIAL"` (`backend/database/models.py:808`), any financial settings save quietly resets the user's universe to `"FINANCIAL"`. *(Empirically verified in test execution)*.
   - **Defect C (`static/saas_dashboard.html:3882`)**: When switching UI tabs, `window.selectUniverse(universe)` executes `window.lastDashboardStats.trading_universe = universe;`, corrupting the in-memory settings state with the current viewing tab (`"FINANCIAL"` or `"SPORTS"`), erasing `"BOTH"` from subsequent client payloads.
   - **Defect D (`static/saas_dashboard.html:6990-7100`)**: The UI currently uses a single shared drawer (`#settingsPanel`) that conditionally hides/shows elements via CSS classes rather than maintaining two strictly separated, independently toggleable drawers as required by prompt R1.

---

## 2. Backend Database Schemas & Storage Architecture

### 2.1 Primary User Database (`backend/data/users.db`)
The application relies on SQLite with WAL mode (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`), accessed through `get_db_connection()` in `backend/database/models.py`.

- **Database File Location**:  
  `backend/data/users.db` (configurable via environment variable `USERS_DB_PATH`).
- **Data Directory**:  
  `backend/data` (configurable via `USERS_DATA_DIR`).
- **Cross-Process Concurrency**:  
  Managed via `CrossProcessLock` (`backend/data/locks/user_{user_id}.lock`) protecting per-user disk writes between FastAPI workers and background background workers (`worker.py`).

### 2.2 Table Schemas
```sql
-- Main Users Table (backend/database/models.py:245-260 + REQUIRED_COLUMNS)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    kalshi_key_id TEXT,
    kalshi_priv_key_encrypted TEXT,
    is_active BOOLEAN DEFAULT 1,
    role TEXT DEFAULT 'user',
    trading_mode TEXT DEFAULT 'PAPER',
    paper_balance REAL DEFAULT 500.0,
    ai_enabled BOOLEAN DEFAULT 1,
    trade_size_pct REAL DEFAULT 20.0,
    stop_loss_pct REAL DEFAULT 50.0,
    one_click_trade BOOLEAN DEFAULT 0,
    -- Columns dynamically added by init_db() via REQUIRED_COLUMNS:
    trade_size_dollars REAL DEFAULT 5.0,
    paper_trade_size_dollars REAL DEFAULT 50.0,
    target_asset TEXT DEFAULT 'BTC',
    trading_style TEXT DEFAULT 'AUTO',
    signal_source TEXT DEFAULT 'RL_DQN',
    take_profit_pct REAL DEFAULT 50.0,
    take_profit_enabled BOOLEAN DEFAULT 1,
    max_daily_trades INTEGER DEFAULT 10,
    max_daily_risk REAL DEFAULT 50.0,
    trailing_stop_enabled BOOLEAN DEFAULT 0,
    trailing_stop_activation_pct REAL DEFAULT 35.0,
    trailing_stop_distance_pct REAL DEFAULT 6.0,
    second_entry_enabled BOOLEAN DEFAULT 0,
    second_entry_max_ask REAL DEFAULT 0.75,
    reentry_after_stop_loss BOOLEAN DEFAULT 0,
    model_choice TEXT DEFAULT 'RL_DQN',
    train_window INTEGER DEFAULT 4000,
    regularization_c REAL DEFAULT 0.5,
    class_weight TEXT DEFAULT 'balanced',
    xgb_estimators INTEGER DEFAULT 300,
    xgb_max_depth INTEGER DEFAULT 5,
    xgb_learning_rate REAL DEFAULT 0.1,
    ignore_pass_technical BOOLEAN DEFAULT 0,
    one_shot_ai BOOLEAN DEFAULT 0,
    profile_pic TEXT DEFAULT NULL,
    notify_trade_results BOOLEAN DEFAULT 1,
    notify_market_trends BOOLEAN DEFAULT 1,
    last_seen_update TEXT DEFAULT NULL,
    dismissed_update TEXT DEFAULT NULL,
    edge_gate_enabled BOOLEAN DEFAULT 1,
    min_edge_cents REAL DEFAULT 0.0,
    use_kelly_criterion BOOLEAN DEFAULT 0,
    atr_risk_enabled BOOLEAN DEFAULT 0,
    -- Universe & Sports Settings
    trading_universe TEXT DEFAULT 'FINANCIAL',
    min_sports_confidence REAL DEFAULT 70.0,
    min_sports_edge REAL DEFAULT 3.0,
    sports_max_wager REAL DEFAULT 10.0,
    sports_trade_size_dollars REAL DEFAULT 10.0,
    sports_include_live BOOLEAN DEFAULT 0,
    sports_active_leagues TEXT DEFAULT 'NFL,MLB,NPB/KBO,SOC,UFC,TEN,NHL',
    sports_min_price REAL DEFAULT 0.20,
    sports_max_price REAL DEFAULT 0.80,
    sports_max_daily_trades INTEGER DEFAULT 10,
    sports_max_open_trades INTEGER DEFAULT 5,
    sports_max_daily_risk REAL DEFAULT 100.0,
    sports_tp_enabled BOOLEAN DEFAULT 0,
    sports_tp_pct REAL DEFAULT 35.0,
    sports_use_kelly BOOLEAN DEFAULT 0,
    sports_market_types TEXT DEFAULT 'GAME,SPREAD,TOTAL,PROP',
    sports_active_props TEXT DEFAULT 'ANYTIME_TD,PASSING_YDS,RUSHING_YDS,RECEIVING_YDS,HOME_RUNS,STRIKEOUTS,HITS_RUNS_RBIS,TOTAL_BASES,OTHER'
);

-- User Profiles Table (backend/database/models.py:227-233)
CREATE TABLE IF NOT EXISTS user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    profile_name TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    created_at TEXT
);
```

### 2.3 Auto-Migration Mechanism
In `backend/database/models.py:264-273`:
```python
cursor.execute("PRAGMA table_info(users)")
existing_cols = {row[1] for row in cursor.fetchall()}
for col_name, col_def in REQUIRED_COLUMNS.items():
    if col_name not in existing_cols:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        conn.commit()
```
`trading_universe` is guaranteed to exist on table initialization.

---

## 3. Authentication & Authorization Architecture

### 3.1 Token Transmission
1. **HTTP Authorization Header**: `Authorization: Bearer <JWT>`
2. **Cookie Fallback**: `saas_token=<JWT>` (HttpOnly, Secure, SameSite=none, 90-day expiry).

### 3.2 Key Auth Dependencies
1. **`get_current_user` (`backend/auth/routes.py:151-176`)**:
   - Decodes JWT via `decode_jwt_token(token)` (`backend/auth/security.py`).
   - Resolves payload `user_id` against `get_user_by_id(user_id)`.
   - Checks `is_active == 1` (raises HTTP 403 if deactivated).
   - Injects full `dict(row)` into route dependencies.
2. **`require_auth` (`backend/auth/dependencies.py:69-100`)**:
   - Validates JWT from header or cookie.
   - If no JWT, checks `is_owner_request(request)` (validates `X-API-Token` against master secret or checks local/LAN IP address).
   - **Ngrok / Proxy Hardening**: `_is_local_client` rejects requests containing `X-Forwarded-For` header, preventing external attackers from spoofing localhost.

---

## 4. API Endpoints & Request/Response Models

| Endpoint | Method | Auth Dependency | Purpose | `trading_universe` Handling |
| :--- | :---: | :---: | :--- | :--- |
| `/api/auth/user/config` | `POST` | `get_current_user` | Save all user config parameters | Accepted via `UserConfigRequest.trading_universe`. Persists via `update_user_trading_universe` & `update_user_config`. |
| `/api/auth/dashboard_stats` | `GET` | `get_current_user` | Primary dashboard state poll | Returns `"trading_universe": current_user.get("trading_universe", "FINANCIAL")` with ETag caching. |
| `/api/auth/me` | `GET` | `get_current_user` | Basic user profile | **Does NOT return** `trading_universe`. Returns username, role, mode, paper_balance, keys. |
| `/api/auth/trade/config` | `POST` | `get_current_user` | Change mode (PAPER/LIVE) | Does not touch `trading_universe`. |
| `/api/engine/{asset}/trade/toggle` | `POST` | `require_auth` | Toggle auto-trading execution | **DANGEROUS**: When `asset` is a sports asset, line 706 executes `update_user_trading_universe(user_id, "SPORTS")`. |
| `/api/engine/{asset}/trade/config` | `POST` | `require_auth` | Asset-specific trading config | **DANGEROUS**: Non-sports calls omit `trading_universe` in `update_user_config`, resetting it to `"FINANCIAL"`. |
| `/api/engine/{asset}/trade/status` | `GET` | `require_auth` | Asset-specific engine status | Returns `"universe": "SPORTS"` for sports assets as metadata. |
| `/api/auth/admin/users` | `GET` | `require_admin_auth` | List all users for admin panel | **Does NOT include** `trading_universe` in returned user objects. |
| `/api/admin/users/{user_id}` | `PUT` | `require_admin_auth` | Admin updates user settings | **Lacks** `trading_universe` field in `AdminConfigPayload`. |

### 4.1 Schema Validation: `UserConfigRequest`
Defined in `backend/auth/routes.py:40-103`:
```python
class UserConfigRequest(BaseModel):
    ...
    ai_enabled: Optional[bool] = None
    trading_universe: Optional[str] = None

    @field_validator("trading_universe")
    @classmethod
    def validate_trading_universe(cls, v):
        if v is not None:
            norm = str(v).strip().upper()
            if norm not in {"FINANCIAL", "SPORTS", "BOTH", "ALL"}:
                raise ValueError(f"Invalid trading_universe '{v}'. Allowed: 'FINANCIAL', 'SPORTS', 'BOTH', 'ALL'")
            return norm
        return v
    ...
```

---

## 5. Execution Engines & Multi-Universe Processing

When `trading_universe` is set to `"BOTH"`:

### 5.1 Financial Engine (`backend/btc/auto_executor/saas_broadcaster.py`)
- **Broadcast Filter (line 177)**:
  ```python
  if (user.get('trading_universe') or 'FINANCIAL').upper() not in ('FINANCIAL', 'BOTH', 'ALL'): return
  ```
- **Interval Active Users Filter (line 414)**:
  ```python
  active_users = [
      u for u in users
      if u.get('ai_enabled', 1)
      and (u.get('trading_universe') or 'FINANCIAL').upper() in ('FINANCIAL', 'BOTH', 'ALL')
      and self.asset.upper() in [x.strip() for x in u.get('target_asset', 'BTC').upper().split(',')]
  ]
  ```
- **Result**: Users with `"BOTH"` or `"ALL"` are successfully included in financial trades.

### 5.2 Sports Engine (`backend/sports_bridge/executor.py`)
- **Active Sports Users Filter (line 350)**:
  ```python
  sports_users = [
      u for u in users
      if (u.get("trading_universe") or "").upper() in ("SPORTS", "BOTH", "ALL") and bool(u.get("ai_enabled", 0))
  ]
  ```
- **Result**: Users with `"BOTH"` or `"ALL"` are successfully included in sports predictions execution.

### 5.3 Simultanous Execution Compatibility
The backend architecture is already designed for simultaneous multi-universe trading when `trading_universe == "BOTH"`. The failure of "BOTH" to persist is entirely caused by unintended mutation points in the API and client state.

---

## 6. Critical Bugs Causing Loss of "BOTH" Setting

### Bug 1: `backend/routes/engine.py:706` Forced Overwrite on Toggle
In `backend/routes/engine.py:695-710`:
```python
@router.post("/api/engine/{asset}/trade/toggle", dependencies=[Depends(require_auth)])
def api_btc_trade_toggle(asset: str, enabled: bool = Query(...), request: Request = None):
    try:
        user_id = _resolve_user_id(None, request)
        if _is_sports_asset(asset):
            if user_id:
                update_user_ai_enabled(user_id, enabled)
                from backend.database.models import update_user_trading_universe
                try:
                    update_user_trading_universe(user_id, "SPORTS")  # <--- BUG HERE
                except Exception:
                    pass
            return JSONResponse({"status": "ok", "success": True, "enabled": enabled, "asset": asset.upper(), "universe": "SPORTS"})
```
- **Impact**: Toggling auto-trading in the sports tab overwrites `trading_universe` to `"SPORTS"`.
- **Empirical Test**:
  - Initial DB value: `"BOTH"`
  - Action: `c.post('/api/engine/sports/trade/toggle?enabled=true')`
  - Resulting DB value: `"SPORTS"` (loss of `"BOTH"` confirmed).

### Bug 2: `backend/routes/engine.py:916` Default Reset via `update_user_config`
In `backend/routes/engine.py:878-948`:
```python
@router.post("/api/engine/{asset}/trade/config", dependencies=[Depends(require_auth)])
async def api_btc_trade_config_post(asset: str, request: Request, background_tasks: BackgroundTasks):
    ...
    if user_id:
        update_user_config(
            user_id=user_id,
            trade_size_dollars=float(data.get("trade_size_dollars", 5.0)),
            ...
            # trading_universe IS NOT PASSED!
        )
```
In `backend/database/models.py:808`:
```python
def update_user_config(
    ...,
    trading_universe: str = "FINANCIAL",  # <--- DEFAULT OVERWRITE
    ...
):
    ...
    c.execute('''
        UPDATE users 
        SET ..., trading_universe = ?, ...
        WHERE id = ?
    ''', (..., trading_universe, ..., user_id))
```
- **Impact**: Any save of financial settings via `/api/engine/{asset}/trade/config` overwrites `trading_universe` with `"FINANCIAL"`.
- **Empirical Test**:
  - Initial DB value: `"BOTH"`
  - Action: `c.post('/api/engine/btc/trade/config', json={'trade_size_dollars': 15.0})`
  - Resulting DB value: `"FINANCIAL"` (loss of `"BOTH"` confirmed).

### Bug 3: `static/saas_dashboard.html:3882` In-Memory Mutation
In `window.selectUniverse` (`static/saas_dashboard.html:3882`):
```javascript
window.selectUniverse = function(universe) {
    window.currentUniverse = universe;
    ...
    if (window.lastDashboardStats) {
        window.lastDashboardStats.trading_universe = universe;  // <--- OVERWRITING SETTING WITH TAB VIEW
        ...
    }
}
```
- **Impact**: When the user clicks between tabs (`FINANCIAL` vs `SPORTS`), `lastDashboardStats.trading_universe` is mutated to the clicked tab name. When `saveUserConfig()` runs, it reads `window.lastDashboardStats.trading_universe` as a fallback, sending `"FINANCIAL"` or `"SPORTS"` to the backend instead of `"BOTH"`.

### Bug 4: Shared Drawer Architecture in `static/saas_dashboard.html`
- **Location**: `static/saas_dashboard.html:6990-7500`
- **Current State**: There is only one drawer container `#settingsPanel` with a button pill ("Show settings for: Financials Menu / Sports Menu"). Selecting a tab dynamically applies `.hidden` to classes `.finance-only-setting` and `.sports-only-setting`.
- **Requirement R1 Violation**: The prompt requires two distinct, independently toggleable UI components: one strictly for Financials and one strictly for Sports.

---

## 7. Concrete Recommendations for Implementation

### Recommendation 1: Fix `backend/routes/engine.py:706` (Toggle Route)
Remove `update_user_trading_universe(user_id, "SPORTS")` from `api_btc_trade_toggle`. The toggle endpoint must strictly toggle `ai_enabled` without altering the user's trading universe:
```python
# In backend/routes/engine.py:695-710
if _is_sports_asset(asset):
    if user_id:
        update_user_ai_enabled(user_id, enabled)
    return JSONResponse({"status": "ok", "success": True, "enabled": enabled, "asset": asset.upper(), "universe": "SPORTS"})
```

### Recommendation 2: Fix `update_user_config` Default & Query (`backend/database/models.py`)
1. Change `trading_universe: Optional[str] = None` in `update_user_config`'s signature.
2. In the SQL statement, use `COALESCE(?, trading_universe, 'FINANCIAL')` so omitting `trading_universe` preserves the existing database value:
```python
# In backend/database/models.py:808
def update_user_config(
    ...,
    trading_universe: Optional[str] = None,
    ...
):
    ...
    # In SQL:
    trading_universe = COALESCE(?, trading_universe, 'FINANCIAL'),
```
3. Update `backend/routes/engine.py:916` to pass `trading_universe=None` (or the existing universe from DB), ensuring it never overwrites the database value.

### Recommendation 3: Remove `window.lastDashboardStats.trading_universe = universe` in `static/saas_dashboard.html`
In `selectUniverse(universe)`:
Delete line 3882:
```javascript
// REMOVE: window.lastDashboardStats.trading_universe = universe;
```
The active UI view tab (`window.currentUniverse`) must remain strictly decoupled from the auto-trading execution setting (`window.configuredTradingUniverse` and `window.lastDashboardStats.trading_universe`).

### Recommendation 4: Decouple Frontend Settings into Dual Drawers (R1)
1. In `static/saas_dashboard.html`, split `#settingsPanel` into two distinct drawers:
   - `#financialSettingsDrawer`: Contains Financial parameters (BTC/crypto trade size, trailing stop, take profit, ATR risk, Kelly criterion, RL model hyperparameters).
   - `#sportsSettingsDrawer`: Contains Sports parameters (sports trade size, confidence slider, edge slider, active leagues, props, odds filters).
2. In both drawers, include the auto-trading universe selector (`CRYPTO`, `SPORTS`, `BOTH`) synced with `window.configuredTradingUniverse`.
3. Provide dedicated trigger functions (`openFinancialSettings()`, `openSportsSettings()`).

### Recommendation 5: Add `trading_universe` to Admin Route (`backend/auth/admin_routes.py`)
Add `trading_universe: Optional[Literal["FINANCIAL", "SPORTS", "BOTH", "ALL"]] = None` to `AdminConfigPayload` and expose `trading_universe` in `list_all_users`.

---

## 8. Verification Plan & Test Commands

To verify backend persistence and multi-universe execution:

1. **Verify Schema & Model Validation**:
   ```powershell
   python -m pytest tests/test_r2_r5_multi_universe_and_timestamps.py -k "trading_universe or validation" -v
   ```
2. **Verify Simultaneous Execution for BOTH**:
   ```powershell
   python -m pytest tests/test_r2_r5_multi_universe_and_timestamps.py -k "test_user_with_both_matches_simultaneously" -v
   ```
3. **Verify API Persistence via Settings Route**:
   ```powershell
   python -m pytest tests/test_r2_r5_multi_universe_and_timestamps.py -k "test_api_user_config_both_and_all_persistence" -v
   ```
4. **Verify No Overwrites on Sports Toggle**:
   Execute programmatic test ensuring `POST /api/engine/sports/trade/toggle?enabled=true` preserves `"BOTH"`.
5. **Verify No Overwrites on Financial Config Post**:
   Execute programmatic test ensuring `POST /api/engine/btc/trade/config` preserves `"BOTH"`.

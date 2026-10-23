# Handoff Report: Backend Schemas, Settings APIs, & Universe Persistence

**Agent**: `explorer_survey_2`  
**Working Directory**: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_2`  
**Handoff Type**: Hard (Task Complete)  
**Deliverable Artifact**: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_2\survey_report.md`  

---

## 1. Observation

1. **Database Schema & Enums**:
   - `backend/database/models.py:157`: `REQUIRED_COLUMNS` contains `"trading_universe": "TEXT DEFAULT 'FINANCIAL'"`.
   - `backend/database/models.py:410`: `VALID_TRADING_UNIVERSES = {"FINANCIAL", "SPORTS", "BOTH", "ALL"}`.
   - `backend/database/models.py:412-421`:
     ```python
     def update_user_trading_universe(user_id: int, universe: str):
         norm = str(universe).strip().upper()
         if norm not in VALID_TRADING_UNIVERSES:
             raise ValueError(f"Invalid trading_universe '{universe}'. Allowed: {sorted(list(VALID_TRADING_UNIVERSES))}")
         conn = get_db_connection()
         try:
             c = conn.cursor()
             c.execute("UPDATE users SET trading_universe = ? WHERE id = ?", (norm, user_id))
             conn.commit()
         finally:
             conn.close()
     ```
   - `backend/database/models.py:808, 848`: `update_user_config` defines `trading_universe: str = "FINANCIAL"`, and executes `UPDATE users SET ..., trading_universe = ?, ... WHERE id = ?`.

2. **API Request & Response Endpoints**:
   - `backend/auth/routes.py:67-77`: `UserConfigRequest` includes:
     ```python
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
     ```
   - `backend/auth/routes.py:1053`: In `GET /api/auth/dashboard_stats`:
     `"trading_universe": current_user.get("trading_universe", "FINANCIAL")`.
   - `backend/auth/routes.py:1631-1634`: In `POST /api/auth/user/config`:
     ```python
     if req.trading_universe is not None:
         try:
             from backend.database.models import update_user_trading_universe
             update_user_trading_universe(current_user["id"], req.trading_universe)
     ```
   - `backend/auth/routes.py:236-246`: `GET /api/auth/me` does not return `trading_universe`.
   - `backend/auth/admin_routes.py:70-106`: `AdminConfigPayload` does not include `trading_universe`.
   - `backend/auth/admin_routes.py:180-229`: `GET /api/auth/admin/users` does not return `trading_universe`.

3. **Multi-Tenant Execution Engines**:
   - `backend/btc/auto_executor/saas_broadcaster.py:177`:
     `if (user.get('trading_universe') or 'FINANCIAL').upper() not in ('FINANCIAL', 'BOTH', 'ALL'): return`
   - `backend/btc/auto_executor/saas_broadcaster.py:414`:
     `and (u.get('trading_universe') or 'FINANCIAL').upper() in ('FINANCIAL', 'BOTH', 'ALL')`
   - `backend/sports_bridge/executor.py:350`:
     `if (u.get("trading_universe") or "").upper() in ("SPORTS", "BOTH", "ALL") and bool(u.get("ai_enabled", 0))`

4. **Bug: Forced Overwrite on Sports Toggle**:
   - `backend/routes/engine.py:701-709`:
     ```python
     if _is_sports_asset(asset):
         if user_id:
             update_user_ai_enabled(user_id, enabled)
             from backend.database.models import update_user_trading_universe
             try:
                 update_user_trading_universe(user_id, "SPORTS")
             except Exception:
                 pass
         return JSONResponse({"status": "ok", "success": True, "enabled": enabled, "asset": asset.upper(), "universe": "SPORTS"})
     ```
   - Test execution:
     Command:
     `python -c "from backend.database.models import get_user_by_id, update_user_trading_universe; from starlette.testclient import TestClient; from backend.main import app; from backend.auth.security import create_jwt_token; c = TestClient(app); token = create_jwt_token(7, 'Vill3.G'); update_user_trading_universe(7, 'BOTH'); print('Before toggle:', get_user_by_id(7)['trading_universe']); res = c.post('/api/engine/sports/trade/toggle?enabled=true', headers={'Authorization': f'Bearer {token}'}); print('After toggle:', get_user_by_id(7)['trading_universe'])"`
     Output:
     `Before toggle: BOTH`  
     `After toggle: SPORTS`

5. **Bug: Default Reset on Financial Engine Config Post**:
   - `backend/routes/engine.py:916-947`: `api_btc_trade_config_post` calls `update_user_config` without passing `trading_universe`.
   - Test execution:
     Command:
     `python -c "from backend.database.models import get_user_by_id, update_user_trading_universe; from starlette.testclient import TestClient; from backend.main import app; from backend.auth.security import create_jwt_token; c = TestClient(app); token = create_jwt_token(7, 'Vill3.G'); update_user_trading_universe(7, 'BOTH'); print('Before config:', get_user_by_id(7)['trading_universe']); res = c.post('/api/engine/btc/trade/config', json={'trade_size_dollars': 15.0}, headers={'Authorization': f'Bearer {token}'}); print('After config:', get_user_by_id(7)['trading_universe'])"`
     Output:
     `Before config: BOTH`  
     `After config: FINANCIAL`

6. **Bug: Client-Side In-Memory Overwrite on Tab Switch**:
   - `static/saas_dashboard.html:3882`:
     `window.selectUniverse = function(universe) { ... if (window.lastDashboardStats) { window.lastDashboardStats.trading_universe = universe; ... } }`

---

## 2. Logic Chain

1. Observations (1, 2, 3) establish that the database schema, Pydantic schemas, and execution engines (`saas_broadcaster.py` and `sports_bridge/executor.py`) were architected to support simultaneous multi-universe execution when `trading_universe == "BOTH"` or `"ALL"`.
2. Observation (4) shows that whenever a user toggles auto-trading in the sports tab or via mobile UI, `POST /api/engine/sports/trade/toggle` calls `update_user_trading_universe(user_id, "SPORTS")`. This directly overwrites `"BOTH"` with `"SPORTS"`.
3. Observation (5) shows that whenever `/api/engine/{asset}/trade/config` is called for financial assets (e.g., modifying risk parameters), `update_user_config` is called without the `trading_universe` parameter. Because `update_user_config` has `trading_universe: str = "FINANCIAL"`, it overwrites `"BOTH"` with `"FINANCIAL"`.
4. Observation (6) shows that when a user switches tabs in the frontend (`selectUniverse('SPORTS')` or `selectUniverse('FINANCIAL')`), the client-side state `window.lastDashboardStats.trading_universe` is mutated to match the active viewing tab, erasing `"BOTH"` from client-side memory.
5. Therefore, the failure of `"BOTH"` to persist across page reloads and toggles is not a database engine limitation, but rather the cumulative result of these three specific regression points overwriting the stored value.

---

## 3. Caveats

- The standalone `backend/sports/sports_executor.py` does not check `trading_universe` or `ai_enabled` at all, but background trading is driven by `SportsBridgeExecutor` in `backend/worker.py` (which correctly checks `trading_universe in ('SPORTS', 'BOTH', 'ALL')`).
- Frontend visual layout redesign (splitting the single drawer into dual drawers) was investigated and scoped, but per explorer read-only constraints, actual HTML edits must be executed by implementation agents.

---

## 4. Conclusion

The database schema, validation logic, and trading engines already support `"BOTH"`. To guarantee permanent persistence of `"BOTH"`:
1. Remove `update_user_trading_universe(user_id, "SPORTS")` from `backend/routes/engine.py:706`.
2. Change `update_user_config` in `backend/database/models.py` to use `trading_universe: Optional[str] = None` and `COALESCE(?, trading_universe, 'FINANCIAL')`, ensuring omitted arguments do not reset the setting.
3. Remove `window.lastDashboardStats.trading_universe = universe;` from `selectUniverse` in `static/saas_dashboard.html:3882`.
4. Decouple `#settingsPanel` in `static/saas_dashboard.html` into two dedicated drawer components (`#financialSettingsDrawer` and `#sportsSettingsDrawer`) as required by prompt R1.

---

## 5. Verification Method

1. **Unit & API Persistence Test**:
   ```powershell
   python -m pytest tests/test_r2_r5_multi_universe_and_timestamps.py -k "test_api_user_config_both_and_all_persistence or test_user_with_both_matches_simultaneously" -v
   ```
2. **Sports Toggle Non-Regression Test**:
   ```powershell
   python -c "from backend.database.models import get_user_by_id, update_user_trading_universe; from starlette.testclient import TestClient; from backend.main import app; from backend.auth.security import create_jwt_token; c = TestClient(app); token = create_jwt_token(7, 'Vill3.G'); update_user_trading_universe(7, 'BOTH'); res = c.post('/api/engine/sports/trade/toggle?enabled=true', headers={'Authorization': f'Bearer {token}'}); assert get_user_by_id(7)['trading_universe'] == 'BOTH'; print('PASS: Toggle preserved BOTH')"
   ```
3. **Engine Config Non-Regression Test**:
   ```powershell
   python -c "from backend.database.models import get_user_by_id, update_user_trading_universe; from starlette.testclient import TestClient; from backend.main import app; from backend.auth.security import create_jwt_token; c = TestClient(app); token = create_jwt_token(7, 'Vill3.G'); update_user_trading_universe(7, 'BOTH'); res = c.post('/api/engine/btc/trade/config', json={'trade_size_dollars': 15.0}, headers={'Authorization': f'Bearer {token}'}); assert get_user_by_id(7)['trading_universe'] == 'BOTH'; print('PASS: Config preserved BOTH')"
   ```

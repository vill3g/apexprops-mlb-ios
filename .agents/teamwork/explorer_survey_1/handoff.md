# Handoff Report — Explorer Survey 1 (Backend Stability & Architecture)

## 1. Observation

1. **Live Crash in `watchdog_error.log`**:
   `watchdog_error.log:19323` and `watchdog_error.log:19340`:
   ```
   2026-10-01 09:15:24,220 [INFO] [Server] 2026-10-01 09:15:24,220 - backend.btc.auto_executor.saas_broadcaster - ERROR - [SaaS Multitenant] Error executing for user Vill3.G: 'list' object has no attribute 'get'
   ```
   Inspection of `backend/btc/auto_executor/saas_broadcaster.py:748-750, 777` revealed:
   ```python
   trend = str(forecast.get("raw_features", {}).get("trend_1h", "UP")).upper()
   ema_9 = float(forecast.get("raw_features", {}).get("ema_9", 0))
   ema_21 = float(forecast.get("raw_features", {}).get("ema_21", 0))
   ```
   And in `backend/btc/analyzer/contract_eval.py:53, 72`:
   ```python
   "raw_features": [],
   ```
   When `forecast.get("raw_features", {})` executes, it returns the empty list `[]`, and `[].get(...)` raises `AttributeError: 'list' object has no attribute 'get'`.
   Query on `backend/data/users.db` confirmed `Vill3.G` and `Prep109` have `auto_force_trade = 1`, which triggers this code path.

2. **Kalshi Rate Limiting & Defective `@retry`**:
   In `backend/btc/kalshi_trader.py:442-461` and `473-498`:
   ```python
   @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=1, max=5),
          retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout, requests.exceptions.ConnectionError)))
   def get_market_result(self, ticker: str) -> Dict[str, Any]:
       resp = self.session.get(f"{BASE_URL}{path}", ...)
       if resp.status_code != 200:
           return {"success": False, "result": "", "error": f"HTTP {resp.status_code}: {resp.text}"}
   ```
   When Kalshi returns HTTP 429, no exception is raised; the function returns `{"success": False, ...}` on attempt 1. `@retry` is never invoked.
   Furthermore, `get_balance()` (`kalshi_trader.py:129`), `get_positions()` (`kalshi_trader.py:740`), and `place_order()` (`kalshi_trader.py:997`) have zero 429 retry handling.

3. **Runaway Settlement Polling (429 Storm Generator)**:
   In `backend/saas_settler.py:734-750`, for any open trade where the market is no longer active, `kalshi_trader.get_market_result(ticker)` is called without backoff.
   If Kalshi has not posted the official resolution yet or returns 429, `res.get("result")` is empty, leading to `continue`.
   `backend/worker.py:61-90` calls `settle_saas_trades()` every 1.0s.
   This hammers Kalshi with ~60 to 180+ requests/min per unsettled contract, triggering Kalshi 429 rate limit bans.

4. **Launcher Crash on Missing `.venv`**:
   `launch_desktop.py:81, 96`:
   ```python
   venv_python = os.path.join(APP_DIR, ".venv", "Scripts", "python.exe")
   cmd = [venv_python, "-m", "uvicorn", ...]
   worker_cmd = [venv_python, "backend/worker.py"]
   ```
   In `C:\Users\Vill3\Desktop\ShadowTraderAi`, `.venv` does not exist. `launch_desktop.py` crashes with `FileNotFoundError`.

5. **Legacy Process & Named Mutex Conflict**:
   `server_watchdog.py:120` creates a named mutex `"KalshiAITraderWatchdogLock"`.
   Running processes check (`Get-CimInstance Win32_Process`) showed active legacy processes running from `C:\Users\Vill3\Desktop\kalshi-ai-trader`:
   - PID 55200 / 99016: `server_watchdog.py`
   - PID 18160 / 85160: `uvicorn backend.main:app --port 8058`
   - PID 22424: `ngrok.exe`
   Because the mutex is held, starting `server_watchdog.py` in `ShadowTraderAi` exits immediately without running.

6. **Log Flooding**:
   `watchdog_error.log` grew to **48,655,782 bytes (~48.6 MB)** due to unthrottled worker logging every 1 second piped line-by-line through `server_watchdog.py:147-150`.

7. **Test Suite Status**:
   Ran `pytest tests` using `C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests`:
   - 180 tests collected
   - 138 PASSED
   - 38 FAILED (breakdowns: 2 due to refactored `add_all_indicators` missing from `backend.btc.auto_executor.__init__.py`, admin 401s in auth tests, UI DOM ID renames in frontend tests, mock PEM parsing in crypto tests)
   - 4 SKIPPED

---

## 2. Logic Chain

1. **From Observation 1**: In `contract_eval.py:53, 72`, `"raw_features"` is typed as a `list` (`[]`). In `saas_broadcaster.py:748` and `executor.py:1285`, the code does `forecast.get("raw_features", {}).get(...)`. In Python, `dict.get(key, default)` returns the value stored at `key` if present. Because `[]` is truthy or present, it returns `[]`. Calling `.get()` on a list raises `AttributeError: 'list' object has no attribute 'get'`. This crashes user trade execution for any user with `auto_force_trade = 1`.
2. **From Observation 2 & 3**: Kalshi enforces strict REST API rate limits (typically 10-20 req/s or 100/min). The worker loop runs every 1 second and polls `get_market_result` for all pending unsettled contracts. When Kalshi returns 429, `get_market_result()` does not raise an exception, preventing tenacity `@retry` from running, and returning an empty result. The settler loop immediately retries on the next 1-second tick, causing a persistent 429 lockout storm that starves balance checks and halts live order execution.
3. **From Observation 4 & 5**: The watchdog supervisor relies on `launch_desktop.py`, which hardcodes `.venv\Scripts\python.exe`. Without `.venv`, the process crashes. Furthermore, until `stop_server.bat` is executed to terminate the active legacy `kalshi-ai-trader` processes, `server_watchdog.py` cannot acquire the named mutex.

---

## 3. Caveats

- Live trading order execution against real Kalshi funds was not executed (dry-run exploration only).
- We surveyed the Python backend and tests; frontend DOM audits will be handled by the frontend specialist agent.
- `watchdog_error.log` was analyzed via tail/head and pattern extraction rather than reading the entire 48 MB file into context.

---

## 4. Conclusion

The ShadowTrader AI backend architecture is well-structured and modular, but possesses three high-severity stability vulnerabilities:
1. **Kalshi 429 rate limit vulnerability**: Defective `@retry` in `kalshi_trader.py` combined with unthrottled 1-second settlement polling in `saas_settler.py` triggers cascading 429 lockouts.
2. **Crash on force trade**: `'list' object has no attribute 'get'` in `saas_broadcaster.py:748, 777` crashes order processing for users with `auto_force_trade = 1`.
3. **Launcher environment fragility**: Hardcoded `.venv` path in `launch_desktop.py` prevents startup in environments without a local `.venv`.

Fixing these three root causes will restore backend stability, eliminate 429 storms, and allow stable autonomous execution.

---

## 5. Verification Method

1. **Verify Python Test Runner**:
   ```powershell
   & "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/test_audit_findings.py -v
   ```
   Expected: 12 passed.

2. **Verify `'list' object has no attribute 'get'` fix**:
   Unit test `forecast = {"raw_features": []}` in `saas_broadcaster.py` with `auto_force_trade=1` to confirm safe dictionary fallback without `AttributeError`.

3. **Verify Kalshi 429 retry behavior**:
   Mock Kalshi response with status 429 on `get_market_result()` and `get_market_quote()` to confirm the method catches 429, triggers exponential backoff, and retries.

4. **Verify Settlement Polling Backoff**:
   Confirm in `backend/saas_settler.py` that unresolved markets back off to checking at most once every 30-60 seconds rather than every 1 second.

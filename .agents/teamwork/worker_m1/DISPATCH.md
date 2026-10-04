# Worker M1 Dispatch: Backend Stability & Kalshi 429 Resilience

You are worker_m1.
Role: teamwork_preview_worker
Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m1
Project root: C:\Users\Vill3\Desktop\ShadowTraderAi
Mandatory reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: C:\Users\Vill3\Desktop\ShadowTraderAi\PROJECT.md
Survey findings: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_1\survey_report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Exclusively Owned Files:
- backend/btc/kalshi_trader.py
- backend/saas_settler.py
- backend/btc/auto_executor/saas_broadcaster.py
- launch_desktop.py
- backend/worker.py
- server_watchdog.py
- backend/forex/auto_executor.py
- backend/btc/auto_executor/__init__.py

Tasks:
1. In `backend/btc/kalshi_trader.py`: Fix defective `@retry` on `get_market_result` and `get_market_quote`. Ensure HTTP 429 status codes trigger retry with exponential backoff (e.g. check status code or raise for status inside retry loop). Wrap `get_balance()`, `get_positions()`, and `place_order()` with 429 backoff protection.
2. In `backend/saas_settler.py`: Add per-ticker settlement retry backoff/negative caching (e.g. at most once every 30-60 seconds for unresolved contracts) to eliminate runaway 1-second 429 polling storms.
3. In `backend/btc/auto_executor/saas_broadcaster.py:748, 777` (and `executor.py` if needed): Fix `'list' object has no attribute 'get'` crash by validating that `raw_features` is a dictionary before calling `.get()`.
4. In `launch_desktop.py:81`: Add check `if os.path.exists(venv_python)` and fallback to `sys.executable` to prevent `FileNotFoundError` when `.venv` does not exist.
5. In `server_watchdog.py`: Ensure watchdog handles existing mutex cleanly or handles graceful restarts. In `backend/worker.py`: Throttle repetitive routine loop logs to prevent multi-megabyte log flooding.
6. In `backend/forex/auto_executor.py`: Add guard if `current_balance <= 0` to prevent endless negative lot calculation warnings.
7. In `backend/btc/auto_executor/__init__.py`: Re-export `from backend.btc.indicators import add_all_indicators`.

Verification:
- Run the test suite: `& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests`
- Document test outcomes and verified commands in your handoff report at `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m1\handoff.md`.
- Send a completion message via send_message to orchestrator `64adbb8f-6e60-424a-a1e3-00b93642f92a`.

## 2026-10-02T17:40:43Z
You are worker_m1.
Role: teamwork_preview_worker
Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m1
Project root: C:\Users\Vill3\Desktop\ShadowTraderAi
Mandatory reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: C:\Users\Vill3\Desktop\ShadowTraderAi\PROJECT.md
Survey findings: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_1\survey_report.md
Dispatch reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m1\DISPATCH.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Exclusively Owned Files:
- backend/btc/kalshi_trader.py
- backend/saas_settler.py
- backend/btc/auto_executor/saas_broadcaster.py
- launch_desktop.py
- backend/worker.py
- server_watchdog.py
- backend/forex/auto_executor.py
- backend/btc/auto_executor/__init__.py

Tasks:
1. In `backend/btc/kalshi_trader.py`: Fix defective `@retry` on `get_market_result` and `get_market_quote`. Ensure HTTP 429 status codes trigger retry with exponential backoff (e.g. check status code or raise for status inside retry loop). Wrap `get_balance()`, `get_positions()`, and `place_order()` with 429 backoff protection.
2. In `backend/saas_settler.py`: Add per-ticker settlement retry backoff/negative caching (e.g. at most once every 30-60 seconds for unresolved contracts) to eliminate runaway 1-second 429 polling storms.
3. In `backend/btc/auto_executor/saas_broadcaster.py:748, 777` (and `executor.py` if needed): Fix `'list' object has no attribute 'get'` crash by validating that `raw_features` is a dictionary before calling `.get()`.
4. In `launch_desktop.py:81`: Add check `if os.path.exists(venv_python)` and fallback to `sys.executable` to prevent `FileNotFoundError` when `.venv` does not exist.
5. In `server_watchdog.py`: Ensure watchdog handles existing mutex cleanly or handles graceful restarts. In `backend/worker.py`: Throttle repetitive routine loop logs to prevent multi-megabyte log flooding.
6. In `backend/forex/auto_executor.py`: Add guard if `current_balance <= 0` to prevent endless negative lot calculation warnings.
7. In `backend/btc/auto_executor/__init__.py`: Re-export `from backend.btc.indicators import add_all_indicators`.

Verification:
- Run the test suite: `& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests`
- Document test outcomes and verified commands in your handoff report at `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m1\handoff.md`.
- Send a completion message via send_message to orchestrator `64adbb8f-6e60-424a-a1e3-00b93642f92a`.


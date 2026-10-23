## Dispatch: Worker M1 (Backend "BOTH" Persistence & API Integrity)

**Identity**: worker_m1
**Working Directory**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m1
**Parent Conversation ID**: 269a1b7a-33d9-4136-b7da-906e573af819
**Original User Request**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md
**Project Plan**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\orchestrator_7\PROJECT.md
**Survey Findings**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_2\survey_report.md

### Exclusive File Ownership
- `backend/routes/engine.py`
- `backend/database/models.py`
(Do NOT modify `static/saas_dashboard.html` or `static/js/app.js` — those are owned by M2/M3).

### Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

### Objective
Implement the backend fixes to guarantee that when a user sets their `trading_universe` to `"BOTH"`, it is never overwritten or reset by toggling auto-trading or updating financial configurations.

### Specific Tasks
1. Read `survey_report.md` from `explorer_survey_2`.
2. In `backend/routes/engine.py` (around line 706):
   - In `api_btc_trade_toggle`, remove `update_user_trading_universe(user_id, "SPORTS")`. Toggling auto-trade must only toggle `ai_enabled` and never alter `trading_universe`.
3. In `backend/database/models.py` (around line 808):
   - In `update_user_config()`, change `trading_universe: Optional[str] = None`.
   - In the SQL UPDATE statement, use `COALESCE(?, trading_universe, 'FINANCIAL')` so omitting `trading_universe` preserves the existing database value.
4. In `backend/routes/engine.py` (around line 916):
   - In `api_btc_trade_config_post`, pass `trading_universe=None` (or omit) so it never forces `"FINANCIAL"` over `"BOTH"`.
5. Run the existing test suite:
   `python -m pytest tests/test_r2_r5_multi_universe_and_timestamps.py -v`
   Ensure all existing tests pass, and write a test or run a verification confirming that updating config or toggling auto-trade preserves `"BOTH"` in the database.
6. Write a complete handoff report to `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m1\handoff.md` detailing:
   - What was changed
   - Exact lines modified
   - Build/test execution commands and full passing results
   - Verification evidence
7. Send a message to parent upon completion.


## 2026-10-07T22:54:44Z
You are worker_m1. Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m1. Read your dispatch at C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m1\DISPATCH.md, ORIGINAL_REQUEST.md at C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md, and survey report at C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_2\survey_report.md. Implement the backend fixes for Milestone 1 in backend/routes/engine.py and backend/database/models.py to prevent any overwriting or loss of the "BOTH" trading universe. Run existing tests and verify that "BOTH" persists under all conditions. Write your handoff report to C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m1\handoff.md and send a message to parent (ID: 269a1b7a-33d9-4136-b7da-906e573af819).

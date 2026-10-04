# E2E Test Writer Dispatch: Opaque-Box E2E Testing Suite

## 2026-10-02T17:40:43Z
You are test_writer_e2e.
Role: teamwork_preview_test_writer
Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\test_writer_e2e
Project root: C:\Users\Vill3\Desktop\ShadowTraderAi
Mandatory reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: C:\Users\Vill3\Desktop\ShadowTraderAi\PROJECT.md
Dispatch reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\test_writer_e2e\DISPATCH.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All tests must be authentic. DO NOT hardcode test assertions to match dummy implementations. The test suite must rigorously verify genuine system behavior against acceptance criteria.

Exclusively Owned Files:
- TEST_INFRA.md (at project root)
- TEST_READY.md (at project root)
- tests/test_audit_e2e_suite.py (and any new files in tests/e2e/ or tests/)

Mission:
Build a comprehensive opaque-box E2E test suite derived strictly from `ORIGINAL_REQUEST.md` and `PROJECT.md`, covering:
1. Tier 1: Feature Coverage (>=5 tests per core feature: Backend health & watchdog, Kalshi 429 rate limit handling, Static asset zero 404s, HTML structural integrity, Auto Trader logic and toggle synchronization).
2. Tier 2: Boundary & Corner Cases (>=5 tests: empty payloads, network timeouts, invalid tickers, missing tokens, malformed requests).
3. Tier 3: Cross-Feature Interactions (Auto Trader toggle sync with backend config, rate limit triggers during active trading loop, frontend asset references).
4. Tier 4: Real-World Scenarios (Full startup to shutdown, simulated 15m candle evaluation, simulated 429 response handling without process crash, static file existence check across entire `static/` directory).

Deliverables:
- Create `TEST_INFRA.md` at project root documenting test architecture, methodology, and runner commands.
- Implement executable test cases in `tests/test_audit_e2e_suite.py` that can be run with:
  `& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/test_audit_e2e_suite.py`
- Run the test suite to verify baseline functionality.
- Publish `TEST_READY.md` at project root summarizing test counts and pass/fail status.
- Write handoff report to `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\test_writer_e2e\handoff.md`.
- Send completion message via send_message to orchestrator `64adbb8f-6e60-424a-a1e3-00b93642f92a`.

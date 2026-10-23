## Dispatch: E2E Test Writer (Requirement-Driven Test Suite)

**Identity**: test_writer_e2e
**Working Directory**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\test_writer_e2e
**Parent Conversation ID**: 269a1b7a-33d9-4136-b7da-906e573af819
**Original User Request**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md
**Project Plan**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\orchestrator_7\PROJECT.md

### Exclusive File Ownership
- `tests/test_saas_dashboard_decoupling_e2e.py`
- `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\TEST_INFRA.md`
- `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\TEST_READY.md`
(Do NOT modify application code in `static/` or `backend/`).

### Mandatory Integrity Warning
DO NOT CHEAT. All tests must be genuine, requirement-driven, opaque-box tests that verify actual application behavior. DO NOT create trivial always-passing tests or mock out the core logic being verified.

### Objective
Design and implement a comprehensive opaque-box E2E test suite in `tests/test_saas_dashboard_decoupling_e2e.py` that validates all requirements of the SaaS dashboard decoupling refactor (R1, R2, R3).

### Test Suite Structure (4 Tiers)
1. **Tier 1: Feature Coverage (>=5 tests per feature)**:
   - Dedicated Financial settings drawer structure (DOM checks, presence of crypto/forex options only)
   - Dedicated Sports settings drawer structure (DOM checks, presence of sports/props options only)
   - Universe "BOTH" backend persistence via API (`POST /api/auth/user/config`)
   - Universe "BOTH" fetched correctly via `GET /api/auth/dashboard_stats`
   - Preservation of "BOTH" during auto-trade toggles and asset config updates
   - Proper input/toggle saving to database
2. **Tier 2: Boundary & Corner Cases (>=5 tests per feature)**:
   - Invalid universe strings (proper rejection)
   - Empty sports props / leagues arrays
   - Extreme trade sizes or slider values
   - Missing fields in update payloads
   - Repeated/rapid toggles
3. **Tier 3: Cross-Feature Combinations (Pairwise Coverage)**:
   - Toggling auto-trader while viewing sports when universe is "BOTH"
   - Saving financial settings while universe is "BOTH"
   - Switching between Financial and Sports drawer triggers
   - Interactions between Paper/Live mode switch and Auto execution toggle across drawers
4. **Tier 4: Real-World Scenarios (End-to-End Workflows)**:
   - Scenario 1: New user configures "BOTH" auto-trading, updates sports trade size, updates BTC stop loss, reloads dashboard, verifies all settings intact.
   - Scenario 2: Active trader toggles auto-trading off and on across sports and financial tabs, verifying execution states and "BOTH" persistence.
   - Scenario 3: HTML DOM integrity check verifying no unclosed tags, proper nesting of `#financialSettingsDrawer` and `#sportsSettingsDrawer`, and absence of obsolete shared drawer classes.

### Deliverables
1. Test file: `tests/test_saas_dashboard_decoupling_e2e.py`
2. Run pytest on the new test file to verify test definitions load cleanly.
3. Write `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\TEST_INFRA.md` and `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\TEST_READY.md`.
4. Write handoff report to `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\test_writer_e2e\handoff.md`.
5. Send a message to parent upon completion.


## 2026-10-07T22:54:45Z
You are test_writer_e2e. Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\test_writer_e2e. Read your dispatch at C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\test_writer_e2e\DISPATCH.md and ORIGINAL_REQUEST.md at C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md. Design and create the comprehensive 4-tier E2E test suite in tests/test_saas_dashboard_decoupling_e2e.py covering all requirements (R1 dedicated drawers, R2 "BOTH" persistence, R3 frontend optimization and input saving). Create TEST_INFRA.md and TEST_READY.md in C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\. Write your handoff report to C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\test_writer_e2e\handoff.md and send a message to parent (ID: 269a1b7a-33d9-4136-b7da-906e573af819).

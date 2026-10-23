## Dispatch: Worker M2 (Dedicated Dual Settings Menus in saas_dashboard.html)

**Identity**: worker_m2
**Working Directory**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m2
**Parent Conversation ID**: 269a1b7a-33d9-4136-b7da-906e573af819
**Original User Request**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md
**Project Plan**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\orchestrator_7\PROJECT.md
**Survey 1 Report**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_1\survey_report.md
**Survey 3 Report**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_3\survey_report.md
**E2E Test Report**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\TEST_READY.md

### Exclusive File Ownership
- `static/saas_dashboard.html`
- `static/css/mobile-polish.css`
- `backend/database/models.py` (for `sports_trade_size_dollars` COALESCE fix)

### Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

### Objective
Completely decouple the SaaS dashboard UI settings drawer into two dedicated, independently toggleable UI components: `#financialSettingsDrawer` and `#sportsSettingsDrawer` in `static/saas_dashboard.html`. Fix the unclosed `<div>` in Market Types, fix the `sportsActivePropsStr` ReferenceError in `saveUserConfig()`, synchronize the "BOTH" universe selector across both drawers, and ensure `sports_trade_size_dollars` is preserved on config updates.

### Specific Tasks
1. Read `survey_report.md` from `explorer_survey_1` and `TEST_READY.md`.
2. In `static/saas_dashboard.html`:
   - Replace the single shared drawer `#settingsDrawer` with two distinct drawers:
     - `#financialSettingsDrawer`: Dedicated to Financials (crypto/forex assets, trading style, signal source, stop loss, take profit, trailing stop, dynamic ATR, multi-entry DCA, ML hyperparameters, wallet transfer, Kalshi API keys).
     - `#sportsSettingsDrawer`: Dedicated to Sports (7 sports leagues, 5 market types, 9 player props, sports trade size, Kelly toggle, price corridor min/max, mid-game TP, risk caps, AI confidence slider, AI edge slider).
   - In `#sportsSettingsDrawer`, fix the unclosed `<div>` in the Market Types section (line ~7502) so the DOM tree parses with 100% tag balance.
   - Remove obsolete universe pills ("Show settings for: Financials Menu / Sports Menu").
   - Include the 3-button Auto-Trading Universe segmented selector (`[ Crypto ] [ Sports ] [ Both ]`) in BOTH drawers, with clear labels and badges.
3. In `static/saas_dashboard.html` scripts:
   - Update `openSettings(universe)`: Open `#sportsSettingsDrawer` if `universe === 'SPORTS'` or `window.currentUniverse === 'SPORTS'`; otherwise open `#financialSettingsDrawer`.
   - Update `closeSettings()`: Close whichever drawer is active with smooth transition.
   - Update `initSettingsSwipeToClose()`: Bind touch/swipe to both `#financialSettingsPanel` and `#sportsSettingsPanel`.
   - In `saveUserConfig()`: Fix Bug B by declaring and collecting `sportsActivePropsStr` from `.sports-prop-toggle` checkboxes before constructing the payload.
   - In `setAutoTradingUniverse(univ, skipSave = false)`: Synchronize active button states and badges across BOTH drawers.
4. In `backend/database/models.py`:
   - In `update_user_config()`, ensure `sports_trade_size_dollars` uses `COALESCE(?, sports_trade_size_dollars, sports_max_wager)` so saving financial config never wipes previously saved sports trade sizes.
5. In `static/css/mobile-polish.css`:
   - Extend selectors for `#settingsDrawer` to `#financialSettingsDrawer`, `#sportsSettingsDrawer`, `#financialSettingsPanel`, `#sportsSettingsPanel`.
6. Run the test suite:
   `python -m pytest tests/test_saas_dashboard_decoupling_e2e.py -v`
   Verify that all Tier 1 drawer structure tests (F1.1, F1.2), F1.6 saving tests, and Tier 4 Scenario 1 & 3 tests now PASS!
7. Write your handoff report to `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m2\handoff.md` and send a message to parent upon completion.

## 2026-10-07T23:20:12Z
**Context**: Milestone 2 HTML decoupling status check
**Content**: Checking on your progress on Milestone 2 tasks. Please provide a brief status update on which task you are actively working on.
**Action**: Reply with brief status update.


## Dispatch: Worker M3 (UI/UX Optimization & Controls Verification)

**Identity**: worker_m3
**Working Directory**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m3
**Parent Conversation ID**: 269a1b7a-33d9-4136-b7da-906e573af819
**Original User Request**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md
**Project Plan**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\orchestrator_7\PROJECT.md
**Survey 3 Report**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_3\survey_report.md
**E2E Test Report**: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\TEST_READY.md

### Exclusive File Ownership
- `static/js/app.js`
- `static/app.js`
- `static/saas_dashboard.html`

### Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

### Objective
Optimize frontend rendering in `static/js/app.js` and `static/saas_dashboard.html` to eliminate UI stuttering, flickering, and lag during tab switches between Financial and Sports, and verify all buttons, toggles, sliders, and inputs across both universes work without interference.

### Specific Tasks
1. Read `survey_report.md` from `explorer_survey_3` regarding tab switching performance and flickering (Section 2.2).
2. Optimize Tab Switching in `saas_dashboard.html` & `app.js`:
   - When switching to Financial (`selectUniverse('FINANCIAL')`), do NOT trigger blocking `showChartLoader()` or blank HUD elements (`$--,---`, `--%`) if cached candle/market data exists. Keep existing chart visible and immediately resize/fit content via `requestAnimationFrame`.
   - When switching to Sports (`selectUniverse('SPORTS')`), render cached sports events immediately if `window.__sportsEventsCache` exists rather than blanking the container with an animated pulse loader.
   - Synchronize `static/app.js` with `static/js/app.js`.
3. Verify all buttons, toggles, sliders, and inputs across both `#financialSettingsDrawer` and `#sportsSettingsDrawer`:
   - Verify Paper/Live mode toggle works and syncs across both drawers.
   - Verify Auto-trading execution switch works and syncs across both drawers.
   - Verify Auto-trading universe segmented buttons (`CRYPTO`, `SPORTS`, `BOTH`) correctly update active classes and badges across both drawers.
   - Verify financial asset toggles (BTC, ETH, etc.), stop loss %, take profit %, trailing stop, dynamic ATR, DCA, trade size ($).
   - Verify sports leagues (7), market types (5), props (9), sports trade size ($), Kelly toggle, price corridor, mid-game TP, risk caps, confidence and edge sliders.
   - Ensure saving any of these triggers `saveUserConfig()` without throwing JavaScript errors or ReferenceErrors.
4. Run all test suites:
   `python -m pytest tests/test_saas_dashboard_decoupling_e2e.py -v`
   `python -m pytest tests/test_frontend_contracts.py -v`
   `python -m pytest tests/test_m1_both_universe_persistence.py -v`
   Ensure 100% of tests pass cleanly.
5. Write handoff report to `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m3\handoff.md` and send a message to parent upon completion.


## 2026-10-07T23:23:24Z
[Message] timestamp=2026-10-07T23:23:24Z sender=269a1b7a-33d9-4136-b7da-906e573af819 priority=MESSAGE_PRIORITY_HIGH content=You are worker_m3. Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m3. Read your dispatch at C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m3\DISPATCH.md, ORIGINAL_REQUEST.md at C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md, survey report at C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\explorer_survey_3\survey_report.md, and TEST_READY.md at C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\TEST_READY.md. Implement Milestone 3 optimizations in static/js/app.js, static/app.js, and static/saas_dashboard.html to eliminate tab switching stutter/flickering, optimize chart resize and cache-first rendering, and verify all buttons, toggles, and inputs across both drawers. Run tests with pytest tests/test_saas_dashboard_decoupling_e2e.py -v. Write your handoff report to C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_m3\handoff.md and send a message to parent (ID: 269a1b7a-33d9-4136-b7da-906e573af819).

# BRIEFING — 2026-10-09T14:48:00Z

## Mission
Investigate frontend display, tab selection, and event filtering in saas_dashboard.html, app.js, and related static assets to identify why non-NHL sports fail to display prediction cards and show "No active AI picks".

## 🔒 My Identity
- Archetype: explorer
- Roles: investigator, synthesizer
- Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3
- Original parent: 79a13c8c-bb16-4406-ac17-c75d551d55ff
- Milestone: Survey & Investigation (Survey 3: Frontend display & tab filtering)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Investigate frontend display, tab selection, and event filtering in saas_dashboard.html, app.js, and static assets
- Write findings to report.md and handoff.md in working directory
- Send message to orchestrator via send_message when done

## Current Parent
- Conversation ID: 79a13c8c-bb16-4406-ac17-c75d551d55ff
- Updated: 2026-10-09T14:48:00Z

## Investigation State
- **Explored paths**:
  - `static/saas_dashboard.html` (tab definitions lines 783-789, `isSportMatch` lines 4061-4083, `renderSportsEvents` lines 4088-4341, `loadSportsEvents` lines 4693-4738, `querySportsAI` lines 4590-4680, `filterSportsEvents` lines 4033-4059, pull-to-refresh lines 5713-5717)
  - `static/js/sports-settings-panels.js` (`sportOf` lines 232-243, `marketOf` lines 244-270, `sportsEventAllowed` lines 271-285)
  - `static/js/sports-trade-details.js` (`loadEvent` line 71, `statusOf`, `loadPrediction`)
  - `static/js/sports-open-bar.js`
  - `static/app.js` and `static/js/app.js` (verified they contain crypto trading logic; sports logic is embedded in `saas_dashboard.html`)
  - `backend/routes/engine.py` (lines 2709-3400 `/api/engine/sports/events` route, line 3378 `is_today` filter, line 2948 date difference > 1 day)
  - `tests/test_sports_dashboard.py` (executed pytest; failed on empty events for NPB/KBO, NFL, TEN)
- **Key findings**:
  1. *Premature "No active AI picks" flash*: Line 4119 of `saas_dashboard.html` only shows loading spinner if the *entire cache* across all sports is empty (`!__sportsEventsCache || __sportsEventsCache.length === 0`). When NHL events are cached, clicking non-NHL tabs immediately renders "No active AI picks" while network requests are still loading.
  2. *`isSportMatch` missing ticker checks & aliases*: Lines 4061-4083 only check `evt.sport`, `evt.league`, `evt.series_ticker`. Kalshi event tickers like `KXATPMATCH-...`, `KXWTAMATCH-...`, `KXNFL...`, `KXMLB...`, `KXEPL...`, `KXUFC...` are not matched against `evt.event_ticker` or `evt.ticker`. Does not normalize `BASEBALL` -> `MLB`, `FOOTBALL` -> `NFL`, `HOCKEY` -> `NHL`, `ATP`/`WTA` -> `TEN`, `EPL`/`MLS`/`UEFA`/`WC` -> `SOC`.
  3. *Settings gate blocking explicit tab clicks*: Line 4099 calls `window.sportsEventAllowed(e)` unconditionally. If user's auto-trading settings turned off tennis/other sports, explicitly browsing that tab suppresses all cards.
  4. *Pull-to-refresh toggles off current sport*: Line 5715 calls `filterSportsEvents(window.sportsFilter || 'NFL')`, which toggles the active sport back to `'ALL'`.
  5. *Backend `is_today` pruning*: Backend line 3378 `kalshi_events = [e for e in kalshi_events if e.get("is_today")]` deletes all upcoming games (tomorrow or weekend), causing backend to return `[]` for non-NHL sports.
  6. *Tennis 24h date discrepancy*: Backend line 2948 rejects tennis picks if date difference > 1 day (`diff > 1`), discarding ApexProps tournament picks.
- **Unexplored areas**: None. Complete trace accomplished across UI, static assets, and backend contract.

## Key Decisions Made
- Fully documented all 6 tasks with exact line numbers, code snippets, root causes, and recommended patches.

## Artifact Index
- C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\DISPATCH.md — Task instructions
- C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\BRIEFING.md — Agent briefing and state
- C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\progress.md — Progress and liveness tracker
- C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\report.md — Comprehensive survey report
- C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\handoff.md — 5-component handoff report

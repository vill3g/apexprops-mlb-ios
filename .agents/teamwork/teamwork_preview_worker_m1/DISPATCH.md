## 2026-10-09T14:52:35Z

Read C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md first.
You are teamwork_preview_worker_m1.
Your working directory is: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_worker_m1

MANDATORY INTEGRITY WARNING:
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A teamwork_preview_auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.

Context & Scope:
You are assigned Milestone 1: Multi-Sport Backend Matching & Frontend Display Implementation (R1 & R2).
Project plan: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\orchestrator_8\PROJECT.md
Examine the 3 survey reports for exact file paths, line numbers, and proposed code changes:
- C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_1\report.md
- C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_2\report.md
- C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\report.md

Exclusive Write Ownership:
- backend/routes/engine.py
- backend/sports_bridge/prediction_client.py
- backend/sports_bridge/executor.py
- static/saas_dashboard.html
- tests/test_sports_dashboard.py (if adding/updating tests)

Detailed Implementation Tasks:
1. Backend Changes (backend/routes/engine.py):
   - Line ~3378: Remove or relax `kalshi_events = [e for e in kalshi_events if e.get("is_today")]` so all upcoming open events for all sports (NFL, MLB, TEN, SOC, UFC, NPB/KBO) are preserved while past events remain filtered by line 2821.
   - Lines ~3265 & ~3325: Attach `"ai_prediction": best_pick if has_valid_pick else None` (and for props `matched_pick if has_ai_prediction else None`) to each returned event object at the top level and inside metadata.
   - Lines ~2946-2950: Extend Tennis date matching tolerance to 48 hours (`diff <= 2` days; i.e. `if diff > 2: date_match = False`). Also adjust Tennis stale threshold in line 3153.
   - Line ~2885: Add fallback player extraction in Tennis matching. If `p_away_raw` or `p_home_raw` is missing, parse `meta.get("matchup")` or `p.get("opponent")` by splitting on `\s+(?:vs\.?|at|@)\s+`.
   - Add team aliases to `_SPORT_TEAM_MAP` for `SOC`, `NPB`, `KBO`.
   - Add `KXBUNDESLIGA` and `KXLALIGA` to `_SPORTS_SERIES_MAP["SOC"]`.
   - Line ~2854: Refine title prefix regex so team matchups before `: Spread` or `: Total Points` are preserved.
   - Line ~3232: Normalize sport comparison in player prop matching loop using `_normalize_sport`.

2. Backend Changes (backend/sports_bridge/prediction_client.py & executor.py):
   - In `prediction_client.py` around line 546: extend Tennis date window in `predict_for_event()` from 1 day to 2 days (`if abs((ed - pd).days) > 2: continue`).
   - In `executor.py` line 126: ensure `_generate_kalshi_market` returns a 4-tuple: `return None, 0.0, None, {}`.

3. Frontend Changes (static/saas_dashboard.html):
   - Line ~4119: Fix loading pulse check so it displays loading indicator while `window.__sportsLoading` is true, preventing premature flash of "No active AI picks".
   - Lines ~4061-4083: Expand `isSportMatch()` to check `event_ticker`/`ticker` prefixes (`KXATP*`, `KXWTA*`, `KXNFL*`, `KXMLB*`, `KXNHL*`, `KXEPL*`, `KXUFC*`, `KXNPB*`, `KXKBO*`) and sport aliases (`ATP`, `WTA`, `SOC`, `EPL`, `MLS`, `BASEBALL`, `FOOTBALL`, `HOCKEY`).
   - Line ~4099: Decouple background settings gate so `sportsEventAllowed(e)` only filters when viewing `'ALL'` sports, allowing users to explicitly browse specific sports tabs.
   - Line ~5715: Fix pull-to-refresh calling `loadSportsEvents(window.sportsFilter)` instead of `filterSportsEvents`.
   - Update `SPORT_ICONS` map.

4. Build and Test Verification:
   - Run `pytest tests/test_sports_dashboard.py` and ensure all tests pass.
   - Run verification script to query `/api/engine/sports/events?sport=TEN` and verify `ai_prediction` object is present on returned events.
   - Verify that all sports (`NHL`, `MLB`, `NFL`, `TEN`, `SOC`, `UFC`, `NPB/KBO`) return events.
   - Document all verification commands and outputs in your report.

5. Deliverables:
   - Write full report to `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_worker_m1\report.md`
   - Write handoff report to `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_worker_m1\handoff.md`
   - Send completion message to parent orchestrator.

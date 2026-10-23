# BRIEFING — 2026-10-09T14:48:00Z

## Mission
Investigate Tennis date-matching discrepancy (>24h vs 48h) between Kalshi events and ApexProps AI predictions, multi-sport name normalization, and schema matching / silent drop issues.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_2
- Original parent: 79a13c8c-bb16-4406-ac17-c75d551d55ff
- Milestone: survey_2

## 🔒 Key Constraints
- Read-only investigation — do NOT implement / modify source code directly
- Focus on sports_bridge/ and backend/ matching logic, date window, name normalization, and schema/exception handling
- Provide exact file paths, line numbers, and recommended code changes
- Output report.md and handoff.md

## Current Parent
- Conversation ID: 79a13c8c-bb16-4406-ac17-c75d551d55ff
- Updated: 2026-10-09T14:48:00Z

## Investigation State
- **Explored paths**: `backend/routes/engine.py`, `backend/sports_bridge/prediction_client.py`, `backend/sports_bridge/executor.py`, `backend/routes/sports.py`, `tests/test_sports_dashboard.py`, `static/saas_dashboard.html`
- **Key findings**:
  1. `backend/routes/engine.py:3378` filters `kalshi_events = [e for e in kalshi_events if e.get("is_today")]`, which wipes out all upcoming events for NFL, Tennis, MLB, UFC, NPB/KBO on days when games aren't scheduled today.
  2. Tennis date difference capped at `diff > 1` (24h) in `engine.py:2948` and `prediction_client.py:546`; must be extended to `diff > 2` (48h) due to international tournament timezones and Kalshi ticker creation conventions.
  3. Predictions from `bot-bridge` lacked `player_a`/`player_b` keys in `metadata`, storing them in `matchup` (e.g., `"Carlos Alcaraz vs Juan Manuel Cerundolo"`). Because `engine.py:2885` didn't parse `matchup`, `p_away` and `p_home` were empty strings, bypassing the Tennis matching block entirely.
  4. Missing `"ai_prediction"` key in `/api/engine/sports/events` responses.
  5. Missing team dictionaries for SOC, NPB, KBO in `_SPORT_TEAM_MAP`.
  6. Player prop matching in `engine.py:3232` lacked `_normalize_sport`, dropping props when `"SOCCER" != "SOC"` or `"TENNIS" != "TEN"`.
- **Unexplored areas**: None; full problem boundary covered and verified empirically.

## Key Decisions Made
- Confirmed root cause of "only NHL displays" is line 3378 of `engine.py`.
- Verified empirically that parsing `matchup` and extending to 48 hours allows 32 Tennis matches from `KXATPMATCH` to match active AI predictions.
- Synthesized full 5-component report and detailed patch recommendations.

## Artifact Index
- `DISPATCH.md` — Initial dispatch message
- `progress.md` — Liveness heartbeat and progress log
- `report.md` — Full investigation report with exact file paths, line numbers, and proposed code changes
- `handoff.md` — Self-contained 5-component handoff report

# Handoff Report: Investigation of Backend Sports Events Matching & Display

**Agent:** `teamwork_preview_explorer_survey_1`  
**Date:** 2026-10-09  
**Type:** Hard Handoff  

---

## 1. Observation

1. **Kalshi API Returns Open Events Across All Sports:**
   Direct execution of `_fetch_kalshi_series_events(series)` across all series tickers in `_SPORTS_SERIES_MAP` yielded open events for every sport:
   - `NFL`: 117 events (15 spread, 15 total, 32 season wins, 28 game, 14 TD, 13 REC)
   - `NHL`: 111 events (50 game, 21 spread, 4 goal, 18 2P, 18 1P)
   - `TEN`: 47 events (19 ATP, 18 WTA, 5 ATP futures, 5 WTA futures)
   - `SOC`: 68 events (21 EPL, 46 MLS, 1 WC)
   - `KBO`: 24 events (8 game, 8 spread, 8 total)
   - `UFC`: 15 events (3 title, 12 fight)
   - `MLB`: 13 events (5 game, 2 spread, 2 total, 2 F5, 2 HRR)
   - `NPB`: 12 events (4 game, 4 spread, 4 total)

2. **Local AI Engine Returns Active Predictions Across All Sports:**
   Execution of `SportsPredictionClient().fetch_latest_picks()` fetched **293 active picks** from `http://127.0.0.1:8057`:
   - `NBA`: 114 picks
   - `TEN` / `TENNIS`: 112 picks
   - `NFL`: 15 picks
   - `UFC`: 14 picks
   - `MLB`: 13 picks
   - `NHL`: 10 picks
   - `NPB/KBO`: 9 picks
   - `SOC` / `SOCCER`: 6 picks

3. **Verbatim Code in `backend/routes/engine.py:3378`:**
   ```python
   kalshi_events = [e for e in kalshi_events if e.get("is_today")]
   ```
   Where `is_today` is defined at line 3146:
   ```python
   is_today = bool(ev_date == today_et or (start_epoch and start_epoch < time.time()))
   ```
   Testing event retention showed that for upcoming events (`ev_date > today_et`):
   - `MLB`: 13 raw events -> 0 marked `is_today`
   - `NFL`: 117 raw events -> 0 marked `is_today`
   - `NPB`: 12 raw events -> 0 marked `is_today`
   - `KBO`: 24 raw events -> 0 marked `is_today`
   - `SOC`: 68 raw events -> 0 marked `is_today`
   - `UFC`: 15 raw events -> 0 marked `is_today`
   - `NHL`: 111 raw events -> 20 marked `is_today` (games scheduled today 2026-10-09)
   - `TEN`: 47 raw events -> 10 marked `is_today`

4. **Verbatim Code in `backend/routes/engine.py:3257-3376` (Missing `ai_prediction` payload):**
   Top-level dictionary constructed for each event contains:
   `ticker`, `title`, `sport`, `league`, `matchup`, `predicted_team`, `has_ai_prediction`, `ai_pick`, `market_type`, `prop_type`, `line`, `confidence_pct`, `edge_pct`, `markets`, `metadata`.
   There is **no** `"ai_prediction"` key present in the returned dictionary.

5. **Verbatim Code in `backend/routes/engine.py:2946-2950` & `backend/sports_bridge/prediction_client.py:546-547` (Tennis Date Window):**
   `engine.py`:
   ```python
   compare_date = ev_real_date or ev_date
   if p_date and compare_date:
       diff = abs((p_date - compare_date).days)
       if diff > 1:
           date_match = False
   ```
   `prediction_client.py`:
   ```python
   if abs((ed - pd).days) > 1:
       continue
   ```
   `engine.py:3153-3156`:
   ```python
   if ev_date and (today_et - ev_date).days > 1:
       is_stale = True
   if sport_tag == "TEN" and is_stale:
       continue
   ```

6. **Verbatim Code in `backend/routes/engine.py:2854` (Title Regex):**
   ```python
   m_title = re.sub(r'^.*:\s*', '', title or '').strip()
   ```
   When `title = "PHI Eagles vs JAC Jaguars: Total Points"`, `m_title` evaluates to `"Total Points"`.

7. **Verbatim Code in `static/saas_dashboard.html:4106-4109` (Frontend Stale Drop):**
   ```javascript
   const se = parseFloat(e.start_epoch) || 0;
   if (se > 0) {
       const sp = String(e.sport || e.league || '').toUpperCase();
       const capH = /TEN|TENNIS/.test(sp) ? 6 : /MLB|NPB|KBO/.test(sp) ? 5.5 : /NFL|NCAAF/.test(sp) ? 4.5 : /NHL|NBA/.test(sp) ? 3.5 : /SOC|EPL|MLS/.test(sp) ? 3.2 : /UFC/.test(sp) ? 9 : 5;
       if (nowSec - se > capH * 3600) return false;
   }
   ```

---

## 2. Logic Chain

1. **Step 1 (Event Inventory):** Observations 1 and 2 establish that both Kalshi and the AI Prediction Engine possess dozens to hundreds of valid, open sports events and active AI predictions for NFL, MLB, TEN, SOC, UFC, and NPB/KBO. Lack of events or predictions is **not** the cause of the issue.
2. **Step 2 (The Primary Drop Mechanism):** Observation 3 shows that on line 3378, `kalshi_events = [e for e in kalshi_events if e.get("is_today")]` executes after all sports events have been processed. Because games for NFL (Sunday), MLB (Saturday), NPB (Saturday), KBO (Saturday), SOC (Saturday), and UFC (Saturday) have `ev_date > today_et`, their `is_today` flag is `False`. Consequently, line 3378 drops 100% of events for NFL, MLB, NPB, KBO, SOC, and UFC. Only NHL (which has 20 games scheduled today) survives.
3. **Step 3 (Missing API Schema Payload):** Observation 4 shows that although `has_ai_prediction`, `ai_pick`, and `confidence_pct` are set, the actual prediction dictionary `best_pick` is never assigned to `event["ai_prediction"]`. This violates the system contract and Acceptance Criterion R1.
4. **Step 4 (Tennis Discrepancy & Drop):** Observation 5 shows that for Tennis, when the Kalshi ticker date and the AI prediction date differ by 2 days (48 hours) due to tournament duration and Asian time zones, `diff > 1` sets `date_match = False`. Furthermore, `(today_et - ev_date).days > 1` flags the event as stale and discards it.
5. **Step 5 (Frontend Tennis Drop):** Observation 7 shows that for the 10 Tennis events that did survive the backend filter, their Asian start time (1:00 AM ET) is 9.7 hours in the past by morning in New York. Because `capH` is 6 hours, the frontend JavaScript filter discards all 10 events as "finished", displaying "No active AI picks for TEN right now."
6. **Step 6 (Regex Mangling):** Observation 6 proves that line 2854 mangles titles ending in `: Spread` or `: Total Points` into just `"Spread"` or `"Total Points"`, breaking team name extraction for spread and total markets.

---

## 3. Caveats

1. **Live Odds API Key:** The system log notes `THE_ODDS_API_KEY is not configured; live odds requests will be skipped.` This is expected in development/paper mode and does not prevent AI model prediction matching from port 8057.
2. **Soccer Slate Leagues:** Port 8057 currently generates predictions for Bundesliga and La Liga. While Kalshi has open markets for `KXBUNDESLIGA` and `KXLALIGA`, they were omitted from `_SPORTS_SERIES_MAP["SOC"]`. Adding them will enable immediate matching for Soccer.

---

## 4. Conclusion

The sole reason why only NHL displays on the dashboard is that **line 3378 of `backend/routes/engine.py` discards every event where `is_today` is not True**, discarding all upcoming events across NFL, MLB, NPB, KBO, SOC, and UFC.

To fully resolve the issue across the application:
1. Replace line 3378 in `backend/routes/engine.py` to preserve upcoming open events while keeping past-event filtering.
2. Attach `"ai_prediction": best_pick` to each returned event object in `api_sports_events`.
3. Extend the Tennis date matching window from 1 day (24h) to 2 days (48h) in both `backend/routes/engine.py:2948` and `backend/sports_bridge/prediction_client.py:546`, and relax the stale threshold at line 3153.
4. Update title prefix regex at line 2854 to prevent greedy stripping of team names on spread and total markets.
5. Update `capH` in `static/saas_dashboard.html` to prevent open tournament markets from being prematurely hidden.
6. Add `KXBUNDESLIGA` and `KXLALIGA` to `_SPORTS_SERIES_MAP["SOC"]`.

---

## 5. Verification Method

1. **Verify Backend Endpoint via CLI:**
   ```powershell
   $env:PYTHONPATH="."
   python -c "from fastapi.testclient import TestClient; from backend.main import app; c = TestClient(app); [print(sp, len(c.get(f'/api/engine/sports/events?sport={sp}', headers={'Authorization': 'Bearer 7'}).json().get('events', []))) for sp in ['NHL', 'MLB', 'NFL', 'TEN', 'SOC', 'UFC', 'NPB/KBO']]"
   ```
   **Expected Result:** Every sport returns a non-zero count of open events (NHL >= 20, NFL >= 15, MLB >= 2, TEN >= 10, NPB/KBO >= 10).

2. **Verify `ai_prediction` Payload:**
   ```powershell
   $env:PYTHONPATH="."
   python -c "from fastapi.testclient import TestClient; from backend.main import app; c = TestClient(app); res = c.get('/api/engine/sports/events?sport=TEN', headers={'Authorization': 'Bearer 7'}).json(); preds = [e for e in res.get('events', []) if e.get('ai_prediction') is not None]; print('Events with ai_prediction:', len(preds))"
   ```
   **Expected Result:** `Events with ai_prediction > 0`.

3. **Verify Dashboard Tests:**
   ```powershell
   $env:PYTHONPATH="."
   pytest tests/test_sports_dashboard.py -k "test_api_sports_events_npb_kbo or test_api_sports_events_other_sports or test_tennis_and_soccer_sport_normalization"
   ```
   **Expected Result:** Tests pass with exit code 0.

4. **Invalidation Conditions:**
   If `api_sports_events` returns 0 events for NFL, MLB, or NPB/KBO when open events exist on Kalshi, the fix is invalid.

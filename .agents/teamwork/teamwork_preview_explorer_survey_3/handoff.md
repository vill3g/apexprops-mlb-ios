# Handoff Report: Survey 3 — Frontend Display, Tab Selection & Event Filtering

## 1. Observation

1. **HTML Sports Tab Elements**:
   - `static/saas_dashboard.html`, lines 783–789:
     Buttons define sport filters via `onclick="filterSportsEvents('<SPORT>')"`:
     `#btn-asset-nfl` (`'NFL'`), `#btn-asset-mlb` (`'MLB'`), `#btn-asset-nhl` (`'NHL'`), `#btn-asset-npb-kbo` (`'NPB/KBO'`), `#btn-asset-soc` (`'SOC'`), `#btn-asset-ufc` (`'UFC'`), `#btn-asset-ten` (`'TEN'`).
   - Settings drawer checkboxes at lines 8199–8253:
     `.sports-league-toggle` with `value="NFL"`, `"MLB"`, `"NHL"`, `"SOC"`, `"UFC"`, `"TEN"`, `"NPB/KBO"`.

2. **Frontend Loading State Masking Bug**:
   - `static/saas_dashboard.html`, lines 4118–4124:
     ```javascript
     if (list.length === 0) {
         if (window.__sportsLoading && (!window.__sportsEventsCache || window.__sportsEventsCache.length === 0)) {
             container.innerHTML = '<div class="col-span-full text-center text-cyan-400 text-xs py-6 animate-pulse">⚡ Loading ' + label + ' AI picks...</div>';
         } else {
             container.innerHTML = '<div class="col-span-full text-center text-gray-500 text-xs py-6">No active AI picks for ' + label + ' right now.</div>';
         }
         return;
     }
     ```
     `(!window.__sportsEventsCache || window.__sportsEventsCache.length === 0)` checks whether the global cache across all sports is completely empty. When NHL events are loaded on initialization, this is false, causing any tab click on a non-NHL sport to immediately render `"No active AI picks for [sport] right now."` while the network request is still loading.

3. **`isSportMatch` Lacks Ticker and Sport Aliases**:
   - `static/saas_dashboard.html`, lines 4061–4083:
     ```javascript
     function isSportMatch(evt, f) {
         if (!f || f === 'ALL') return true;
         const filterNorm = f.toUpperCase();
         const eSport = String(evt.sport || '').toUpperCase();
         const eLeague = String(evt.league || evt.metadata?.league || '').toUpperCase();
         const eSeries = String(evt.series_ticker || evt.metadata?.series_ticker || '').toUpperCase();
         ...
     ```
     `isSportMatch` checks only `eSport`, `eLeague`, and `eSeries`. It does not inspect `evt.event_ticker` or `evt.ticker` (e.g. `KXATPMATCH-...`, `KXWTAMATCH-...`, `KXNFL...`, `KXMLB...`, `KXEPL...`, `KXUFC...`). It does not normalize `ATP`/`WTA` to `TEN`, `EPL`/`MLS`/`UEFA`/`WC` to `SOC`, `BASEBALL` to `MLB`, `FOOTBALL` to `NFL`, or `HOCKEY` to `NHL`.

4. **Settings Gate Suppresses Explicit Tab Selection**:
   - `static/saas_dashboard.html`, line 4099:
     ```javascript
     if (typeof window.sportsEventAllowed === 'function' && !window.sportsEventAllowed(e)) return false; // Sports & Markets settings
     ```
     `window.sportsEventAllowed(e)` in `static/js/sports-settings-panels.js` lines 271–285 checks `cfg[k].on`. If the user has a sport disabled in background settings, explicitly clicking that sport's tab hides all cards for that sport.

5. **Pull-to-Refresh Filter Inversion**:
   - `static/saas_dashboard.html`, lines 5713–5717:
     ```javascript
     if (window.currentUniverse === 'SPORTS') {
         if (typeof filterSportsEvents === 'function') {
             promises.push(filterSportsEvents(window.sportsFilter || 'NFL'));
         }
     }
     ```
     Because `filterSportsEvents` toggles the active filter, refreshing the page while viewing an active sport tab toggles the filter back to `'ALL'`.

6. **Backend Event Dropping**:
   - `backend/routes/engine.py`, line 3378:
     ```python
     kalshi_events = [e for e in kalshi_events if e.get("is_today")]
     ```
     Where `is_today = bool(ev_date == today_et or (start_epoch and start_epoch < time.time()))` (line 3146). Discards all upcoming games for non-today dates (e.g., Sunday NFL, upcoming tennis matches, MLB, SOC, UFC), returning `events: []`.
   - `backend/routes/engine.py`, lines 2947–2950:
     ```python
     compare_date = ev_real_date or ev_date
     if p_date and compare_date:
         diff = abs((p_date - compare_date).days)
         if diff > 1:
             date_match = False
     ```
     Drops valid tennis AI predictions if Kalshi event and ApexProps model dates differ by more than 24 hours.

7. **Test Execution Result**:
   - Command: `python -m pytest tests/test_sports_dashboard.py`
   - Output: 6 failed, 17 passed.
   - Specific failure: `test_api_sports_events_npb_kbo` and `test_api_sports_events_other_sports` failed with `AssertionError: Expected active events for NFL - where 0 = len([])` due to the backend `is_today` filter.

---

## 2. Logic Chain

1. **Step 1**: Observation 2 establishes that `saas_dashboard.html` line 4119 evaluates `(!window.__sportsEventsCache || window.__sportsEventsCache.length === 0)` when deciding between displaying the loading pulse versus the empty message.
2. **Step 2**: Observation 1 shows that on initialization, `loadSportsEvents('ALL')` caches active events (such as NHL). Thus, `window.__sportsEventsCache.length > 0`.
3. **Step 3**: When a user clicks a non-NHL tab (e.g. TEN), Observation 1 and 2 show that `filterSportsEvents('TEN')` runs `renderSportsEvents()`. Because no TEN events are in cache yet, `list.length === 0`. Because `window.__sportsEventsCache.length > 0`, line 4119 evaluates to `false` and renders `"No active AI picks for TEN right now."` while the network fetch is still pending.
4. **Step 4**: Observation 3 shows that even when the network response arrives, `isSportMatch` does not inspect `event_ticker` or `ticker`. Events returned with series tickers or league names like `ATP`, `WTA`, `EPL`, `MLS`, or `BASEBALL` are dropped.
5. **Step 5**: Observation 4 demonstrates that if the user's auto-trading settings has a sport disabled, `sportsEventAllowed(e)` suppresses cards even when the user explicitly clicks that sport's tab.
6. **Step 6**: Observations 6 and 7 show that on the backend, line 3378 strips all non-today events (`kalshi_events = [e for e in kalshi_events if e.get("is_today")]`), causing the API to return `events: []` for sports not scheduled for today.
7. **Step 7**: Concluding from Steps 1–6, non-NHL sports erroneously display "No active AI picks" because of the premature loading state flash, `isSportMatch` ticker/alias omission, settings gate blocking explicit tab selection, and upstream backend pruning of upcoming events.

---

## 3. Caveats

1. The investigation focused on frontend display, tab selection, and event filtering in `static/saas_dashboard.html` and related static JS assets as requested.
2. We investigated the backend route `/api/engine/sports/events` in `backend/routes/engine.py` strictly to trace the API contract and data shapes returned to the frontend. Modifying backend Python code should be delegated to SWE implementation agents.
3. Live trade execution on port 8058 was verified conceptually via static code analysis and pytest suite inspection.

---

## 4. Conclusion

The display issue is caused by four frontend flaws and two backend constraints:
1. **Frontend Fix 1 (`saas_dashboard.html:4119`)**: Replace `if (window.__sportsLoading && (!window.__sportsEventsCache || window.__sportsEventsCache.length === 0))` with `if (window.__sportsLoading)` so switching tabs displays the pulse loader rather than "No active AI picks".
2. **Frontend Fix 2 (`saas_dashboard.html:4061-4083`)**: Update `isSportMatch` to inspect `eTicker = evt.event_ticker || evt.ticker` and include aliases (`ATP`, `WTA` for TEN; `EPL`, `MLS`, `UEFA`, `WC` for SOC; `BASEBALL` for MLB; `FOOTBALL` for NFL; `HOCKEY` for NHL; `MMA` for UFC; `KX(NPB|KBO)` for NPB/KBO).
3. **Frontend Fix 3 (`saas_dashboard.html:4099`)**: Scope `sportsEventAllowed(e)` so that when browsing a specific sport tab (`f !== 'ALL'`), background league toggles do not hide that sport's cards.
4. **Frontend Fix 4 (`saas_dashboard.html:5715`)**: Change `filterSportsEvents(window.sportsFilter || 'NFL')` to `loadSportsEvents(window.sportsFilter)` in `manualDashboardRefresh`.
5. **Frontend Fix 5 (`saas_dashboard.html:4013-4031`)**: Add `ATP`, `WTA`, `EPL`, `MLS`, `UEFA`, `BASEBALL`, `FOOTBALL`, `HOCKEY` aliases to `SPORT_ICONS`.
6. **Backend Recommendation (`backend/routes/engine.py:3378, 2948`)**: Remove the strict `is_today` deletion of future games and extend the tennis date matching window to 48 hours (`diff > 2`).

---

## 5. Verification Method

1. **Static Inspection**:
   - Inspect `static/saas_dashboard.html` lines 4061–4083 to verify `isSportMatch` checks `event_ticker` / `ticker` prefixes and sport aliases.
   - Inspect `static/saas_dashboard.html` line 4119 to verify the pulse loader check is `if (window.__sportsLoading)`.
   - Inspect `static/saas_dashboard.html` line 4099 to verify `sportsEventAllowed` only applies when `f === 'ALL'`.
2. **Regression Test Command**:
   ```powershell
   python -m pytest tests/test_sports_dashboard.py
   ```
3. **Invalidation Conditions**:
   - If clicking the "TEN" tab while NHL events are cached still shows "No active AI picks for TEN right now" while network requests are in flight.
   - If an event with ticker `KXATPMATCH-...` is filtered out when the TEN tab is selected.

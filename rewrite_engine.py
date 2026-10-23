import re

with open('backend/routes/engine.py', 'r') as f:
    engine_code = f.read()

import_stmt = "from backend.engine.kalshi_events_cache import get_series_events, get_milestone_map\n"

# Replace _fetch_kalshi_series_events body
s1 = "def _fetch_kalshi_series_events(series: str) -> list:"
e1 = "        time.sleep(1.0)\n    return []"
if s1 in engine_code and e1 in engine_code:
    idx1 = engine_code.find(s1)
    idx2 = engine_code.find(e1, idx1) + len(e1)
    engine_code = engine_code[:idx1] + "def _fetch_kalshi_series_events(series: str) -> list:\n    return get_series_events(series)\n" + engine_code[idx2:]

# Replace the ThreadPool logic in api_sports_events
s2 = "        if unique_series:\n            with concurrent.futures.ThreadPoolExecutor"
e2 = "series_data_map[s] = []\n"
if s2 in engine_code and e2 in engine_code:
    idx1 = engine_code.find(s2)
    idx2 = engine_code.find(e2, idx1) + len(e2)
    replacement = """        if unique_series:
            for s in unique_series:
                series_data_map[s] = _fetch_kalshi_series_events(s)
"""
    engine_code = engine_code[:idx1] + replacement + engine_code[idx2:]

# Replace _fetch_all_slates_for_times() call with get_milestone_map()
s3 = "slate_map = _fetch_all_slates_for_times()"
if s3 in engine_code:
    engine_code = engine_code.replace(s3, "milestone_map = get_milestone_map()")

if import_stmt not in engine_code:
    idx_import = engine_code.find("import logging")
    engine_code = engine_code[:idx_import] + import_stmt + engine_code[idx_import:]

with open('backend/routes/engine.py', 'w') as f:
    f.write(engine_code)

import re

with open('backend/routes/engine.py', 'r') as f:
    c = f.read()

s = "def extract_sports_event_date_and_time("
e = 'return ev_date, start_epoch'

idx1 = c.find(s)
idx2 = c.find(e, idx1) + len(e)

new_func = """def extract_sports_event_date_and_time(
    ticker: str,
    metadata: Optional[dict] = None,
    event_obj: Optional[dict] = None,
    milestone: Optional[dict] = None
) -> tuple[Optional[date], Optional[float]]:
    metadata = metadata or {}
    event_obj = event_obj or {}
    
    if milestone and milestone.get("start_date"):
        try:
            dt = datetime.fromisoformat(milestone["start_date"].replace("Z", "+00:00"))
            dt_et = dt.astimezone(ZoneInfo("America/New_York"))
            return dt_et.date(), dt_et.timestamp()
        except Exception:
            pass

    if event_obj.get("markets"):
        for m in event_obj["markets"]:
            exp_time = m.get("expected_expiration_time") or m.get("occurrence_datetime")
            if exp_time:
                try:
                    dt = datetime.fromisoformat(exp_time.replace("Z", "+00:00"))
                    dt_et = dt.astimezone(ZoneInfo("America/New_York"))
                    return dt_et.date(), dt_et.timestamp()
                except Exception:
                    pass

    return None, None"""

c = c[:idx1] + new_func + c[idx2:]

with open('backend/routes/engine.py', 'w') as f:
    f.write(c)

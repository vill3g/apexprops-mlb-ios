import re

with open('backend/routes/engine.py', 'r') as f:
    c = f.read()

# Replace the giant slate_time_str block
pattern = r"slate_time_str = None.*?ev_date, start_epoch = extract_sports_event_date_and_time\(event_ticker, event_obj=e, slate_time_str=slate_time_str\)"
replacement = """milestone = milestone_map.get(event_ticker)
                    ev_date, start_epoch = extract_sports_event_date_and_time(event_ticker, event_obj=e, milestone=milestone)"""

c = re.sub(pattern, replacement, c, flags=re.DOTALL)

# Also fix the signature of extract_sports_event_date_and_time
c = c.replace("slate_time_str = None", "milestone = None")

with open('backend/routes/engine.py', 'w') as f:
    f.write(c)

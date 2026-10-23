
with open('backend/routes/engine.py') as f:
    c = f.read()
    idx = c.find('def extract_sports_event_date_and_time')
    print(c[idx:idx+1500])


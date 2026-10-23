
with open('backend/routes/engine.py', 'r') as f:
    c = f.read()
    idx = c.find('def api_sports_events')
    print(c[idx:idx+2500])


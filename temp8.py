
with open('backend/routes/engine.py') as f:
    c = f.read()
    idx = c.find('def parse_sports_market_details')
    idx_end = c.find('def api_sports_events', idx)
    with open('parse.txt', 'w') as out:
        out.write(c[idx:idx_end])



with open('backend/routes/engine.py') as f:
    c = f.read()
    idx = c.find('def parse_sports_market_details')
    print(c[idx:idx+2000])


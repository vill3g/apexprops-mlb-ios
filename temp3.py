
with open('backend/routes/engine.py') as f:
    c = f.read()
    idx = c.find('def api_sports_predict')
    print(c[idx+3500:idx+5500])


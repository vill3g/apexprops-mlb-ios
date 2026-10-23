
with open('backend/sports_bridge/prediction_client.py') as f:
    c = f.read()
    idx = c.find('def fetch_latest_picks')
    print(c[idx:idx+1500])


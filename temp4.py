
with open('backend/sports_bridge/prediction_client.py') as f:
    c = f.read()
    idx = c.find('def predict_for_event')
    print(c[idx:idx+2500])


with open("backend/routes/engine.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find('prediction = client.predict_for_event(event_ticker, title=event_title, sport=event_sport)')
print(text[idx-200:idx+2500])

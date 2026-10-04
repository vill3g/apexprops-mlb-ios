import re

with open('backend/routes/engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add import if missing
if 'SportsPredictionClient' not in code:
    code = code.replace('from fastapi.responses import JSONResponse', 'from fastapi.responses import JSONResponse\nfrom backend.sports_bridge.prediction_client import SportsPredictionClient')

# Add route if missing
if '/api/engine/sports/events' not in code:
    route_code = '''
@router.get("/api/engine/sports/events")
def api_sports_events():
    client = SportsPredictionClient()
    picks = client.fetch_latest_picks()
    return {"status": "ok", "events": picks}
'''
    code += route_code

with open('backend/routes/engine.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Added sports events route')

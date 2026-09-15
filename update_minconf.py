import requests

r = requests.get('http://localhost:8056/api/btc/trade/status')
settings = r.json().get('ai_settings', {})
settings['minConf'] = 65

r2 = requests.post('http://localhost:8056/api/btc/trade/ai_settings', json=settings)
print(r2.status_code, "minConf updated to:", r2.json().get('settings', {}).get('minConf'))

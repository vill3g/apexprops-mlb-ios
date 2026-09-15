import requests

# Get current
r = requests.get('http://localhost:8056/api/btc/trade/status')
data = r.json()
settings = data.get('ai_settings', {})

# Update
settings['minConf'] = 75
settings['trainWindow'] = 1000
settings['edgeWeightFactor'] = 1.5

# Post back
r2 = requests.post('http://localhost:8056/api/btc/trade/ai_settings', json=settings)
print(r2.status_code, r2.text)

import requests
r = requests.get('http://127.0.0.1:8057/api/tennis/top_picks').json()
print(list(r['top_picks'][0].keys()))

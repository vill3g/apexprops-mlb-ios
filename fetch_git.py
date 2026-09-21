import urllib.request
try:
    url = "https://raw.githubusercontent.com/vill3g/apexprops-mlb-ios/main/static/index.html"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
    with open('static/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Successfully restored from GitHub!")
except Exception as e:
    print("Failed to restore from GitHub:", e)

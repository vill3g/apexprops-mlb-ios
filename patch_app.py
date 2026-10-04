import re

app_path = r'C:\Users\Vill3\Desktop\ShadowTraderAi\static\js\app.js'
with open(app_path, 'r', encoding='utf-8') as f:
    app_js = f.read()

app_js = app_js.replace('window.API_BASE_URL + ', 'getKalshiApiBase() + ')

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(app_js)
print("Patched app.js successfully.")

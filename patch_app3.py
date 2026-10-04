import re

app_path = r'C:\Users\Vill3\Desktop\ShadowTraderAi\static\js\app.js'
with open(app_path, 'r', encoding='utf-8') as f:
    app_js = f.read()

# Fix the property names parsing
app_js = app_js.replace('if (ex.exchange === 0)', 'if (ex.exchange_index === 0)')
app_js = app_js.replace('if (ex.exchange === 2)', 'if (ex.exchange_index === 2)')
app_js = app_js.replace('mainBal = parseFloat(ex.balance_dollars) || 0.0;', 'mainBal = parseFloat(ex.balance) || 0.0;')
app_js = app_js.replace('cryptoBal = parseFloat(ex.balance_dollars) || 0.0;', 'cryptoBal = parseFloat(ex.balance) || 0.0;')

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(app_js)
print("Patched app.js successfully.")

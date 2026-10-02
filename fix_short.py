file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\app.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('      if (token) {\n        headers["X-API-Token"] = token;\n      }\n      return headers;\n      const saasToken =', '      if (token) {\n        headers["X-API-Token"] = token;\n      }\n      const saasToken =')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("app.js fixed short circuit")

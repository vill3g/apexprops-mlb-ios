file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\admin_users.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """    if (saasToken) {
      headers["Authorization"] = `Bearer ${saasToken}`;
    }
  }"""
  
replacement = """    if (saasToken) {
      headers["Authorization"] = `Bearer ${saasToken}`;
    }
    return headers;
  }"""

content = content.replace(target, replacement)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("admin_users.js patched using exact substring!")

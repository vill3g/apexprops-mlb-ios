import os

path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add viewport-fit=cover
if "viewport-fit=cover" not in content:
    content = content.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">'
    )
    content = content.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">'
    )

# 2. Fix Header z-index and background
if 'z-[999]' not in content:
    content = content.replace('z-50 bg-black', 'z-[999] bg-black')
    
# 3. Ensure header has solid background and no blur
content = content.replace('backdrop-blur', '')

# 4. Check for absolute paths
content = content.replace('href="/static/', 'href="./')
content = content.replace('src="/static/', 'src="./')

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("saas_dashboard.html patched!")

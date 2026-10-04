import os

path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Prepend the ngrok URL to any profile_pic if it starts with /static/
# Instead of complex regex, let's just add a helper function and use it for image srcs.
# Wait, let's just replace s.profile_pic logic.

content = content.replace(
    "if (s.profile_pic) {",
    "if (s.profile_pic) {\n                    if (s.profile_pic.startsWith('/static/')) s.profile_pic = 'https://moneyprinter.ngrok.app' + s.profile_pic;"
)

content = content.replace(
    "src=\"${t.profile_pic || './assets/icon.png'}\"", 
    "src=\"${(t.profile_pic && t.profile_pic.startsWith('/static/')) ? 'https://moneyprinter.ngrok.app'+t.profile_pic : (t.profile_pic || './assets/icon.png')}\""
)

# Wait, the template strings use ''
content = content.replace(
    "src=\"\"",
    "src=\"\""
)

content = content.replace(
    "src=\"\"",
    "src=\"\""
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Profile pics fixed!")

import os

path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\js\admin_users.js"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("u.profile_picture_url", "(u.profile_picture_url && u.profile_picture_url.startsWith('/static/') ? 'https://moneyprinter.ngrok.app' + u.profile_picture_url : u.profile_picture_url)")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Admin profile pics fixed!")

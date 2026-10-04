import os

base_dir = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static"

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".html") or file.endswith(".js"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            content = content.replace('./ai_avatar.gif', './assets/icon.png')
            content = content.replace('/static/ai_avatar.gif', './assets/icon.png')
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
print("Replaced ai_avatar.gif everywhere!")

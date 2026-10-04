import json

path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\manifest.json"
with open(path, "r") as f:
    data = json.load(f)

data["icons"] = [
    {"src": "./assets/app_icon_192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
    {"src": "./assets/app_icon_512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    {"src": "./assets/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"}
]

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print("manifest.json updated!")

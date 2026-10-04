import os

path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('id="assetSelectorBar" class="bg-[#0b101d]', 'id="assetSelectorBar" class="sticky top-[calc(3.5rem+env(safe-area-inset-top,0px))] z-40 bg-[#0b101d]')

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("assetSelectorBar made sticky!")

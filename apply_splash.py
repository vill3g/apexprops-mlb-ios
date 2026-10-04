import os

path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace nav avatar
content = content.replace('src="./ai_avatar.gif"', 'src="./assets/icon.png"')
content = content.replace("src=''", "src=''")

# 2. Replace SVG in splash screen with the splash image
old_svg_start = '<!-- Composite Logo: Crypto'
old_svg_end = '</svg>'

start_idx = content.find(old_svg_start)
end_idx = content.find(old_svg_end)

if start_idx != -1 and end_idx != -1:
    old_content = content[start_idx:end_idx + len(old_svg_end)]
    new_content = '<img src="./assets/splash.png" class="absolute inset-0 w-full h-full object-cover" alt="ShadowTrader AI">'
    
    # We also want to remove the glow backdrop and relative w-28 h-28 classes since the splash.png is full screen
    content = content.replace('<div class="absolute w-72 h-72 bg-purple-600/20 rounded-full  pointer-events-none animate-pulse"></div>', '')
    content = content.replace('<div class="relative w-28 h-28 mb-5">', '<div class="absolute inset-0 w-full h-full">')
    
    content = content.replace(old_content, new_content)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("saas_dashboard.html patched for new splash and icon!")

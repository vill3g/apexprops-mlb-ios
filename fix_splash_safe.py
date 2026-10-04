import os

path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the inner SVG part exactly
start_marker = "<!-- Glow Backdrop -->"
end_marker = "<!-- Spline/Pulse Core -->"

idx1 = content.find(start_marker)
# Find the exact end of the SVG block
end_svg = content.find("</svg>", idx1)

if idx1 != -1 and end_svg != -1:
    # We replace everything from Glow Backdrop to </svg> + </div></div>
    # Actually, let's just find the exact text block
    part1 = content[:idx1]
    
    # find the script tag that starts right after the splash HTML
    script_start = content.find("<script>", idx1)
    
    part2 = content[script_start:]
    
    new_splash = '''
    <img src="./assets/splash.png" class="absolute inset-0 w-full h-full object-cover" alt="ShadowTrader AI">
    '''
    content = part1 + new_splash + part2

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Splash fixed safely!")

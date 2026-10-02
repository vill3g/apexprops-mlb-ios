import re

html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

pattern = r'<div class="flex items-center gap-2">\s*<div onclick="showMarketRegime\(\)" class="relative w-7 h-7 sm:w-8 sm:h-8 rounded-full shrink-0 p-\[1px\] bg-gradient-to-tr from-cyan-500/70 via-purple-500/50 to-amber-500/60 shadow-\[0_0_12px_rgba\(6,182,212,0\.35\)\] flex items-center justify-center group cursor-pointer transition-transform hover:scale-105 active:scale-95" title="Click to view Live AI Market Regime">'

replacement = """<div class="flex items-center gap-2 cursor-pointer group active:scale-95 transition-transform" onclick="openSocialModal()" title="View Your Stats">
                <div class="relative w-7 h-7 sm:w-8 sm:h-8 rounded-full shrink-0 p-[1px] bg-gradient-to-tr from-cyan-500/70 via-purple-500/50 to-amber-500/60 shadow-[0_0_12px_rgba(6,182,212,0.35)] flex items-center justify-center transition-transform group-hover:scale-105">"""

html = re.sub(pattern, replacement, html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated user profile click logic!")

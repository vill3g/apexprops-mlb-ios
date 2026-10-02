import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the select tag to include AUTO
pattern = re.compile(r'<select id="signal-source" class="hidden" onchange="saveUserConfig()">.*?</select>', re.DOTALL)
new_select = '<select id="signal-source" class="hidden" onchange="saveUserConfig()"><option value="AUTO">🤖 AUTO</option><option value="BLEND">⚖️ BLEND</option><option value="AI_ONLY">🧠 AI ONLY</option><option value="CHART_ONLY">📊 CHART ONLY</option></select>'

content = pattern.sub(new_select, content)

# Also fix the JS fallback display text for AUTO if it's broken
content = content.replace("signalSource === 'BLEND' ? '⚖️ BLEND'", "signalSource === 'AUTO' ? '🤖 AUTO' : signalSource === 'BLEND' ? '⚖️ BLEND'")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched saas_dashboard.html")

import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Instead of regex, let's just do a string replace since we know exactly what is there.
old_select1 = '<select id="signal-source" class="hidden" onchange="saveUserConfig()"><option value="BLEND">⚖️ BLEND</option><option value="AI_ONLY">🧠 AI ONLY</option><option value="CHART_ONLY">📊 CHART ONLY</option></select>'
old_select2 = '<select id="signal-source" class="hidden" onchange="saveUserConfig()"><option value="BLEND">?? BLEND</option><option value="AI_ONLY">?? AI ONLY</option><option value="CHART_ONLY">?? CHART ONLY</option></select>'

new_select = '<select id="signal-source" class="hidden" onchange="saveUserConfig()"><option value="AUTO">🤖 AUTO</option><option value="BLEND">⚖️ BLEND</option><option value="AI_ONLY">🧠 AI ONLY</option><option value="CHART_ONLY">📊 CHART ONLY</option></select>'

if old_select1 in content:
    content = content.replace(old_select1, new_select)
elif old_select2 in content:
    content = content.replace(old_select2, new_select)
else:
    # Use split and join to forcefully replace it
    parts = content.split('<select id="signal-source"')
    if len(parts) > 1:
        post_select = parts[1].split('</select>')[1]
        content = parts[0] + new_select + post_select

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched!")

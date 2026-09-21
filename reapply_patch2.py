with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Insert AUTO and CHOP options for tradingStyle
opts = '''<option value="AUTO" selected>\uD83E\uDD16 AUTO (Adaptive)</option>
                            <option value="SNIPER">\uD83C\uDFAF Sniper (15m)</option>
                            <option value="MACHINE_GUN">\uD83D\uDD2B Machine Gun (1m)</option>
                            <option value="CHOP">\u2696\uFE0F Chop Engine (Low Vol)</option>'''
                            
text = re.sub(r'<option value="SNIPER".*?Machine Gun \(1m\)</option>', opts, text, flags=re.DOTALL)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Added CHOP")

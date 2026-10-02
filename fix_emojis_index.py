import sys
content = open('static/index.html', 'r', encoding='utf-8').read()
import re
content = re.sub(r'<option value="SNIPER">.*?</option>', '<option value="SNIPER">🎯 Sniper</option>', content)
content = re.sub(r'<option value="MOMENTUM_SURFER">.*?</option>', '<option value="MOMENTUM_SURFER">🌊 Momentum</option>', content)
content = re.sub(r'<option value="AMBUSH">.*?</option>', '<option value="AMBUSH">⚡ Ambush</option>', content)
content = re.sub(r'<option value="CHOP">.*?</option>', '<option value="CHOP">🔄 Chop</option>', content)
content = re.sub(r'<span>.*?</span> MOMENTUM SURFER', '<span>🌊</span> MOMENTUM SURFER', content)
open('static/index.html', 'w', encoding='utf-8').write(content)

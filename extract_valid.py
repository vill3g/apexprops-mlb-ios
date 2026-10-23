with open("backend/routes/engine.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = re.finditer(r'has_valid_pick = True(.*?)clean_mkt_sub', text, re.DOTALL)
for m in matches:
    print(m.group(0))

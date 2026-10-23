with open("backend/routes/engine.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
match = re.search(r'def api_sports_predict\(.*?return \{', text, re.DOTALL)
if match:
    print(match.group(0))

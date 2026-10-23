with open("backend/sports_bridge/prediction_client.py", "r", encoding="utf-8") as f:
    c = f.read()

import re
# Remove the if not any for Soccer
soc_re = r'# 4\. Fetch Soccer slate\n\s+if not any\(\(p\.get\("sport"\) or ""\)\.upper\(\) in \("SOC", "SOCCER"\) for p in all_picks\):\n\s+try:'
soc_new = """# 4. Fetch Soccer slate
        try:"""
c = re.sub(soc_re, soc_new, c)
# The except block is indented correctly relative to try, but since we removed the `if not any`, we need to dedent the try/except block.
# Actually, the easiest way is to just do a simple string replace.

with open("backend/sports_bridge/prediction_client.py", "w", encoding="utf-8") as f:
    f.write(c)

print("Removed if not any wrappers")

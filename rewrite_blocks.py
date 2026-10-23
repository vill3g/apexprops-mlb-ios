with open("backend/sports_bridge/prediction_client.py", "r", encoding="utf-8") as f:
    c = f.read()

import re

# We can just replace the `if not any(...)` with `if True:` so the indentation stays valid!
c = re.sub(r'if not any\(\(p\.get\("sport"\) or ""\)\.upper\(\) in \("SOC", "SOCCER"\) for p in all_picks\):', 'if True:', c)
c = re.sub(r'if not any\(\(p\.get\("sport"\) or ""\)\.upper\(\) in \("UFC", "MMA"\) for p in all_picks\):', 'if True:', c)

with open("backend/sports_bridge/prediction_client.py", "w", encoding="utf-8") as f:
    f.write(c)

print("Replaced with if True:")

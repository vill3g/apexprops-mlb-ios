import re
import json

path = "backend/auth/routes.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

pattern = r'elif t\.get\("market_snapshot", \{\}\)\.get\("probability_percent"\) is not None:.*?(?=else:)'
replacement = """elif t.get("market_snapshot"):
                ms = t.get("market_snapshot")
                if isinstance(ms, str):
                    try:
                        ms = __import__('json').loads(ms)
                    except:
                        ms = {}
                if not isinstance(ms, dict):
                    ms = {}
                if ms.get("probability_percent") is not None:
                    prob_pct = float(ms["probability_percent"])
                elif ms.get("confidence") is not None:
                    prob_pct = float(ms["confidence"])
        """

code = re.sub(pattern, replacement, code, flags=re.DOTALL)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)
print("Fixed market_snapshot parsing in routes.py")

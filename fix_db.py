
import re
with open("backend/database/trade_store.py", "r", encoding="utf-8") as f:
    content = f.read()

old_code = "return [json.loads(row[0]) for row in cursor.fetchall()]"
new_code = """
            results = []
            for row in cursor.fetchall():
                try:
                    parsed = json.loads(row[0])
                    if isinstance(parsed, dict):
                        results.append(parsed)
                except Exception:
                    pass
            return results
"""
content = content.replace(old_code, new_code.strip())

with open("backend/database/trade_store.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed DB fetch")


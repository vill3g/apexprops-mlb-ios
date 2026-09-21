import json, os, sys, glob
sys.stdout.reconfigure(encoding='utf-8')

# 1. Validate all JSON files
print("=" * 60)
print("JSON VALIDATION")
print("=" * 60)
json_files = glob.glob("backend/data/*.json") + glob.glob("backend/btc/*.json") + glob.glob("backend/*.json")
for jf in json_files:
    try:
        with open(jf, 'r', encoding='utf-8') as f:
            json.load(f)
        print(f"  OK: {jf}")
    except Exception as e:
        print(f"  FAIL: {jf} -> {e}")

# 2. Check getElementById mismatches
print("\n" + "=" * 60)
print("FRONTEND: getElementById calls in app.js")
print("=" * 60)
import re
with open("static/js/app.js", encoding="utf-8") as f:
    js = f.read()
js_ids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', js))

with open("static/index.html", encoding="utf-8") as f:
    html = f.read()
html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))

missing = js_ids - html_ids
if missing:
    print(f"  WARNING: {len(missing)} IDs referenced in JS but NOT found in HTML:")
    for mid in sorted(missing):
        print(f"    - {mid}")
else:
    print("  OK: All getElementById calls match HTML element IDs")

extra = html_ids - js_ids
print(f"\n  INFO: {len(extra)} HTML IDs not referenced in JS (probably CSS-only or unused)")

# 3. Check for duplicate IDs in HTML
from collections import Counter
all_html_ids = re.findall(r'id=["\']([^"\']+)["\']', html)
dupes = {k: v for k, v in Counter(all_html_ids).items() if v > 1}
if dupes:
    print(f"\n  WARNING: {len(dupes)} DUPLICATE element IDs in index.html:")
    for did, cnt in sorted(dupes.items()):
        print(f"    - '{did}' appears {cnt} times")
else:
    print("\n  OK: No duplicate IDs in index.html")

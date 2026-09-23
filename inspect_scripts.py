import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Find the MAIN big script block (last one)
all_scripts = [(m.start(), m.end()) for m in re.finditer(r'<script(?:[^>]*)>.*?</script>', c, re.DOTALL)]
print(f"Found {len(all_scripts)} script blocks")
for i, (start, end) in enumerate(all_scripts):
    blk = c[start:end]
    print(f"\n--- Script block {i+1} (len={len(blk)}) ---")
    print(blk[:150])
    print("...")

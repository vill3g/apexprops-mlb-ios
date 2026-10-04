import re

with open('static/saas_dashboard.html', encoding='utf-8') as f:
    lines = f.readlines()

corrupted = []
for idx, line in enumerate(lines):
    matches = re.finditer(r'[\s"\'](-2xl|-xl|-lg|-md|-sm)[\s"\']', line)
    for m in matches:
        corrupted.append((idx + 1, m.group(1), line.strip()[:100]))

print(f"Corrupted Tailwind utility classes found: {len(corrupted)}")
for l, c, text in corrupted:
    print(f"  L{l}: class '{c}' in: {text}")

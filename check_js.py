import re, subprocess, tempfile

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
for i, s in enumerate(scripts):
    print(f"Script {i} length: {len(s)}")
    # We can't easily syntax check without node, but we can look for obvious unclosed strings/braces

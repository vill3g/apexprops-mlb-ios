import re

with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    html = f.read()

# Let's extract the JS and look for syntax errors.
scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
js_code = scripts[1] if len(scripts) > 1 else scripts[0]

with open("test.js", "w", encoding="utf-8") as f:
    f.write(js_code)
print(f"Extracted {len(js_code)} bytes of JS.")

import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

btn = '''
<div style="position: fixed; bottom: 10px; right: 10px; z-index: 9999;">
    <a href="/login.html" style="background: #00ff88; color: #121212; padding: 8px 12px; border-radius: 20px; font-weight: bold; font-size: 12px; text-decoration: none; box-shadow: 0 4px 6px rgba(0,0,0,0.5);">SaaS Copilot Login</a>
</div>
'''

if 'SaaS Copilot Login' not in content:
    content = content.replace('</body>', btn + '\n</body>')
    with open('static/index.html', 'w', encoding='utf-8') as f:
        f.write(content)

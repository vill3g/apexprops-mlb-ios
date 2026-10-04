import re
import py_compile
import subprocess

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

scripts = re.findall(r'<script\b[^>]*>([\s\S]*?)<\/script>', html, re.IGNORECASE)
for i, script in enumerate(scripts):
    if not script.strip(): continue
    with open(f'temp_script_{i}.js', 'w', encoding='utf-8') as f:
        f.write(script)
    try:
        subprocess.run(['node', '-c', f'temp_script_{i}.js'], check=True, capture_output=True, text=True)
        print(f'Script {i} OK')
    except subprocess.CalledProcessError as e:
        print(f'Script {i} ERROR:')
        print(e.stderr)

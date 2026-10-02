import subprocess
import re

out = subprocess.check_output([r'C:\Users\Vill3\AppData\Local\GitHubDesktop\app-3.6.6\resources\app\git\cmd\git.exe', 'show', 'HEAD:static/js/app.js'], encoding='utf-8')

matches = re.finditer(r'function getAuthHeaders.*?return headers;\s*\}', out, re.DOTALL)
for m in matches:
    print(m.group(0))
    print("---")

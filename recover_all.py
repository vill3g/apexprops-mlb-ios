import os
import subprocess
import time

scripts_dir = r'C:\Users\Vill3\Desktop\kalshi-ai-trader'
scripts = []
for f in os.listdir(scripts_dir):
    if f.endswith('.py'):
        path = os.path.join(scripts_dir, f)
        mtime = os.path.getmtime(path)
        # From 09/23/2026 00:20:00 to 09/28/2026 00:00:00
        # Wait, create_preview.py is at 00:25:34 on 09/23.
        # write_iphone_dashboard is at 00:24:25 on 09/23.
        # I'll just filter explicitly.
        if mtime > 1790137200 and mtime < 1790568000: # Approx Sep 22 to Sep 27
            with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
                if "static/saas_dashboard.html" in content or "static/js/dashboard.js" in content or "static/index.html" in content:
                    scripts.append((path, mtime, f))

# Sort by modification time
scripts.sort(key=lambda x: x[1])

print(f"Found {len(scripts)} scripts. Executing in order...")
for path, mtime, f in scripts:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))}] Running {f}...")
    try:
        res = subprocess.run([r'C:\Users\Vill3\Desktop\kalshi-ai-trader\.venv\Scripts\python.exe', path], capture_output=True, text=True, cwd=scripts_dir)
        if res.returncode != 0:
            print(f"  FAILED: {res.stderr.strip()}")
        else:
            print(f"  Success.")
    except Exception as e:
        print(f"  Error: {e}")

print("Recovery complete.")

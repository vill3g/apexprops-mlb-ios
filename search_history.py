import os
import time

search_file = "index.html"
target_size_min = 70000
target_size_max = 150000
found = []

# Quick search in AppData for VS Code History
history_path = os.path.expandvars(r"%APPDATA%\Code\User\History")
if os.path.exists(history_path):
    for root, dirs, files in os.walk(history_path):
        for file in files:
            full_path = os.path.join(root, file)
            try:
                size = os.path.getsize(full_path)
                if size > target_size_min and size < target_size_max:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if "kalshi" in content.lower() and "<html" in content.lower():
                            found.append((full_path, os.path.getmtime(full_path)))
            except:
                pass

found.sort(key=lambda x: x[1], reverse=True)
for f, t in found[:10]:
    print(f"Found potential VS Code history backup: {f} modified {time.ctime(t)}")

import os
import re

file_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add profile mount
mount_str = 'app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")'
if mount_str in content and 'app.mount("/profiles"' not in content:
    new_mount = """app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

PROFILES_DIR = os.path.join(DATA_DIR, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)
app.mount("/profiles", StaticFiles(directory=PROFILES_DIR), name="profiles")"""
    content = content.replace(mount_str, new_mount)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Mounted /profiles")
else:
    print("Already mounted or static mount not found")

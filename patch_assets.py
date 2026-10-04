
import os
import json

base_dir = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

# 1. Update package.json
pkg_path = os.path.join(base_dir, "package.json")
with open(pkg_path, "r", encoding="utf-8") as f:
    data = json.load(f)

if "devDependencies" not in data:
    data["devDependencies"] = {}
data["devDependencies"]["@capacitor/assets"] = "^3.0.0"

with open(pkg_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

# 2. Update build-ios.yml
yml_path = os.path.join(base_dir, ".github", "workflows", "build-ios.yml")
with open(yml_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add the assets command after npx cap sync ios
old_sync = "- name: Sync Capacitor\n        run: npx cap sync ios"
new_sync = """- name: Sync Capacitor
        run: npx cap sync ios

      - name: Generate Custom App Icon & Splash Screen
        run: npx @capacitor/assets generate --ios"""

content = content.replace(old_sync, new_sync)

with open(yml_path, "w", encoding="utf-8") as f:
    f.write(content)


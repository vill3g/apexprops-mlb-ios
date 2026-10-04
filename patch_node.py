
import os

repo1 = r"C:\Users\Vill3\Desktop\ShadowTraderAi\.github\workflows\build-ios.yml"
repo2 = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\.github\workflows\build-ios.yml"

for path in [repo1, repo2]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("node-version: 20", "node-version: 24")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)



import os

with open(".github/workflows/build-ios.yml", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("branches: [ \"main\", \"master\" ]", "branches: [ \"main\", \"master\", \"kalshi-ai-trader\" ]")

with open(".github/workflows/build-ios.yml", "w", encoding="utf-8") as f:
    f.write(content)


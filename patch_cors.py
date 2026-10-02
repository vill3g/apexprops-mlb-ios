
import os

with open("backend/main.py", "r", encoding="utf-8") as f:
    content = f.read()

target = """        "http://localhost:8055",
        "https://localhost",
    ]"""

new_target = """        "http://localhost:8055",
        "https://localhost",
        "capacitor://localhost",
        "ionic://localhost",
        "*"
    ]"""

content = content.replace(target, new_target)

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(content)


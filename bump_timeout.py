import re
with open('backend/routes/engine.py', 'r') as f:
    content = f.read()

content = content.replace("with httpx.Client(timeout=3.0) as c:", "with httpx.Client(timeout=7.0) as c:")

with open('backend/routes/engine.py', 'w') as f:
    f.write(content)

print("Bumped timeout.")

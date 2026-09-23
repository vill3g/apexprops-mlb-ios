with open("backend/auth/routes.py", "r", encoding="utf-8") as f:
    code = f.read()

code = code.replace("for t in trades_filtered[-50:][::-1]:", "for t in trades[-50:][::-1]:")

with open("backend/auth/routes.py", "w", encoding="utf-8") as f:
    f.write(code)

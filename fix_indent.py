path = "backend/auth/routes.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if line.startswith("      while count > 0 and (count * price"):
        lines[i] = line.replace("      while", "    while")
    elif line.startswith("          count -= 1"):
        lines[i] = line.replace("          count -= 1", "        count -= 1")
with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

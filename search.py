import os

for root, _, files in os.walk('backend'):
    for f in files:
        if f.endswith('.py'):
            with open(os.path.join(root, f), 'r', encoding='utf-8') as file:
                lines = file.readlines()
                for i, line in enumerate(lines):
                    if '60.0' in line or '65.0' in line or '55.0' in line:
                        print(f"{f}:{i+1}: {line.strip()}")

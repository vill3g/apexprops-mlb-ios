import os
for root, _, files in os.walk('backend'):
    if 'locks' in root: continue
    for f in files:
        if f.endswith('.py'):
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fh:
                    for i, line in enumerate(fh):
                        if '"message"' in line and 'str(' in line:
                            print(f'{root}/{f}:{i+1}: {line.strip()}')
            except: pass

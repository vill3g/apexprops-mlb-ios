import os
for root, _, files in os.walk('backend'):
    for f in files:
        if f.endswith('.py'):
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fh:
                    for i, line in enumerate(fh):
                        if "'status': 'error'" in line or '"status": "error"' in line:
                            print(f'{root}/{f}:{i+1}: {line.strip()}')
            except: pass

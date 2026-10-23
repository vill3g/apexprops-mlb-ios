import os
import re
for root, _, files in os.walk('backend'):
    if 'locks' in root: continue
    for f in files:
        if f.endswith('.py'):
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fh:
                    code = fh.read()
                    if '"status"' in code and '"message"' in code:
                        print(f'MATCH in {root}/{f}')
            except: pass

# -*- coding: utf-8 -*-
"""Final comprehensive scan for encoding issues across all frontend files."""
import os
import re

base = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static'
problems = []

for root, dirs, files in os.walk(base):
    for fname in files:
        if not fname.endswith(('.html', '.js', '.css')):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except:
            continue
            
        for i, line in enumerate(lines, 1):
            # Check for U+FFFD replacement character
            if '\ufffd' in line:
                problems.append((fname, i, 'REPL_CHAR', line.strip()[:120]))
            
            # Check for ?? that are NOT JS nullish coalescing
            for m in re.finditer(r'\?\?(?!\?)', line):
                pos = m.start()
                before = line[max(0, pos-2):pos]
                after = line[pos+2:pos+4]
                # Nullish coalescing has spaces/operators around it
                if re.match(r'.*[\w\)\]\.] $', before + ' ') and re.match(r'^ [\w\'"`\[\(]', ' ' + after):
                    continue
                # Skip if in a ternary/nullish context
                ctx = line[max(0, pos-3):min(len(line), pos+5)]
                if ' ?? ' in ctx:
                    continue
                problems.append((fname, i, 'DOUBLE_Q', line.strip()[:120]))
                break

            # Check for isolated ? that look like broken emojis in HTML content
            # (not in JS code, URLs, or ternary operators)
            if fname.endswith('.html'):
                # Pattern: >?< or >? WORD in HTML tags
                for m in re.finditer(r'>\?(?:\s+[A-Z]|<)', line):
                    problems.append((fname, i, 'SINGLE_Q', line.strip()[:120]))
                    break

# Also check backend Python source
py_base = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer'
for fname in os.listdir(py_base):
    if not fname.endswith('.py'):
        continue
    fpath = os.path.join(py_base, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if '??' in line and 'Prediction' in line:
                problems.append((fname, i, 'PY_BROKEN', line.strip()[:120]))

if problems:
    print(f'Found {len(problems)} remaining issues:')
    for fname, line, kind, text in problems:
        print(f'  {fname}:{line} [{kind}] {text}')
else:
    print('ALL CLEAR - No encoding issues found anywhere!')

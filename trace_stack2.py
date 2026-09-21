with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
scripts = list(re.finditer(r'<script>(.*?)</script>', text, flags=re.DOTALL))
s2 = scripts[2].group(1)

state = 'CODE'
i = 0
line_idx = 1
stack = 0

lines = s2.split('\n')

while i < len(s2):
    c = s2[i]
    if c == '\n': 
        if stack == 1 and lines[line_idx-1].strip() == '}':
            print(f"Stack is 1 after line {line_idx}: {lines[line_idx-1].strip()}")
        line_idx += 1
    
    if state == 'CODE':
        if c == '"': state = 'DQUOTE'
        elif c == "'": state = 'SQUOTE'
        elif c == '': state = 'TQUOTE'
        elif c == '/' and i+1 < len(s2) and s2[i+1] == '/':
            state = 'LINE_COMMENT'
            i += 1
        elif c == '/' and i+1 < len(s2) and s2[i+1] == '*':
            state = 'BLOCK_COMMENT'
            i += 1
        elif c == '{': stack += 1
        elif c == '}': stack -= 1
    elif state == 'DQUOTE':
        if c == '\\': i += 1
        elif c == '"': state = 'CODE'
    elif state == 'SQUOTE':
        if c == '\\': i += 1
        elif c == "'": state = 'CODE'
    elif state == 'TQUOTE':
        if c == '\\': i += 1
        elif c == '': state = 'CODE'
    elif state == 'LINE_COMMENT':
        if c == '\n': state = 'CODE'
    elif state == 'BLOCK_COMMENT':
        if c == '*' and i+1 < len(s2) and s2[i+1] == '/':
            state = 'CODE'
            i += 1
    i += 1

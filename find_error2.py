with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import json
# I will use a simple state machine to strip strings and comments, then count braces
cleaned = []
state = 'CODE'
i = 0
while i < len(text):
    c = text[i]
    if state == 'CODE':
        if c == '"': state = 'DQUOTE'
        elif c == "'": state = 'SQUOTE'
        elif c == '': state = 'TQUOTE'
        elif c == '/' and i+1 < len(text) and text[i+1] == '/':
            state = 'LINE_COMMENT'
            i += 1
        elif c == '/' and i+1 < len(text) and text[i+1] == '*':
            state = 'BLOCK_COMMENT'
            i += 1
        else:
            cleaned.append(c)
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
        if c == '\n':
            state = 'CODE'
            cleaned.append(c)
    elif state == 'BLOCK_COMMENT':
        if c == '*' and i+1 < len(text) and text[i+1] == '/':
            state = 'CODE'
            i += 1
    i += 1

cleaned_text = ''.join(cleaned)
open_b = cleaned_text.count('{')
close_b = cleaned_text.count('}')
print(f"Total {{ : {open_b}")
print(f"Total }} : {close_b}")

if open_b != close_b:
    print("Mismatch!")
    # Find where it gets negative or where it ends
    stack = []
    lines = cleaned_text.split('\n')
    for line_idx, line in enumerate(lines):
        for char in line:
            if char == '{': stack.append(line_idx)
            elif char == '}':
                if len(stack) > 0: stack.pop()
                else: print(f"Unmatched }} at line {line_idx+1}: {line}")

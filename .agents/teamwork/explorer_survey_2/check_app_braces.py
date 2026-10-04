with open('static/js/app.js', encoding='utf-8') as f:
    text = f.read()

cleaned = []
in_str = False
str_char = ''
in_line_comment = False
in_block_comment = False
i = 0
n = len(text)
while i < n:
    c = text[i]
    if in_line_comment:
        if c == '\n':
            in_line_comment = False
            cleaned.append(c)
        else:
            cleaned.append(' ')
        i += 1
        continue
    if in_block_comment:
        if c == '*' and i + 1 < n and text[i+1] == '/':
            in_block_comment = False
            cleaned.append('  ')
            i += 2
        else:
            cleaned.append(' ')
            i += 1
        continue
    if in_str:
        if c == '\\':
            cleaned.append('  ')
            i += 2
            continue
        if c == str_char:
            in_str = False
        cleaned.append(' ')
        i += 1
        continue
    if c == '/' and i + 1 < n and text[i+1] == '/':
        in_line_comment = True
        cleaned.append('  ')
        i += 2
        continue
    if c == '/' and i + 1 < n and text[i+1] == '*':
        in_block_comment = True
        cleaned.append('  ')
        i += 2
        continue
    if c in ('"', "'", '`'):
        in_str = True
        str_char = c
        cleaned.append(' ')
        i += 1
        continue
    cleaned.append(c)
    i += 1

cleaned_str = ''.join(cleaned)
stack = []
lines = cleaned_str.split('\n')
for l_idx, line in enumerate(lines):
    for c_idx, ch in enumerate(line):
        if ch == '{':
            stack.append((l_idx + 1, c_idx + 1))
        elif ch == '}':
            if stack:
                stack.pop()
            else:
                print(f"Extra closing brace at L{l_idx+1}:C{c_idx+1}")

print('Open braces at end of app.js:', len(stack))
raw_lines = text.splitlines()
for l, c in stack:
    print(f'  L{l}:C{c}: {raw_lines[l-1].strip()[:80]}')

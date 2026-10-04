import re

with open('static/saas_dashboard.html', encoding='utf-8') as f:
    lines = f.readlines()

stack = []
for i in range(5287, 6100):
    line = lines[i]
    tokens = re.finditer(r'(<div\b[^>]*>|</div>)', line)
    for tok in tokens:
        tag_str = tok.group(1)
        if tag_str.startswith('<div'):
            id_m = re.search(r'id=["\']([^"\']*)["\']', tag_str)
            cls_m = re.search(r'class=["\']([^"\']*)["\']', tag_str)
            ident = id_m.group(1) if id_m else (cls_m.group(1)[:30] if cls_m else 'div')
            stack.append((ident, i+1))
        else:
            if stack:
                popped = stack.pop()
                if i+1 >= 6090:
                    print(f"Line {i+1}: popped {popped[0]} (opened at {popped[1]})")
            else:
                print(f"Line {i+1}: extra </div>")

print("\nRemaining unclosed:")
for item in stack:
    print(f"  {item[0]} from line {item[1]}")

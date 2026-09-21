with open('static/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'let allPitcherProps = [];' in line:
        pass # I deleted this

stack = []
in_script = False
for i, line in enumerate(lines):
    if '<script>' in line:
        in_script = True
    if '</script>' in line:
        in_script = False
        if len(stack) != 0:
            print(f"End of script {i}, stack not empty: {len(stack)}")
            stack = []
            
    if in_script:
        # Very naive parser
        # remove strings
        import re
        line_clean = re.sub(r'\".*?\"', '', line)
        line_clean = re.sub(r'\'.*?\'', '', line_clean)
        line_clean = re.sub(r'\.*?\', '', line_clean)
        line_clean = re.sub(r'//.*', '', line_clean)
        
        for char in line_clean:
            if char == '{':
                stack.append(i)
            elif char == '}':
                if len(stack) > 0:
                    stack.pop()
                else:
                    print(f"Unmatched }} at line {i+1}: {line.strip()}")

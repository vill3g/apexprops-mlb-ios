import sys

def move_imports(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    imports_to_add = []
    in_try = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('try:'):
            in_try = True
        elif stripped.startswith('except') or stripped == 'except:':
            in_try = False
        
        # Check if line is an import and it's indented (i.e. inside function)
        if (stripped.startswith('import ') or stripped.startswith('from ')) and (line.startswith('    ') or line.startswith('\t')):
            # Only move if not in try block (like PIL)
            if not in_try and 'PIL' not in line:
                if stripped not in imports_to_add:
                    imports_to_add.append(stripped)
                continue # Skip adding to new_lines
        new_lines.append(line)
    
    if imports_to_add:
        # Find where to put them. Right after the first bunch of imports.
        insert_idx = 0
        for i, line in enumerate(new_lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_idx = i + 1
        
        # add them
        for imp in reversed(imports_to_add):
            new_lines.insert(insert_idx, imp + '\n')
            
        with open(filename, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

for f in ['backend/routes/engine.py', 'backend/routes/admin.py', 'backend/routes/trading.py', 'backend/routes/ui.py', 'backend/routes/scalp.py', 'backend/auth/routes.py', 'backend/main.py']:
    move_imports(f)

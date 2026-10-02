import re
import os

def fix_bare_excepts(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Replace bare except:
    def replace_bare(m):
        indent = m.group(1)
        return f"{indent}except Exception as e:\n{indent}    logger.warning(f\"Error: {{e}}\")\n"
    content = re.sub(r'^(\s+)except\s*:\s*\n', replace_bare, content, flags=re.MULTILINE)
    
    # 2. Replace except Exception:
    content = re.sub(r'^(\s+)except Exception:\s*\n', r'\1except Exception as e:\n\1    logger.warning(f"Error: {e}")\n', content, flags=re.MULTILINE)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

def fix_fstrings(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    # Simple replacement of f"..." to "..." where there are no brackets.
    # This is slightly risky but let's do it carefully.
    def repl(m):
        s = m.group(1)
        if '{' not in s and '}' not in s:
            return f'"{s}"'
        return m.group(0)
    
    # regex for f"..." or f'...'
    content = re.sub(r'f"([^"\{}]+)"', repl, content)
    content = re.sub(r"f'([^'\{}]+)'", repl, content)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

for f in ['backend/routes/engine.py', 'backend/routes/admin.py', 'backend/routes/trading.py', 'backend/routes/ui.py', 'backend/routes/scalp.py', 'backend/auth/routes.py', 'backend/main.py']:
    fix_bare_excepts(f)
    fix_fstrings(f)

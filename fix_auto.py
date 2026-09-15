import os
import re

def fix():
    file_path = 'backend/btc/auto_executor.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # The block to remove:
    pattern = r'# If static rules returned PASS / CHOP.*?except Exception as e:\s*logger\.error\(f"\[AutoExecutor\] ML fallback error: \{e\}"\)'

    content = re.sub(pattern, '', content, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix()
    print("Removed fallback block from auto_executor.py")

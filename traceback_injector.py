import ast
import traceback

with open('backend/routes/engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Let's just find the catch block in api_sports_events and add traceback.print_exc()!
import re

new_code = re.sub(
    r'(except Exception as e:\s+logger\.debug\(f"Could not fetch picks for events: \{e\}"\))',
    r'\1\n        import traceback; traceback.print_exc()',
    code
)

new_code = re.sub(
    r'(logger\.error\(f"Error in sports events API: \{e\}"\))',
    r'\1\n        import traceback; traceback.print_exc()',
    new_code
)

with open('backend/routes/engine.py', 'w', encoding='utf-8') as f:
    f.write(new_code)

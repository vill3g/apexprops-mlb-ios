# -*- coding: utf-8 -*-
"""Fix the remaining ?? and stray cent signs in dashboard.js."""

path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

GOLD = '\U0001F947'    # gold medal
SILVER = '\U0001F948'  # silver medal
BRONZE = '\U0001F949'  # bronze medal
TEST_TUBE = '\U0001F9EA'  # test tube

# Fix rank badges
content = content.replace(
    '0.5)]">\\uD83E\\uDD47</div>',
    '0.5)]">' + GOLD + '</div>'
)
content = content.replace(
    '0.4)]">??</div>',
    '0.4)]">' + SILVER + '</div>'
)
content = content.replace(
    '0.3)]">??</div>',
    '0.3)]">' + BRONZE + '</div>'
)

# Fix PAPER MODE hint
content = content.replace(
    '"?? <span',
    '"' + TEST_TUBE + ' <span'
)

# Fix stray cent signs in CSS class names
import re
# Pattern: a digit followed by cent sign followed by a digit (e.g. "95¢0" -> "950")
content = re.sub(r'(\d)\u00a2(\d)', r'\1\2', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

import os
ret = os.system(f'node -c "{path}"')
print(f"Syntax check: {'OK' if ret == 0 else 'FAIL'}")
print("Remaining ?? and cent fixes applied")

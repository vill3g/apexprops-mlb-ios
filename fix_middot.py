# -*- coding: utf-8 -*-
"""Fix middle-dot corruption in dashboard.js and restore legitimate uses."""
import os
import re

path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Step 1: Replace ALL middle dots with spaces (they were ALL introduced by corruption)
content = content.replace('\u00b7', ' ')

# Step 2: Restore legitimate middle dots in JS string patterns.
# The original code used middle dots as UI separators in template literals:
#   parts.join(' \u00b7 ')       ->  became parts.join('   ')
#   [style, src].join(' \u00b7 ')
# These show up as:  ' \u00b7 '  in join() calls and template literals
# We need to find patterns like .join('   ') and restore to .join(' \u00b7 ')
content = content.replace(".join('   ')", ".join(' \u00b7 ')")
content = content.replace('.join("   ")', '.join(" \u00b7 ")')

# Also in template literal interpolations like:
#   `${style}   ${src}`  should be  `${style} \u00b7 ${src}`
# This pattern appears in _telemetryFromSignal and other places
content = re.sub(
    r'\$\{([^}]+)\}\s{3}\$\{([^}]+)\}',
    lambda m: '${' + m.group(1) + '} \u00b7 ${' + m.group(2) + '}',
    content
)

# Fix specific UI separator patterns that use middot between parts
# e.g.:  parts.push(Number(s.prob_percent).toFixed(1) + '%')
# Pattern in priceYes/priceNo display:  `56 \u00a2`  (cent sign, not middot - leave alone)
# The `X   Y` triple-space pattern in direct string concatenations
content = content.replace("'edge '", "'edge '")  # no-op sanity

# Step 3: Write
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("dashboard.js: middle dots replaced with spaces")
ret = os.system(f'node -c "{path}"')
print(f"Syntax check: {'OK' if ret == 0 else 'FAIL'}")

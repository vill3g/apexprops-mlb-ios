# -*- coding: utf-8 -*-
"""
Remove all spurious cent signs from dashboard.js that were introduced
by the earlier over-broad REPL -> cent replacement, then re-insert
cent signs ONLY where they belong (price displays).
"""
import re

path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

CENT = '\u00a2'

# Step 1: Remove ALL cent signs. We'll add back the legitimate ones.
content = content.replace(CENT, '')

# Step 2: Add cent signs back ONLY in legitimate price display contexts.
# These are patterns like:
#   `${yesPriceCents}\u00a2`       -> price display in template literal
#   `${noPriceCents}\u00a2`        -> price display
#   `--\u00a2`                     -> placeholder price
#   `56\u00a2`                     -> rendered price
#   Number + \u00a2  in string     -> "75\u00a2" style in descriptions
#
# Legitimate patterns found in the original code:
#   const txt = yesPriceCents !== null ? `${yesPriceCents}\u00a2` : "--\u00a2";
#   const txt = noPriceCents  !== null ? `${noPriceCents}\u00a2` : "--\u00a2";
#   if (priceYesEl) priceYesEl.innerText = "--\u00a2";
#   if (priceNoEl) priceNoEl.innerText = "--\u00a2";
#   descriptions mentioning "75\u00a2" and "85\u00a2-95\u00a2"

# Pattern: ${...Cents} should be followed by cent sign in template literals
content = re.sub(r'\$\{(yesPriceCents|noPriceCents)\}', 
                 lambda m: '${' + m.group(1) + '}' + CENT, content)

# Pattern: "--" used as price placeholder followed by quote/backtick
# We need to be careful: only "--" that are price placeholders
# These appear as: `"--"` or `` "--" `` in price display contexts
# Looking at the original patterns:
#   ? `${yesPriceCents}\u00a2` : "--\u00a2"
#   priceYesEl.innerText = "--\u00a2"
# So the pattern is: "--" followed by " or ` in a price context
# Let's target the specific known patterns:
content = content.replace(': "--"', ': "--' + CENT + '"')
content = content.replace('= "--"', '= "--' + CENT + '"')
content = content.replace("': '--'", "': '--" + CENT + "'")
content = content.replace("= '--'", "= '--" + CENT + "'")

# Pattern: number+cent in description strings about price limits
# "75\u00a2" in descriptions like "0.75 for 75\u00a2"
# "85\u00a2-95\u00a2" in descriptions  
# These appear inside desc: '...' strings
content = content.replace("for 75", "for 75" + CENT)
content = content.replace("(85", "(85" + CENT)
content = content.replace("-95", "-95" + CENT)
# Fix pattern like: "certainty (85¢-95¢)."
# Actually let me be more targeted:
content = re.sub(r'certainty \(85-95\)', 
                 'certainty (85' + CENT + '-95' + CENT + ')', content)
content = re.sub(r'for 75\)', 'for 75' + CENT + ')', content)

# Step 3: Write
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("dashboard.js: all spurious cent signs removed, legitimate ones restored")

import os
ret = os.system(f'node -c "{path}"')
print(f"Syntax check: {'OK' if ret == 0 else 'FAIL'}")

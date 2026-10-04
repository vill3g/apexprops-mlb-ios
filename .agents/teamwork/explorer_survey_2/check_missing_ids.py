import re

with open('static/saas_dashboard.html', encoding='utf-8') as f:
    html_content = f.read()

# Collect all IDs present in saas_dashboard.html
dom_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html_content))
print(f"Total unique IDs in saas_dashboard.html: {len(dom_ids)}")

def check_file_for_missing_ids(filepath):
    print(f"\n==========================================")
    print(f"Checking missing DOM IDs referenced in: {filepath}")
    print(f"==========================================")
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # Look for getElementById('...')
    matches = re.finditer(r'getElementById\s*\(\s*["\']([^"\']+)["\']\s*\)', content)
    missing = {}
    for m in matches:
        el_id = m.group(1)
        line_no = content[:m.start()].count('\n') + 1
        # Check snippet around the call to see if it does safe navigation (if (el) ...)
        snippet = content[m.start():m.start() + 150].replace('\n', ' ')
        if el_id not in dom_ids:
            if el_id not in missing:
                missing[el_id] = []
            missing[el_id].append((line_no, snippet))

    print(f"Total referenced IDs NOT present in saas_dashboard.html: {len(missing)}")
    for el_id, occurrences in sorted(missing.items()):
        print(f"\nMissing ID: '{el_id}' (used {len(occurrences)} times):")
        for line_no, snip in occurrences[:3]:
            # check if followed by direct property access without null check
            print(f"  Line {line_no}: {snip[:80]}")

check_file_for_missing_ids('static/js/app.js')
check_file_for_missing_ids('static/saas_dashboard.html')

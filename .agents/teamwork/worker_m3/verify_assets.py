import os
import re
import json

REPO_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"
STATIC_DIR = os.path.join(REPO_ROOT, "static")

all_refs = []

for root, dirs, files in os.walk(STATIC_DIR):
    for fname in files:
        if fname.endswith(('.html', '.json', '.js', '.css')):
            fpath = os.path.join(root, fname)
            rel_fpath = os.path.relpath(fpath, STATIC_DIR)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Find src, href, url(...)
            matches = re.findall(r'(?:src|href)=["\']([^"\']+)["\']', content)
            matches += re.findall(r'url\(["\']?([^"\'()]+)["\']?\)', content)
            if fname == 'manifest.json':
                try:
                    m = json.loads(content)
                    for ic in m.get('icons', []):
                        matches.append(ic.get('src', ''))
                except Exception:
                    pass
            for m in matches:
                if m.startswith(('http://', 'https://', 'data:', 'mailto:', 'tel:', 'javascript:', '#')):
                    continue
                if '{' in m or '}' in m or '$' in m:
                    continue
                # Skip external domain like moneyprinter.ngrok.app
                all_refs.append((rel_fpath, m))

missing = []
for source, ref in all_refs:
    clean_ref = ref.split('?')[0].split('#')[0]
    if not clean_ref:
        continue
    if clean_ref.startswith('/static/'):
        disk_path = os.path.join(STATIC_DIR, clean_ref[len('/static/'):].replace('/', os.sep))
    elif clean_ref.startswith('/'):
        # could be an API route like /api/... or /admin/mobile or root / or a static file
        if clean_ref.startswith(('/api/', '/admin', '/login', '/trades', '/saas_dashboard', '/dashboard')):
            continue
        disk_path = os.path.join(STATIC_DIR, clean_ref.lstrip('/').replace('/', os.sep))
    else:
        source_dir = os.path.dirname(os.path.join(STATIC_DIR, source))
        disk_path = os.path.normpath(os.path.join(source_dir, clean_ref.replace('/', os.sep)))
    
    if not os.path.exists(disk_path):
        missing.append((source, ref, disk_path))

print(f"Total internal refs checked: {len(all_refs)}")
unique_missing = sorted(set(missing))
print(f"Missing files ({len(unique_missing)}):")
for src, ref, disk_path in unique_missing:
    print(f"  In {src}: {ref} -> {disk_path}")

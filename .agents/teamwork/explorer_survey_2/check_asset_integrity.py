import os
import re

STATIC_DIR = os.path.abspath('static')

def resolve_asset_path(ref, html_file):
    # Remove query string or hash
    clean_ref = ref.split('?')[0].split('#')[0]
    
    # Ignore absolute URLs, data URIs, javascript:, #, tel:, mailto:
    if clean_ref.startswith(('http://', 'https://', 'data:', 'javascript:', '#', 'tel:', 'mailto:', '//')):
        return None
    
    # If starts with /static/
    if clean_ref.startswith('/static/'):
        target = os.path.join(STATIC_DIR, clean_ref[len('/static/'):].replace('/', os.sep))
    elif clean_ref.startswith('/'):
        # Could be root relative (e.g. /favicon.ico)
        target = os.path.join(STATIC_DIR, clean_ref[1:].replace('/', os.sep))
    elif clean_ref.startswith('./'):
        target = os.path.join(os.path.dirname(html_file), clean_ref[2:].replace('/', os.sep))
    else:
        target = os.path.join(os.path.dirname(html_file), clean_ref.replace('/', os.sep))
    
    return os.path.normpath(target)

files_to_check = [
    'static/saas_dashboard.html',
    'static/login.html',
    'static/trades.html',
    'static/admin_mobile.html',
    'static/index.html',
    'static/js/app.js',
    'static/js/admin_users.js'
]

print("==========================================")
print("STATIC ASSET INTEGRITY SCAN")
print("==========================================")

missing_assets = []
checked_count = 0

for filepath in files_to_check:
    abs_fp = os.path.abspath(filepath)
    if not os.path.exists(abs_fp):
        continue
    
    with open(abs_fp, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    # Extract src="...", href="...", url('...'), etc.
    patterns = [
        r'(?:src|href)=["\']([^"\']+)["\']',
        r'url\(["\']?([^"\'\)]+)["\']?\)'
    ]
    
    for pat in patterns:
        for m in re.finditer(pat, content):
            ref = m.group(1).strip()
            # Skip API endpoints or html pages if checking static media/css/js
            resolved = resolve_asset_path(ref, abs_fp)
            if resolved is None:
                continue
            
            # Filter to static files (extensions: .png, .jpg, .jpeg, .gif, .webp, .svg, .ico, .js, .css, .json, .mp3, .wav)
            ext = os.path.splitext(resolved)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.js', '.css', '.json', '.mp3', '.wav']:
                checked_count += 1
                if not os.path.exists(resolved):
                    line_no = content[:m.start()].count('\n') + 1
                    missing_assets.append((filepath, line_no, ref, resolved))

print(f"Total asset references checked: {checked_count}")
print(f"Missing / 404 assets found: {len(missing_assets)}")
for orig_file, l, ref, resolved in missing_assets:
    print(f"\n[404 NOT FOUND] In {orig_file} at line {l}:")
    print(f"  Referenced: {ref}")
    print(f"  Resolved to: {resolved}")

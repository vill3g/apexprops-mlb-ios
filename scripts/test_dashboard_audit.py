import re
from bs4 import BeautifulSoup

def audit():
    with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    # 1. Duplicate IDs
    ids = [el.get('id') for el in soup.find_all(True) if el.get('id')]
    dups = set([x for x in ids if ids.count(x) > 1])
    print(f"[AUDIT] Duplicate IDs in saas_dashboard.html: {sorted(dups)}")

    # 2. Check broken tailwind classes
    broken = []
    for line_idx, line in enumerate(html.splitlines(), 1):
        if 'backdrop- ' in line or 'blur- ' in line:
            broken.append((line_idx, line.strip()))
    print(f"[AUDIT] Broken classes found: {broken}")

    # 3. Check nav-live-pnl-container
    pnl_container = soup.find(id='nav-live-pnl-container')
    if pnl_container:
        print(f"[AUDIT] nav-live-pnl-container class: {pnl_container.get('class')}")
    else:
        print("[AUDIT] nav-live-pnl-container NOT found!")

    # 4. Check profileDropdown
    dd = soup.find(id='profileDropdown')
    if dd:
        print(f"[AUDIT] profileDropdown class: {dd.get('class')} | style: {dd.get('style')}")

if __name__ == '__main__':
    audit()

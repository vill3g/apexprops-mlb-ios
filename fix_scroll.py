with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

old_str = 'class="bg-kalshi-dark border-t border-kalshi-border w-full rounded-t-2xl p-5 pb-10 shadow-[0_-10px_30px_rgba(0,0,0,0.5)] transform transition-transform translate-y-full" id="settings-panel"'
new_str = 'class="bg-kalshi-dark border-t border-kalshi-border w-full rounded-t-2xl p-5 pb-10 shadow-[0_-10px_30px_rgba(0,0,0,0.5)] transform transition-transform translate-y-full max-h-[90vh] overflow-y-auto overscroll-contain" id="settings-panel"'

if old_str in c:
    c = c.replace(old_str, new_str)
    with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Successfully added scroll properties to settings-panel")
else:
    print("Could not find the exact string. Let's try regex.")
    import re
    c = re.sub(r'class="bg-kalshi-dark(.*?)translate-y-full"\s+id="settings-panel"', r'class="bg-kalshi-dark\1translate-y-full max-h-[90vh] overflow-y-auto overscroll-contain" id="settings-panel"', c)
    with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Applied via regex.")

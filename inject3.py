import re

html_path = r'C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

target = r'''    if (typeof syncSoundSettingsUI === 'function') {
        syncSoundSettingsUI();
    }'''

injection = target + '''
    if (typeof refreshWalletBalances === 'function') {
        refreshWalletBalances();
    }'''

if target in html:
    new_html = html.replace(target, injection)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print("Injected into openSettings successfully.")
else:
    print("Could not find openSettings injection point.")

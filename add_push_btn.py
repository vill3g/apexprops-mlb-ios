import re

path = "static/saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    html = f.read()

btn_html = """
                    <div class="mt-4 pt-3 border-t border-kalshi-border/50 text-center">
                        <button onclick="enableWebPushNotifications()" class="w-full py-2 bg-kalshi-blue/20 hover:bg-kalshi-blue/30 border border-kalshi-blue/50 rounded-lg text-kalshi-blue font-bold text-[10px] uppercase tracking-widest transition-all">Enable iOS Push Notifications</button>
                        <div class="text-[8px] text-gray-500 mt-1.5">(Requires adding app to Home Screen on iOS 16.4+)</div>
                    </div>
"""

# Insert button after the two toggles in the Notifications Card
pattern = r'(<input type="checkbox" id="notify-market-trends"[\s\S]*?</div>\s*</label>\s*</div>)'
replacement = r'\1' + btn_html
html = re.sub(pattern, replacement, html)

with open(path, "w", encoding="utf-8") as f:
    f.write(html)

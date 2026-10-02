import re

html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Remove the refresh button
refresh_btn_pattern = r'<button onclick="location\.reload\(\)" title="Reload" class="w-7 h-7 flex items-center justify-center bg-gray-800 text-gray-300 rounded-md active:scale-95 transition-all">\s*<svg.*?</svg>\s*</button>'
html = re.sub(refresh_btn_pattern, "", html, flags=re.DOTALL)

# Add custom pull-to-refresh spinner element just after <body>
ptr_html = """
    <!-- Custom Pull to Refresh Indicator -->
    <div id="ptr-indicator" class="fixed top-0 left-0 right-0 h-16 flex items-center justify-center bg-transparent z-[100] transition-transform duration-200" style="transform: translateY(-100%); pointer-events: none;">
        <div class="bg-gray-900 border border-kalshi-border rounded-full p-2 shadow-lg flex items-center justify-center">
            <svg id="ptr-spinner" class="w-5 h-5 text-kalshi-blue transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
        </div>
    </div>
"""

body_pattern = r'(<body[^>]*>)'
html = re.sub(body_pattern, r'\1' + ptr_html, html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Removed refresh button and added PTR HTML!")

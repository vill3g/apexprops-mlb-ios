import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# The support button to remove
support_btn = """<button onclick="openTicketModal()" id="btn-header-support" title="Report Issue" class="w-7 h-7 flex items-center justify-center bg-gray-900 hover:bg-gray-800 text-gray-400 hover:text-white rounded-md active:scale-95 transition-all border border-gray-800 ml-1">
<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
</button>
"""
if support_btn in html:
    html = html.replace(support_btn, "")
else:
    print("WARNING: Support button not found in header!")

# The settings bottom section to replace
settings_bottom = """            <!-- Bottom Buttons -->
            <div class="pt-2 pb-6 space-y-3">
                <button onclick="closeSettingsPage()" class="w-full py-3 bg-kalshi-blue/15 hover:bg-kalshi-blue/25 border border-kalshi-blue/40 text-kalshi-blue font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 flex items-center justify-center gap-2 shadow-sm">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                    Done & Return to Dashboard
                </button>"""

new_settings_bottom = """            <!-- Bottom Buttons -->
            <div class="pt-2 pb-6 space-y-3">
                <button onclick="openTicketModal()" class="w-full py-3 bg-gray-800/40 hover:bg-gray-800/60 border border-gray-700/80 text-gray-300 font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 flex items-center justify-center gap-2 shadow-sm mb-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Report an Issue
                </button>
                <button onclick="closeSettingsPage()" class="w-full py-3 bg-kalshi-blue/15 hover:bg-kalshi-blue/25 border border-kalshi-blue/40 text-kalshi-blue font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 flex items-center justify-center gap-2 shadow-sm">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                    Done & Return to Dashboard
                </button>"""

if settings_bottom in html:
    html = html.replace(settings_bottom, new_settings_bottom)
    print("Support button successfully moved to settings.")
else:
    print("WARNING: Settings bottom not found!")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)

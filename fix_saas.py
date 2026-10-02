import os

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Extract lines 760 to 793 (0-indexed 759 to 793)
# But we should rely on string finding
content = "".join(lines)
start_str = "            <!-- Notifications & Alerts Card -->"
end_str = "            <!-- Model & Training Controls Card -->"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

notifications_block = content[start_idx:end_idx]

# Modify the notifications block to be collapsed details
new_notifications_block = notifications_block.replace(
    '''<div class="bg-black/40 px-4 py-3 border-b border-kalshi-border flex items-center gap-2 text-kalshi-blue text-[10px] sm:text-xs font-bold uppercase tracking-widest">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
                    Notifications & Alerts
                </div>''',
    '''<details class="group">
                    <summary class="bg-black/40 px-4 py-3 cursor-pointer outline-none flex justify-between items-center list-none [&::-webkit-details-marker]:hidden border-b border-kalshi-border">
                        <div class="flex items-center gap-2 text-gray-400 font-bold uppercase tracking-widest text-[10px] group-open:text-kalshi-blue transition-colors">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
                            Notifications & Alerts
                        </div>
                        <svg class="w-4 h-4 text-gray-500 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </summary>'''
)

new_notifications_block = new_notifications_block.replace('                </div>\n            </div>\n', '                </div>\n                </details>\n            </div>\n')

content_without_notif = content[:start_idx] + content[end_idx:]

# Insert just above API Settings Card
api_start_str = "            <!-- API Settings Card -->"
api_idx = content_without_notif.find(api_start_str)

final_content = content_without_notif[:api_idx] + new_notifications_block + content_without_notif[api_idx:]

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(final_content)
print("Done")

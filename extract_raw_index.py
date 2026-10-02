import json
import os
import re

brains_dir = r'C:\Users\Vill3\.gemini\antigravity\brain'
folders = [f for f in os.listdir(brains_dir) if os.path.isdir(os.path.join(brains_dir, f))]
folders.sort(key=lambda x: os.path.getmtime(os.path.join(brains_dir, x)), reverse=True)

recovered_count = 0
for folder in folders:
    log_path = os.path.join(brains_dir, folder, '.system_generated', 'logs', 'transcript_full.jsonl')
    if not os.path.exists(log_path):
        continue
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except:
                    continue
                if entry.get('type') == 'TOOL_RESPONSE' and 'content' in entry:
                    content = entry['content']
                    if 'static/index.html' in content or 'static\\index.html' in content:
                        # view_file outputs lines like "1 | <!DOCTYPE html>"
                        # or just raw text depending on the tool implementation
                        if '<html' in content and 'admin_users' in content:
                            # It's an HTML file with admin_users!
                            with open(f'recovered_admin_index_{folder[:8]}.html', 'w', encoding='utf-8') as out:
                                out.write(content)
                            print(f"Recovered an index with admin_users from {folder}!")
                            recovered_count += 1
    except:
        pass

print(f"Total recovered: {recovered_count}")

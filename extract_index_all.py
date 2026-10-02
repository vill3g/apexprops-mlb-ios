import json
import os
import re

brains_dir = r'C:\Users\Vill3\.gemini\antigravity\brain'
folders = [f for f in os.listdir(brains_dir) if os.path.isdir(os.path.join(brains_dir, f))]

# Sort by last modified
folders.sort(key=lambda x: os.path.getmtime(os.path.join(brains_dir, x)), reverse=True)

recovered = False
for folder in folders[:10]:
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
                
                # Check if this is a view_file response
                if entry.get('type') == 'TOOL_RESPONSE' and 'content' in entry:
                    content = entry['content']
                    if 'File Path: `file:///C:/Users/Vill3/Desktop/kalshi-ai-trader/static/index.html`' in content:
                        m = re.search(r'```[a-z]*\n(.*)```', content, re.DOTALL)
                        if m:
                            code = m.group(1)
                            # Only keep it if it's substantial (e.g. > 10000 bytes)
                            if len(code) > 10000:
                                with open(f'recovered_index_{folder}.html', 'w', encoding='utf-8') as out:
                                    out.write(code)
                                print(f"Recovered index.html from {folder}! Size: {len(code)}")
                                recovered = True
    except Exception as e:
        print("Error reading", folder, e)

if not recovered:
    print("Could not recover index.html from any transcript.")

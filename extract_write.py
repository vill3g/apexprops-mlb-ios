import json
import os
import re

brains_dir = r'C:\Users\Vill3\.gemini\antigravity\brain'
folders = [f for f in os.listdir(brains_dir) if os.path.isdir(os.path.join(brains_dir, f))]
folders.sort(key=lambda x: os.path.getmtime(os.path.join(brains_dir, x)), reverse=True)

for folder in folders[:15]:
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
                
                # Check if this is a tool call
                if 'tool_calls' in entry:
                    for tc in entry['tool_calls']:
                        args = tc.get('arguments', {})
                        if tc['name'] == 'write_to_file':
                            target = args.get('TargetFile', '')
                            if 'index.html' in target or 'saas_dashboard.html' in target:
                                content = args.get('CodeContent', '')
                                if len(content) > 10000: # Only save if it's the whole file
                                    name = "recovered_" + os.path.basename(target)
                                    with open(f'{name}_{folder}.html', 'w', encoding='utf-8') as out:
                                        out.write(content)
                                    print(f"Recovered {target} from {folder}! Size: {len(content)}")
                        elif tc['name'] == 'replace_file_content':
                            pass # We can't easily reconstruct the whole file from a replace
    except Exception as e:
        print("Error reading", folder, e)

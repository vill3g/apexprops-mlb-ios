import json
import os

brains_dir = r'C:\Users\Vill3\.gemini\antigravity\brain'
folders = [f for f in os.listdir(brains_dir) if os.path.isdir(os.path.join(brains_dir, f))]
folders.sort(key=lambda x: os.path.getmtime(os.path.join(brains_dir, x)), reverse=True)

for folder in folders[:20]:
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
                if 'tool_calls' in entry:
                    for tc in entry['tool_calls']:
                        args = tc.get('arguments', {})
                        if 'TargetFile' in args and 'index.html' in args['TargetFile']:
                            print(f"[{folder}] TOOL CALL:", tc['name'])
    except:
        pass

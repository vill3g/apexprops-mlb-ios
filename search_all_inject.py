import json
import os

brains_dir = r'C:\Users\Vill3\.gemini\antigravity\brain'
folders = [f for f in os.listdir(brains_dir) if os.path.isdir(os.path.join(brains_dir, f))]
folders.sort(key=lambda x: os.path.getmtime(os.path.join(brains_dir, x)), reverse=True)

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
                if 'tool_calls' in entry:
                    for call in entry['tool_calls']:
                        if call['name'] in ['write_to_file', 'replace_file_content']:
                            args = call.get('arguments', {})
                            if args.get('TargetFile', '').endswith('index.html'):
                                text = args.get('CodeContent', '') + args.get('ReplacementContent', '')
                                if 'admin_users.js' in text:
                                    print(f"Found it in {folder}!")
    except:
        pass

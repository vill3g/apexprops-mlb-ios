import json
import os

brains_dir = r'C:\Users\Vill3\.gemini\antigravity\brain'
folders = [f for f in os.listdir(brains_dir) if os.path.isdir(os.path.join(brains_dir, f))]
folders.sort(key=lambda x: os.path.getmtime(os.path.join(brains_dir, x)), reverse=True)

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
                if 'tool_calls' in entry:
                    for tc in entry['tool_calls']:
                        if tc['name'] == 'write_to_file':
                            args = tc.get('arguments', {})
                            if 'dashboard.js' in args.get('TargetFile', ''):
                                print(f"Found write_to_file dashboard.js in {folder}!")
                                with open('recovered_dashboard.js', 'w', encoding='utf-8') as out:
                                    out.write(args['CodeContent'])
    except:
        pass

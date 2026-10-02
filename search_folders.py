import json
import os

brains_dir = r'C:\Users\Vill3\.gemini\antigravity\brain'
folders = ["c9d9ff40-75bb-460f-8743-2d09c14d7f73", "d40b2869-c1a0-41fd-89f4-4481673cce27", "f9732238-5384-4f24-8075-ded12557e9eb"]

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
                        if call['name'] in ['write_to_file', 'replace_file_content', 'run_command']:
                            args = call.get('arguments', {})
                            if 'admin_users' in str(args):
                                print(f"[{folder}] Tool: {call['name']}")
                                if call['name'] == 'run_command':
                                    print(f"  Command: {args.get('CommandLine')[:100]}")
                                else:
                                    print(f"  Target: {args.get('TargetFile')}")
    except:
        pass

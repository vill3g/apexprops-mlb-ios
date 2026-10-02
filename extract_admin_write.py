import json
import os

log_path = r'C:\Users\Vill3\.gemini\antigravity\brain\d40b2869-c1a0-41fd-89f4-4481673cce27\.system_generated\logs\transcript_full.jsonl'

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
                        if 'admin_users' in str(args):
                            print(f"File: {args.get('TargetFile')}")
                            if 'index.html' in args.get('TargetFile', ''):
                                print(f"Index HTML edit found!")
                                with open('recovered_admin_index.txt', 'w', encoding='utf-8') as out:
                                    out.write(json.dumps(args, indent=2))
                                
except Exception as e:
    pass

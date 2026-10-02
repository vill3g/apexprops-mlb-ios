import json

log_path = r'C:\Users\Vill3\.gemini\antigravity\brain\fad92bba-4f6b-4714-873b-c9b313c28176\.system_generated\logs\transcript_full.jsonl'
found = False

try:
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
            except:
                continue
            
            if entry.get('type') == 'PLANNER_RESPONSE' and 'tool_calls' in entry:
                for call in entry['tool_calls']:
                    if call['name'] in ['write_to_file', 'replace_file_content']:
                        args = call.get('arguments', {})
                        if args.get('TargetFile', '').endswith('index.html'):
                            if 'admin_users.js' in args.get('CodeContent', '') or 'admin_users.js' in args.get('ReplacementContent', ''):
                                print(f"Found injection in {call['name']}!")
                                found = True
except Exception as e:
    pass

if not found:
    print("Not found in previous session.")

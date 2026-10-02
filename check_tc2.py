import json

log_path = r'C:\Users\Vill3\.gemini\antigravity\brain\8ca217a2-ad24-4ffb-ba07-1d83a4a0ab1a\.system_generated\logs\transcript_full.jsonl'
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
                    print("TOOL CALL:", tc['name'])
                    print("TargetFile:", args['TargetFile'])

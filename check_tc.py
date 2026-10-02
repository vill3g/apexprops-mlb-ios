import json
import re

log_path = r'C:\Users\Vill3\.gemini\antigravity\brain\fad92bba-4f6b-4714-873b-c9b313c28176\.system_generated\logs\transcript_full.jsonl'
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

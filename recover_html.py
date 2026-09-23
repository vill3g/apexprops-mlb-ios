import re
import json

with open(r'C:\Users\Vill3\.gemini\antigravity\brain\f9732238-5384-4f24-8075-ded12557e9eb\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for line in reversed(lines):
    try:
        data = json.loads(line)
        if 'tool_calls' in data:
            for tc in data['tool_calls']:
                args = tc.get('arguments', {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except: pass
                if isinstance(args, dict):
                    if 'saas_dashboard.html' in args.get('TargetFile', ''):
                        if 'CodeContent' in args:
                            print('FOUND!')
                            with open('saas_dashboard_recovered.html', 'w', encoding='utf-8') as out:
                                out.write(args['CodeContent'])
                            exit(0)
    except Exception as e:
        pass

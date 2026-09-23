import json
import glob

brains = glob.glob(r"C:\Users\Vill3\.gemini\antigravity\brain\*\.system_generated\logs\transcript*.jsonl")
found_html = ""
for path in brains:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get('type') == 'TOOL_RESPONSE':
                        content = data.get('content', '')
                        if 'function getTradeIdentifierPills' in content and 'function renderTrades' in content:
                            if len(content) > len(found_html):
                                found_html = content
                except:
                    pass
    except Exception as e:
        print(f"Error reading {path}: {e}")

if found_html:
    print(f"Found something! len={len(found_html)}")
    with open('trades_recovered.html', 'w', encoding='utf-8') as out:
        out.write(found_html)
else:
    print("Not found in any transcript")

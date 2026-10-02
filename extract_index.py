import json

log_path = r'C:\Users\Vill3\.gemini\antigravity\brain\fad92bba-4f6b-4714-873b-c9b313c28176\.system_generated\logs\transcript_full.jsonl'
found_index = False
latest_index = ""

try:
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
            except:
                continue
            
            # Check if this is a view_file response
            if entry.get('type') == 'TOOL_RESPONSE' and 'content' in entry:
                content = entry['content']
                if 'File Path: `file:///C:/Users/Vill3/Desktop/kalshi-ai-trader/static/index.html`' in content:
                    found_index = True
                    latest_index = content
                    
    if found_index:
        # Extract the content from the view_file output format
        # Usually it's wrapped in triple backticks
        import re
        m = re.search(r'```[a-z]*\n(.*)```', latest_index, re.DOTALL)
        if m:
            code = m.group(1)
            with open('recovered_index.html', 'w', encoding='utf-8') as out:
                out.write(code)
            print(f"Recovered index.html! Size: {len(code)}")
        else:
            print("Found it but couldn't parse the code block.")
    else:
        print("Did not find index.html in previous conversation transcript.")
except Exception as e:
    print("Error:", e)

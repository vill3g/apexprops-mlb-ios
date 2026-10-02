import json
import re

log_path = r'C:\Users\Vill3\.gemini\antigravity\brain\f9732238-5384-4f24-8075-ded12557e9eb\.system_generated\logs\transcript_full.jsonl'

# We want to find the latest write_to_file or replace_file_content or view_file that contains index.html
# Because it's huge, let's just parse the JSON and extract the latest known good state.

latest_index = None
latest_saas = None

try:
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
            except:
                continue
            
            # Check if this is a tool call
            if 'tool_calls' in entry:
                for tc in entry['tool_calls']:
                    args = tc.get('arguments', {})
                    # Look for write_to_file or replace_file_content on index.html
                    if tc['name'] == 'write_to_file' and 'index.html' in args.get('TargetFile', ''):
                        latest_index = args.get('CodeContent', '')
                    if tc['name'] == 'write_to_file' and 'saas_dashboard.html' in args.get('TargetFile', ''):
                        latest_saas = args.get('CodeContent', '')
            
            # Check if this is a tool response (view_file)
            if entry.get('type') == 'TOOL_RESPONSE' and 'content' in entry:
                content = entry['content']
                if 'File Path: `file:///C:/Users/Vill3/Desktop/kalshi-ai-trader/static/index.html`' in content:
                    # If it showed lines 1 to 2000, we might have the whole file
                    latest_index = content
                if 'File Path: `file:///C:/Users/Vill3/Desktop/kalshi-ai-trader/static/saas_dashboard.html`' in content:
                    latest_saas = content

    print(f"Found latest index.html? {'Yes' if latest_index else 'No'}")
    print(f"Found latest saas_dashboard.html? {'Yes' if latest_saas else 'No'}")
    
except Exception as e:
    print("Error:", e)

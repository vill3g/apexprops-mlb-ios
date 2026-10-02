import json
import os

brains_dir = r'C:\Users\Vill3\.gemini\antigravity\brain'
folders = [f for f in os.listdir(brains_dir) if os.path.isdir(os.path.join(brains_dir, f))]

found = False
for folder in folders:
    log_path = os.path.join(brains_dir, folder, '.system_generated', 'logs', 'transcript_full.jsonl')
    if not os.path.exists(log_path):
        continue
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if 'admin_users' in line:
                    if 'write_to_file' in line or 'replace_file_content' in line:
                        print(f"Found admin_users write in {folder}!")
                        found = True
                        break
    except:
        pass
        
if not found:
    print("No write to file for admin_users found in any transcript.")

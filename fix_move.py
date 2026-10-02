import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

start_str = "            <!-- Notifications & Alerts Card -->"
end_str = "<!-- Model & Training Controls Card -->"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
    notif_block = content[start_idx:end_idx]
    # Remove it
    content = content[:start_idx] + content[end_idx:]
    
    # Let's find API settings
    api_str = "            <!-- API Settings Card -->"
    api_idx = content.find(api_str)
    
    if api_idx != -1:
        content = content[:api_idx] + notif_block + "\n" + content[api_idx:]
        with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Moved successfully")
    else:
        print("API card not found")
else:
    print("Notif block not found properly")

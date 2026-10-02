import re

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix cent signs
content = content.replace('75\ufffd', '75¢')
content = content.replace('95\ufffd', '95¢')
content = content.replace('--\ufffd', '--¢')
content = content.replace('{yesPriceCents}\ufffd', '{yesPriceCents}¢')
content = content.replace('{noPriceCents}\ufffd', '{noPriceCents}¢')
content = content.replace(" + '\ufffd'", " + '¢'")
content = content.replace("'\ufffd'", "'¢'")

# Fix dot
content = content.replace('\ufffd  ', '·  ')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("dashboard.js ufffd fixed")

import os

html_path = r'C:\Users\Vill3\Desktop\ShadowTraderAi\static\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

if 'admin_users.js' not in content:
    content = content.replace('</head>', '<script src="/static/js/admin_users.js" defer></script>\n</head>')

if 'id="btnOpenUserPanel"' not in content:
    content = content.replace('<nav', '<button id="btnOpenUserPanel" onclick="openAdminUserPanel()">Users</button>\n<nav')

if 'id="btnIphoneUsers"' not in content:
    content = content.replace('<nav', '<button id="btnIphoneUsers" onclick="openAdminUserPanel()">Mobile Users</button>\n<nav')

if 'id="adminUserModal"' not in content:
    modal_html = '''
    <div id="adminUserModal" style="display:none;">
        <div id="adminUserListContainer"></div>
        <div id="adminUserDetailPanel"></div>
    </div>
    '''
    content += modal_html

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched index.html')

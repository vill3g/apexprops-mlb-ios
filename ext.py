import re  
html = open('static/index.html', encoding='utf-8').read()  
start = html.find('id=\" "adminUserModal\')  

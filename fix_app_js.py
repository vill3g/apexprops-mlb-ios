import re

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Add to save settings
old_save = 'ignorePass: document.getElementById("settingIgnorePass")?.checked || false,'
new_save = 'ignorePass: document.getElementById("settingIgnorePass")?.checked || false,\n            ignorePassTechnicalOnly: document.getElementById("settingIgnorePassTechnicalOnly")?.checked || false,'
content = content.replace(old_save, new_save)

# Add to load settings
old_load = 'if (document.getElementById("settingIgnorePass")) document.getElementById("settingIgnorePass").checked = !!aiSet.ignorePass;'
new_load = 'if (document.getElementById("settingIgnorePass")) document.getElementById("settingIgnorePass").checked = !!aiSet.ignorePass;\n                if (document.getElementById("settingIgnorePassTechnicalOnly")) document.getElementById("settingIgnorePassTechnicalOnly").checked = !!aiSet.ignorePassTechnicalOnly;'
content = content.replace(old_load, new_load)

with open('static/js/app.js', 'w', encoding='utf-8') as f:
    f.write(content)

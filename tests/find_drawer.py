import re

content = open("static/saas_dashboard.html", encoding="utf-8").read()
matches = re.findall(r'id=["\'][^"\']*[sS]ettings[^"\']*["\']', content)
print("Settings IDs found:", set(matches))

matches_drawer = re.findall(r'id=["\'][^"\']*[dD]rawer[^"\']*["\']', content)
print("Drawer IDs found:", set(matches_drawer))

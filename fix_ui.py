
import re

with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    c = f.read()

# Fix selectUniverse toggling classes
old_sp = "if(universe === 'SPORTS') {"
new_sp = """if(universe === 'SPORTS') {
                document.querySelectorAll('.finance-only-setting').forEach(el => el.classList.add('hidden'));
                document.querySelectorAll('.sports-only-setting').forEach(el => el.classList.remove('hidden'));"""
c = c.replace(old_sp, new_sp)

old_fin = "if(fAs) fAs.classList.remove('hidden');"
new_fin = """if(fAs) fAs.classList.remove('hidden');
                document.querySelectorAll('.finance-only-setting').forEach(el => el.classList.remove('hidden'));
                document.querySelectorAll('.sports-only-setting').forEach(el => el.classList.add('hidden'));"""
c = c.replace(old_fin, new_fin)

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(c)

print("Fixed HTML!")


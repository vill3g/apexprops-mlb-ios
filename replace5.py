import re
with open('backend/routes/engine.py', 'r') as f:
    content = f.read()

old_block = '''                parts = t.split()
                if len(parts) > 1:
                    mascot_clean = re.sub(r'[^a-zA-Z0-9]', '', parts[-1]).lower()
                    if mascot_clean:
                        if slate_map[sport].get(mascot_clean) in ('TBD', None, '') or start_time not in ('TBD', None, ''):
                            slate_map[sport][mascot_clean] = start_time'''

new_block = '''                parts = t.split()
                if len(parts) > 1:
                    mascot_clean = re.sub(r'[^a-zA-Z0-9]', '', parts[-1]).lower()
                    city_clean = re.sub(r'[^a-zA-Z0-9]', '', "".join(parts[:-1])).lower()
                    if mascot_clean:
                        if slate_map[sport].get(mascot_clean) in ('TBD', None, '') or start_time not in ('TBD', None, ''):
                            slate_map[sport][mascot_clean] = start_time
                    if city_clean:
                        if slate_map[sport].get(city_clean) in ('TBD', None, '') or start_time not in ('TBD', None, ''):
                            slate_map[sport][city_clean] = start_time'''

content = content.replace(old_block, new_block)
with open('backend/routes/engine.py', 'w') as f:
    f.write(content)
print('Added city_clean')

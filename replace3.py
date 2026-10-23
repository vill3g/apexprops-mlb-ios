with open('backend/routes/engine.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip_next = False
for line in lines:
    if skip_next:
        skip_next = False
        continue
    if "if event_ticker == 'KXMLBGAME-26OCT081700CLECWS':" in line:
        skip_next = True
        continue
    if "DEBUG MLB: slate_time_str=" in line:
        continue
    new_lines.append(line)

with open('backend/routes/engine.py', 'w') as f:
    f.writelines(new_lines)
print('Removed debug print')

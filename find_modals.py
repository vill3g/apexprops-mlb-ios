lines = open('static/index.html', 'r', encoding='utf-8').readlines()
for i, line in enumerate(lines):
    if 'id=' in line and 'Modal' in line:
        print(f'{i+1}: {line.strip()}')

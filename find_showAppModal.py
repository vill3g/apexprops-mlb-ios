lines = open('static/js/app.js', 'r', encoding='utf-8').readlines()
for i, line in enumerate(lines):
    if 'showAppModal' in line:
        print(f'{i+1}: {line.strip()}')

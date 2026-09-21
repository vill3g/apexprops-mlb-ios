with open('static/index.html', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

for i in range(7800, 7835):
    print(f"{i+1}: {lines[i].encode('ascii', 'ignore').decode('ascii')}")

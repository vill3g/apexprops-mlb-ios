with open('static/index.html', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

for i in range(4530, 4550):
    print(f"{i+1}: {lines[i].encode('ascii', 'ignore').decode('ascii')}")

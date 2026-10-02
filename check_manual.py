file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'
with open(file_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'MANUAL' in line and 'badges.push' in line:
            print(line.strip())

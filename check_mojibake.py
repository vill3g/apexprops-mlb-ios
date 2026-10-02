file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\index.html'
with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        if '' in line:
            print(line.strip())

with open('backend/routes/engine.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if '"status"' in line and '"error"' in line:
            print(f'Line {i+1}: {line.strip()}')

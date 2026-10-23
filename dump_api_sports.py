
with open('backend/routes/engine.py', 'r') as f:
    lines = f.readlines()
    start = -1
    end = -1
    for i, line in enumerate(lines):
        if line.startswith('def api_sports_events('):
            start = i
            break
    for i in range(start + 1, len(lines)):
        if lines[i].startswith('def '):
            end = i
            break
    if end == -1: end = len(lines)
    
    with open('api_sports.txt', 'w') as out:
        out.write(''.join(lines[start:end]))


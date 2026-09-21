with open('static/index.html', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

unmatched = [3486, 3661, 3820, 4147, 4222, 4263, 4266, 4295, 5328, 5330]
for u in unmatched:
    idx = u - 1
    print(f"--- LINE {u} ---")
    for i in range(idx-2, idx+3):
        if i >= 0 and i < len(lines):
            print(lines[i])

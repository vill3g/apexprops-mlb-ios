with open('backend/sports_bridge/prediction_client.py', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
for i, line in enumerate(lines):
    if 'predict_for_event' in line:
        start = i
        break

for i in range(start, len(lines)):
    if 'def ' in lines[i] and i > start:
        end = i
        break
else:
    end = len(lines)

for line in lines[start:end]:
    if 'api/' in line and 'simulate' in line:
        print(line.strip())

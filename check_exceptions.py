import os, glob

def check_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i in range(len(lines)):
        if 'except Exception' in lines[i] or 'except:' in lines[i]:
            if i + 1 < len(lines) and 'pass' in lines[i+1]:
                print(f'{path}:{i+1} Swallowed Exception')

for f in glob.glob('backend/btc/*.py'):
    check_file(f)

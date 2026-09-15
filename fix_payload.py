import re

def fix():
    file_path = 'backend/btc/kalshi_trader.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'"count": f"\{int\(count\)\}\.00",', '"count": int(count),', content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix()
    print("Fixed payload count")

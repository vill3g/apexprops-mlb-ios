import os

def fix():
    file_path = 'backend/btc/kalshi_trader.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Kalshi V2 API is written in Go and expects a string representation of decimals
    # for the count field, not a raw JSON integer.
    target = '"count": int(count),'
    injection = '"count": f"{int(count)}.00",'

    content = content.replace(target, injection)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix()
    print("Restored Kalshi API count to string format")

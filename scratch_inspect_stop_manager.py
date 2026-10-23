import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('backend/btc/auto_executor/stop_manager.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos = text.find('bid_price =')
while pos != -1:
    print('--- bid_price match ---')
    print(text[pos-100:pos+300])
    pos = text.find('bid_price =', pos+1)

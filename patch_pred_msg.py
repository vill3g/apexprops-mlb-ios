with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\btc\\analyzer\\contract_eval.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('Chart technicals confirm UP (+15%)', 'Chart technicals confirm UP (+5%)')
content = content.replace('Chart is heavily bearish (-15%)', 'Chart leans bearish (-5%)')

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\btc\\analyzer\\contract_eval.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated catalyst messages')

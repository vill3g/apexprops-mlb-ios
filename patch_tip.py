import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the inner block of checkTradingTip
old_block = '''        if (data.success && data.tip) {
            document.getElementById('trading-tip-content').textContent = data.tip;
            const modal = document.getElementById('trading-tip-modal');
            if (modal) {
                modal.classList.remove('hidden');
                modal.classList.add('flex');
                sessionStorage.setItem('tradingTipShown', 'true');
            }
        }'''

new_block = '''        if (data.success && data.tip) {
            document.getElementById('trading-tip-content').textContent = data.tip;
            const modal = document.getElementById('trading-tip-modal');
            if (modal) {
                modal.classList.remove('hidden');
                modal.classList.add('flex');
                sessionStorage.setItem('tradingTipShown', 'true');
            }
        } else {
            if (force) alert("Could not fetch tip: " + JSON.stringify(data));
        }'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced!")
else:
    print("Could not find block.")

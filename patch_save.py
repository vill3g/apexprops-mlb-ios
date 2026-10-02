import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

# I need to find the definition of sl inside _executeSaveUserConfig
old_save = '''                const sl = parseFloat(document.getElementById('stop-loss-pct')?.value) || 10.0;
                const tp = parseFloat(document.getElementById('take-profit-pct')?.value) || 50.0;
                const tpEnabled = document.getElementById('take-profit-enabled')?.checked ?? true;'''

new_save = '''                const sl = parseFloat(document.getElementById('stop-loss-pct')?.value) || 10.0;
                const slEnabled = document.getElementById('stop-loss-enabled')?.checked ?? true;
                const tp = parseFloat(document.getElementById('take-profit-pct')?.value) || 50.0;
                const tpEnabled = document.getElementById('take-profit-enabled')?.checked ?? true;'''

if old_save in content:
    content = content.replace(old_save, new_save)
    print("Replaced var extraction")

# Also need to find the fetch payload in _executeSaveUserConfig
old_payload = '''                    body: JSON.stringify({
                        trade_size_dollars: size,
                        paper_trade_size_dollars: paperSize,
                        stop_loss_pct: sl,
                        one_click_trade: false,
                        auto_force_trade: autoForce,
                        target_asset: "BTC",
                        trading_style: style,
                        signal_source: src,
                        take_profit_pct: tp,
                        take_profit_enabled: tpEnabled,'''

new_payload = '''                    body: JSON.stringify({
                        trade_size_dollars: size,
                        paper_trade_size_dollars: paperSize,
                        stop_loss_pct: sl,
                        stop_loss_enabled: slEnabled,
                        one_click_trade: false,
                        auto_force_trade: autoForce,
                        target_asset: "BTC",
                        trading_style: style,
                        signal_source: src,
                        take_profit_pct: tp,
                        take_profit_enabled: tpEnabled,'''

if old_payload in content:
    content = content.replace(old_payload, new_payload)
    print("Replaced fetch payload")

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'w', encoding='utf-8') as f:
    f.write(content)

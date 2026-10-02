import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\btc\\auto_executor\\stop_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'stop_loss_pct = float(self.ai_settings.get("stopLossPercent", 50.0))\n                            if profit_pct <= -stop_loss_pct:',
    'stop_loss_pct = float(self.ai_settings.get("stopLossPercent", 50.0))\n                            sl_enabled = bool(self.ai_settings.get("stopLossEnabled", 1))\n                            if sl_enabled and profit_pct <= -stop_loss_pct:'
)

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\btc\\auto_executor\\stop_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated stop_manager.py!")

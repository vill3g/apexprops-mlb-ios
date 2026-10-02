import re
path = "static/js/dashboard.js"
with open(path, "r", encoding="utf-8") as f:
    js = f.read()

# Let's see how loadConfig populates elements. Usually it's `document.getElementById('xyz').value = s.xyz;`
# We'll use a regex replacement to inject our logic.

load_config_pattern = r"(if \(s\.take_profit_enabled !== undefined\) document\.getElementById\('take-profit-enabled'\)\.checked = s\.take_profit_enabled;)"
load_config_replacement = """\1
                    if (s.notify_trade_results !== undefined) document.getElementById('notify-trade-results').checked = s.notify_trade_results;
                    if (s.notify_market_trends !== undefined) document.getElementById('notify-market-trends').checked = s.notify_market_trends;
"""
js = re.sub(load_config_pattern, load_config_replacement, js)

save_config_pattern = r"(take_profit_enabled: document\.getElementById\('take-profit-enabled'\)\.checked,)"
save_config_replacement = """\1
                notify_trade_results: document.getElementById('notify-trade-results').checked,
                notify_market_trends: document.getElementById('notify-market-trends').checked,
"""
js = re.sub(save_config_pattern, save_config_replacement, js)

with open(path, "w", encoding="utf-8") as f:
    f.write(js)
print("Updated dashboard.js to load/save notification settings")

import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\btc\\analyzer\\contract_eval.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_prediction = '''    if trading_style == \"PREDICTION\":
        # Start with the raw ML probability
        p_yes = float(raw_ml_prob) * 100.0
        
        # Use the raw chart technicals (pre_gate_direction) to adjust the ML probability.
        # This prevents the ML from blindly predicting YES when the chart is clearly crashing.
        if pre_gate_direction == \"ABOVE\":
            p_yes += 15.0'''

new_prediction = '''    if trading_style == \"PREDICTION\":
        # Start with the raw ML probability
        p_yes = float(raw_ml_prob) * 100.0
        
        # Apply a light chart-based nudge (5% instead of 15%) to avoid double-counting
        # features the ML model has already incorporated. The ML prediction is the primary driver.
        if pre_gate_direction == \"ABOVE\":
            p_yes += 5.0'''

if old_prediction in content:
    content = content.replace(old_prediction, new_prediction)
    print('Replaced +15 -> +5')
else:
    print('Could not find +15 block')

old_below = '''        elif pre_gate_direction == \"BELOW\":
            p_yes -= 15.0'''

new_below = '''        elif pre_gate_direction == \"BELOW\":
            p_yes -= 5.0'''

if old_below in content:
    content = content.replace(old_below, new_below)
    print('Replaced -15 -> -5')
else:
    print('Could not find -15 block')

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\btc\\analyzer\\contract_eval.py', 'w', encoding='utf-8') as f:
    f.write(content)

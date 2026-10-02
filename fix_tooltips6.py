fpath = 'static/index.html'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

new_keys = """    'model_training': {
        title: 'Model & Training Controls',
        desc: 'Configures the machine learning architecture and training window. Modifying these parameters affects how the AI interprets incoming market data.',
        tip: 'Deep Q-Network is optimal for high-frequency 15M prediction markets.'
    },
    'signal_isolation': {
        title: 'Trade Signal Isolation',
        desc: 'Dictates the origin of execution signals. Can enforce trades strictly from AI Probability, strictly from Technical indicators, or a blended consensus.',
        tip: 'Use BLEND for maximum safety, or AI Only for pure statistical trading.'
    },
    'risk_position': {
        title: 'Risk & Position Management',
        desc: 'Global rules for bankroll protection. Controls stop-loss thresholds, position sizing, and maximum daily drawdown limits.',
        tip: 'Always set a Max Daily Loss limit to prevent catastrophic streaks in choppy markets.'
    },
    'pred_confidence': {
        title: 'Prediction Confidence Filters',
        desc: 'Minimum probability and confidence thresholds required for the engine to fire an order. Higher thresholds drastically reduce trading frequency.',
        tip: '65% to 75% is the sweet spot for 15M BTC contracts.'
    },
    'exec_timing': {
        title: 'Execution & Timing',
        desc: 'Regulates precisely when orders are dispatched to Kalshi. Includes safety timers to prevent executing too close to contract settlement.',
        tip: 'Allow at least a 2-minute blackout window before settlement to avoid extreme slippage.'
    },
    'log_debug': {
        title: 'Logging & Debugging',
        desc: 'Controls console output verbosity. Debug mode outputs detailed tensor mathematics and raw API JSON payloads.',
        tip: 'Only enable Debug Mode when actively troubleshooting; it generates massive log files.'
    },
"""

text = text.replace("const ADMIN_SETTING_INFO = {", "const ADMIN_SETTING_INFO = {\n" + new_keys)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)

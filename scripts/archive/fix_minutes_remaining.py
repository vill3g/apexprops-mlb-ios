import re

with open('backend/btc/ml_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

bad_block = """        self.feature_keys = list(FEATURE_KEYS)
        if self.trading_style == "MOMENTUM_SURFER":
            self.feature_keys.append("minutes_remaining")"""
            
good_block = """        self.feature_keys = list(FEATURE_KEYS)
        # REMOVED: minutes_remaining is already globally appended in FEATURE_KEYS.
        # Doing it again duplicates it and corrupts the LSTM PyTorch tensor tail."""

code = code.replace(bad_block, good_block)

with open('backend/btc/ml_engine.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed MLEngine.__init__")

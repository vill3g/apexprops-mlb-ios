import re

with open('push_to_github.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add the missing files to the core_files list
engine_files = [
    "backend/engine/__init__.py",
    "backend/engine/multi_asset_fetcher.py",
    "backend/engine/bvp_weather.py",
    "backend/engine/international_model.py",
    "backend/engine/pitcher_k_model.py",
    "backend/engine/simulator.py",
    "backend/engine/top5_selector.py",
]

# We will inject these files into the core_files array.
content = content.replace('"backend/btc/backtest.py",', '"backend/btc/backtest.py",\n        ' + ', '.join(f'"{f}"' for f in engine_files) + ',')

with open('push_to_github.py', 'w', encoding='utf-8') as f:
    f.write(content)

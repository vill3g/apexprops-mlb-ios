import re

with open('backend/engine/multi_asset_fetcher.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix fetch_asset_candles
content = content.replace(
    'def fetch_asset_candles(asset: str = "BTC", timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:\n    """Fetch candles for multi-assets with correct fallbacks."""\n    if asset == "BTC":',
    'def fetch_asset_candles(asset: str = "BTC", timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:\n    """Fetch candles for multi-assets with correct fallbacks."""\n    asset = asset.upper()\n    if asset == "BTC":'
)

# Fix get_asset_ticker
content = content.replace(
    'def get_asset_ticker(asset: str) -> dict:\n    if asset == "BTC":',
    'def get_asset_ticker(asset: str) -> dict:\n    asset = asset.upper()\n    if asset == "BTC":'
)

# Fix is_market_open
content = content.replace(
    'def is_market_open(asset: str) -> bool:\n    if asset in ["BTC", "ETH"]:',
    'def is_market_open(asset: str) -> bool:\n    asset = asset.upper()\n    if asset in ["BTC", "ETH"]:'
)

with open('backend/engine/multi_asset_fetcher.py', 'w', encoding='utf-8') as f:
    f.write(content)

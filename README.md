# Kalshi BTC 15M AI Trader & Confluence Engine

An autonomous, high-frequency trading bot and decision engine designed for **Kalshi 15-Minute Bitcoin Prediction Markets (`KXBTC15M`)**. Combines multi-factor technical analysis, XGBoost machine learning inference, and an RSA-signed Kalshi order execution pipeline with strict risk management controls.

---

## Key Features

1. **Autonomous 15-Minute Rollover & Execution**:
   - Analyzes real-time Bitcoin 15-minute price action, candlestick structure, RSI/MACD/EMA momentum, and VWAP bands.
   - Evaluates orderbook depth, implied probabilities, and directional edges on active Kalshi contracts.
   - Auto-executes `YES` (ABOVE) or `NO` (BELOW) limit orders when probability and conviction thresholds are satisfied.

2. **Machine Learning Inference (`ml_engine.py`)**:
   - Gradient-boosted tree model (XGBoost) trained on historical 15-minute candle progressions and target settlements.
   - Generates direction, calibrated probability percent, conviction grade, and primary catalyst telemetry.

3. **Dual Execution Modes**:
   - **PAPER Mode**: Simulated trading with persistent balance tracking (`paper_balance.json` via atomic I/O).
   - **LIVE Mode**: Direct real-money limit order submission to Kalshi's trading API using RSA cryptographic request signing.

4. **Institutional Risk Management & Guardrails**:
   - Hard daily risk ceiling (`max_daily_risk`).
   - Daily trade volume cap (`max_daily_trades`).
   - Strict per-order contract limit (`ABSOLUTE_MAX_CONTRACTS`).
   - Dynamic stop-loss and take-profit structural bounds.

5. **Security & Authentication**:
   - All sensitive trading, toggle, settings, and scalp endpoints (`/api/btc/trade/*`, `/api/btc/scalp/*`) are gated behind constant-time shared secret authentication (`X-API-Token`).
   - Cryptographic keys and API tokens are gitignored and loaded exclusively from environment variables or local secure files.

---

## Directory Structure

```
kalshi-ai-trader/
├── backend/
│   ├── btc/
│   │   ├── analyzer.py            # Multi-timeframe confluence and signal engine
│   │   ├── auto_executor.py       # Autonomous background trading loop and state manager
│   │   ├── data_fetcher.py        # Exchange klines, orderbook, and ticker data
│   │   ├── dual_ml_engine.py      # Ensemble machine learning predictor
│   │   ├── indicators.py          # Technical indicator calculations
│   │   ├── io_utils.py            # Atomic file persistence helpers
│   │   ├── kalshi_client.py       # Direct Kalshi market data client
│   │   ├── kalshi_trader.py       # Authenticated Kalshi trade execution client
│   │   ├── loss_analyzer.py       # Automated post-mortem loss diagnosis
│   │   ├── ml_engine.py           # Core XGBoost prediction model
│   │   ├── news_fetcher.py        # Crypto sentiment & macro headlines
│   │   ├── paper_balance.py       # Paper trading account balance manager
│   │   ├── pattern_detector.py    # Candlestick pattern detection
│   │   └── scalp_engine.py        # Micro-scalp high-frequency engine
│   ├── data/
│   │   └── trading_config.json    # Bot risk limits & AI configurations
│   └── main.py                    # FastAPI REST API & background watchdog tasks
├── static/
│   ├── index.html                 # Real-time execution dashboard & telemetry UI
│   ├── manifest.json              # Web app manifest
│   └── assets/                    # Application icons
├── scripts/
│   └── manual_probes/             # CLI order probe utilities
├── server_watchdog.py             # Auto-restarting background watchdog supervisor
├── launch_desktop.py              # Windows desktop launcher with single-instance lock
├── run_app.bat                    # One-click Windows runner
├── requirements.txt               # Exact pinned Python dependencies
└── README.md
```

---

## How to Run

### Safe-by-Default Operation
By default, the application starts in **PAPER mode** with autonomous execution **DISABLED** (`enabled: false`, `dryRun: true`, `max_daily_trades: 10`, `max_daily_risk: $25.00`). If started with a fresh clone lacking historical trade records, the bot automatically demotes any accidental `LIVE` setting to `PAPER` to prevent unintended live market orders. Switching to `LIVE` mode strictly requires authenticated Kalshi credentials and an explicit user API or UI command.

### Option 1: Quick Launch (Windows)
Double-click `run_app.bat` or run:
```cmd
run_app.bat
```

### Option 2: Manual Terminal Launch
```powershell
# Set mandatory auth token
$env:APP_API_TOKEN = "YourSecureTokenHere"

# Start Uvicorn server on port 8056
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8056 --reload
```
Access the dashboard at `http://127.0.0.1:8056`.

---

## API Authentication

All `/api/btc/trade/*` and `/api/btc/scalp/*` endpoints require the `X-API-Token` header matching `APP_API_TOKEN`:

```bash
curl -X GET "http://127.0.0.1:8056/api/btc/trade/status" \
     -H "X-API-Token: YourSecureTokenHere"
```
Requests without a valid header receive `HTTP 401 Unauthorized`.

---

## Safety Notice & Disclaimer

> [!WARNING]
> This software interacts with real prediction markets when switched to **LIVE** mode. Real capital is at risk. Always test new strategies thoroughly in **PAPER** mode before enabling live trade execution.

### Exchange Basis Risk Notice
Technical analysis and machine learning inferences are computed from spot BTC-USD orderbook and candlestick feeds (Coinbase, Kraken, Binance.US). However, Kalshi's `KXBTC15M` prediction markets settle strictly against the **CF Benchmarks Bitcoin Real Time Index (BRTI)** at contract expiration. Due to index weighting methodologies and exchange micro-price divergences, short-term basis differences may exist between spot prices and official Kalshi settlement values. Operators should account for this basis spread when trading contracts near the strike pin.

Additionally, the prediction engine consumes live Kalshi market-implied signals (`kalshi_yes_prob` and `kalshi_book_imbalance`). For offline historical backtesting and candle-only synthetic generation, these features default to uninformative neutral priors (`50.0%` probability and `0.0` neutral orderbook imbalance) to prevent forward data leakage while preserving live model feature vector alignment.


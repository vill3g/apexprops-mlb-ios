"""
Centralized configuration constants for the Kalshi AI Trader application.

All hardcoded trading parameters, asset identifiers, timing thresholds,
and API defaults are consolidated here. Values can be overridden via
environment variables.
"""
import os

# ─── Asset & Market ───────────────────────────────────────────────
ASSET = os.getenv("KALSHI_ASSET", "BTC")
TIMEFRAME = os.getenv("KALSHI_TIMEFRAME", "15m")
SERIES_PREFIX = os.getenv("KALSHI_SERIES_PREFIX", "KXBTC15M")

# ─── Server ───────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8056"))

# ─── Trading Defaults ────────────────────────────────────────────
DEFAULT_TRADE_SIZE_DOLLARS = float(os.getenv("DEFAULT_TRADE_SIZE", "5.0"))
DEFAULT_PAPER_TRADE_SIZE_DOLLARS = float(os.getenv("DEFAULT_PAPER_TRADE_SIZE", "50.0"))
DEFAULT_PAPER_BALANCE = float(os.getenv("DEFAULT_PAPER_BALANCE", "500.0"))
DEFAULT_STOP_LOSS_PCT = float(os.getenv("DEFAULT_STOP_LOSS_PCT", "50.0"))
DEFAULT_TAKE_PROFIT_PCT = float(os.getenv("DEFAULT_TAKE_PROFIT_PCT", "50.0"))
DEFAULT_MAX_DAILY_TRADES = int(os.getenv("DEFAULT_MAX_DAILY_TRADES", "10"))
DEFAULT_MAX_DAILY_RISK = float(os.getenv("DEFAULT_MAX_DAILY_RISK", "50.0"))

# ─── AI / ML Defaults ────────────────────────────────────────────
DEFAULT_MODEL_CHOICE = os.getenv("DEFAULT_MODEL_CHOICE", "RL_DQN")
DEFAULT_SIGNAL_SOURCE = os.getenv("DEFAULT_SIGNAL_SOURCE", "RL_DQN")
DEFAULT_TRADING_STYLE = os.getenv("DEFAULT_TRADING_STYLE", "AUTO")
DEFAULT_TRAIN_WINDOW = int(os.getenv("DEFAULT_TRAIN_WINDOW", "4000"))
DEFAULT_REGULARIZATION_C = float(os.getenv("DEFAULT_REGULARIZATION_C", "0.5"))
DEFAULT_CLASS_WEIGHT = os.getenv("DEFAULT_CLASS_WEIGHT", "balanced")
DEFAULT_XGB_ESTIMATORS = int(os.getenv("DEFAULT_XGB_ESTIMATORS", "300"))
DEFAULT_XGB_MAX_DEPTH = int(os.getenv("DEFAULT_XGB_MAX_DEPTH", "5"))
DEFAULT_XGB_LEARNING_RATE = float(os.getenv("DEFAULT_XGB_LEARNING_RATE", "0.1"))

# ─── Trailing Stop Defaults ──────────────────────────────────────
DEFAULT_TRAILING_STOP_ACTIVATION_PCT = float(os.getenv("DEFAULT_TRAILING_STOP_ACTIVATION_PCT", "35.0"))
DEFAULT_TRAILING_STOP_DISTANCE_PCT = float(os.getenv("DEFAULT_TRAILING_STOP_DISTANCE_PCT", "6.0"))
DEFAULT_SECOND_ENTRY_MAX_ASK = float(os.getenv("DEFAULT_SECOND_ENTRY_MAX_ASK", "0.75"))

# ─── Timing & Polling ────────────────────────────────────────────
AUTO_TRADER_LOOP_INTERVAL_SEC = float(os.getenv("AUTO_TRADER_LOOP_INTERVAL", "2.0"))
SETTLEMENT_POLL_INTERVAL_SEC = float(os.getenv("SETTLEMENT_POLL_INTERVAL", "2.0"))
SCALP_MONITOR_INTERVAL_SEC = float(os.getenv("SCALP_MONITOR_INTERVAL", "0.3"))
LIVE_BALANCE_CACHE_TTL_SEC = float(os.getenv("LIVE_BALANCE_CACHE_TTL", "3.0"))
ML_MODEL_CACHE_STALE_HOURS = int(os.getenv("ML_MODEL_CACHE_STALE_HOURS", "168"))  # 7 days

# ─── Kalshi API ───────────────────────────────────────────────────
KALSHI_API_TIMEOUT_SEC = float(os.getenv("KALSHI_API_TIMEOUT", "5.0"))
KALSHI_API_MAX_RETRIES = int(os.getenv("KALSHI_API_MAX_RETRIES", "3"))
KALSHI_API_RETRY_BACKOFF_BASE = float(os.getenv("KALSHI_API_RETRY_BACKOFF", "1.0"))

# ─── Data Paths ───────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

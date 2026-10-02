
import logging

logger = logging.getLogger(__name__)
from dataclasses import dataclass

try:

    pass
except ImportError:
    pass


@dataclass
class TradeSetup:
    direction: str            # "BUY (UP)" | "SELL (DOWN)" | "WAIT (NEUTRAL)"
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward_1: float
    risk_reward_2: float
    risk_amount: float
    risk_percent: float


@dataclass
class AnalysisResult:
    timestamp: str
    price: float
    direction: str            # "STRONG BULLISH (UP)" | "BULLISH (UP)" | "NEUTRAL / CHOPPY" | "BEARISH (DOWN)" | "STRONG BEARISH (DOWN)"
    primary_bias: str         # "UP" | "DOWN" | "NEUTRAL"
    confluence_score: int     # -100 to +100
    confidence_percent: int   # 50% to 95%
    reasons_bullish: list[str]
    reasons_bearish: list[str]
    detected_patterns: list[dict]
    market_structure: dict
    indicators: dict
    trade_setup: dict



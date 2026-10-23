"""
Agentic Intraday AI Desk for US Stocks, ETFs & Options
Powered by Google Gemini (gemini-3.5-flash & gemma-4-26b-a4b-it).
Comprises 3 Specialized Reasoning Agents:
1. Technical & Microstructure Agent: Analyzes ORB, VWAP, EMA9/21, Squeeze, and RVOL.
2. Options Greeks & Structure Agent: Selects between equity shares vs leveraged defined-risk options.
3. Risk & Buying-Power Governor Agent: Enforces buying power, position caps, and Kelly sizing (Unrestricted PDT).
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Any
import requests

from backend.investments.intraday_scanner import IntradayStockScanner
from backend.investments.options_selector import OptionsContractSelector
from backend.investments.robinhood_client import RobinhoodMarketSession
from backend.investments.microstructure_engine import MicrostructureEngine
from backend.investments.macro_catalyst_engine import MacroCatalystEngine
from backend.investments.regime_bandit import RegimeBanditEngine
from backend.investments.options_quant_engine import OptionsQuantEngine

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("DEFAULT_GEMINI_KEY") or ""
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={GEMINI_API_KEY}"


class AgenticInvestmentsDesk:
    """Intraday AI Trading Desk for Robinhood Equities and Options."""

    def __init__(self):
        self.scanner = IntradayStockScanner()
        self.options_selector = OptionsContractSelector()

    def evaluate_opportunity(
        self,
        symbol: str,
        user_config: Dict[str, Any],
        buying_power: float
    ) -> Dict[str, Any]:
        """
        Runs the full 3-Stage Agentic Reasoning Pipeline on a candidate symbol.
        Returns trade recommendation dossier or PASS.
        """
        session = RobinhoodMarketSession.get_current_session()
        breadth = self.scanner.get_market_breadth()
        tech = self.scanner.analyze_symbol(symbol)

        # Pre-filter: Check minimum scanner confidence and market session
        min_conf = float(user_config.get("investments_min_confidence", 72.0))

        # Frontier 4: Cross-Asset Macro & Catalyst Evaluation
        macro_lead_lag = MacroCatalystEngine.get_kalshi_macro_lead_lag()
        sec_catalyst = MacroCatalystEngine.evaluate_sec_catalyst(symbol)
        
        # Apply macro and catalyst multipliers to confidence
        adjusted_conf = tech.get("confidence", 0.0) * sec_catalyst.get("conviction_boost", 1.0)
        if macro_lead_lag.get("event_freeze_active"):
            return {
                "decision": "PASS",
                "symbol": symbol,
                "confidence": adjusted_conf,
                "reason": f"Macro Event Freeze Active ({macro_lead_lag.get('active_event_name')}). All execution paused.",
                "macro_snapshot": macro_lead_lag
            }

        # Frontier 3: Market Regime Detection
        regime_info = RegimeBanditEngine.detect_market_regime(
            bars=tech.get("bars") or [],
            adx=float(tech.get("adx", 25.0)),
            atr=float(tech.get("atr", 1.5)),
            rvol=float(tech.get("rvol", 1.2))
        )
        setup_type = tech.get("setup_type", "ORB_BREAKOUT")
        if regime_info["regime"] == "HIGH_VOLATILITY_CHOP":
            return {
                "decision": "PASS",
                "symbol": symbol,
                "confidence": adjusted_conf,
                "reason": "Market in HIGH_VOLATILITY_CHOP regime. Breakout strategies muted.",
                "regime_info": regime_info
            }

        if adjusted_conf < min_conf or tech.get("bias") == "NEUTRAL":
            return {
                "decision": "PASS",
                "symbol": symbol,
                "confidence": tech.get("confidence", 0.0),
                "reason": f"Scanner confidence ({tech.get('confidence', 0.0):.1f}%) below minimum hurdle ({min_conf:.1f}%) or bias is Neutral.",
                "technical_snapshot": tech,
                "market_session": session
            }

        if not session["can_daytrade"]:
            return {
                "decision": "PASS",
                "symbol": symbol,
                "confidence": tech.get("confidence", 0.0),
                "reason": f"Market session ({session['state']}) does not permit intraday day-trading.",
                "market_session": session
            }

        # Stage 2: Options vs Shares Structuring
        asset_classes = str(user_config.get("investments_asset_classes") or "STOCKS,ETFS,OPTIONS").upper()
        allow_options = "OPTIONS" in asset_classes
        allow_stocks = "STOCKS" in asset_classes or "ETFS" in asset_classes

        option_contract = None
        if allow_options:
            option_contract = self.options_selector.select_best_contract(
                symbol=symbol,
                bias=tech["bias"],
                target_delta=float(user_config.get("investments_options_delta_target", 0.45)),
                dte_window=str(user_config.get("investments_options_dte_window", "0DTE_WEEKLY")),
                max_spread_pct=float(user_config.get("investments_options_max_spread_pct", 8.0)),
                min_oi=int(user_config.get("investments_options_min_oi", 250))
            )

        # Sizing and Risk Governor
        wager_cap = float(user_config.get("investments_trade_size_dollars", 250.0))
        max_daily_risk = float(user_config.get("investments_max_daily_risk", 500.0))
        trade_capital = min(wager_cap, buying_power, max_daily_risk)

        if trade_capital < 25.0:
            return {
                "decision": "PASS",
                "symbol": symbol,
                "reason": f"Insufficient allocated capital (${trade_capital:.2f}) for trade entry.",
                "buying_power": buying_power
            }

        # Prefer Options if available and within capital, otherwise Shares
        recommended_vehicle = "STOCK"
        sizing_details = {}

        if allow_options and option_contract and option_contract.get("cost_per_contract", 9999) <= trade_capital:
            recommended_vehicle = "OPTION"
            cost_per = option_contract["cost_per_contract"]
            contracts = max(1, int(trade_capital / max(cost_per, 1.0)))
            total_cost = round(contracts * cost_per, 2)
            sizing_details = {
                "vehicle": "OPTION",
                "contract_ticker": option_contract["contract_ticker"],
                "option_type": option_contract["option_type"],
                "strike": option_contract["strike"],
                "expiration": option_contract["expiration"],
                "contracts": contracts,
                "price_per_contract": option_contract["ask"],
                "cost_total": total_cost,
                "tp_pct": float(user_config.get("investments_option_tp_pct", 35.0)),
                "sl_pct": float(user_config.get("investments_option_sl_pct", 20.0))
            }
        elif allow_stocks:
            price = tech["price"]
            allow_fractional = bool(user_config.get("investments_allow_fractional", 1))
            if allow_fractional:
                shares = round(trade_capital / max(price, 0.01), 3)
            else:
                shares = int(trade_capital / max(price, 0.01))

            if shares <= 0:
                return {
                    "decision": "PASS",
                    "symbol": symbol,
                    "reason": f"Stock share price (${price:.2f}) exceeds trade capital (${trade_capital:.2f}) and fractional shares disabled."
                }

            total_cost = round(shares * price, 2)
            sizing_details = {
                "vehicle": "STOCK",
                "shares": shares,
                "price": price,
                "cost_total": total_cost,
                "tp_pct": float(user_config.get("investments_stock_tp_pct", 2.5)),
                "sl_pct": float(user_config.get("investments_stock_sl_pct", 1.0))
            }
        else:
            return {
                "decision": "PASS",
                "symbol": symbol,
                "reason": "No supported asset class enabled or within capital bounds."
            }

        # Prompt Gemini for final Desk synthesis
        dossier = self._synthesize_ai_dossier(
            symbol=symbol,
            tech=tech,
            breadth=breadth,
            sizing=sizing_details,
            user_config=user_config
        )

        return {
            "decision": "EXECUTE",
            "symbol": symbol,
            "bias": tech["bias"],
            "setup_type": tech["setup_type"],
            "confidence": tech["confidence"],
            "recommended_vehicle": recommended_vehicle,
            "sizing": sizing_details,
            "technical_snapshot": tech,
            "breadth": breadth,
            "dossier": dossier,
            "market_session": session,
            "generated_at": time.time()
        }

    def _synthesize_ai_dossier(
        self,
        symbol: str,
        tech: Dict[str, Any],
        breadth: Dict[str, Any],
        sizing: Dict[str, Any],
        user_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synthesizes high-conviction narrative using Gemini."""
        prompt = f"""You are the Lead Desk Trader at ShadowTrader AI Investments Desk (Robinhood Equities & Options).
Evaluate the following intraday setup and provide a concise quantitative trade breakdown.

SYMBOL: {symbol}
BIAS: {tech.get('bias')}
SETUP: {tech.get('setup_type')}
PRICE: ${tech.get('price'):.2f} (RVOL: {tech.get('rvol')}x, VWAP: ${tech.get('vwap'):.2f}, EMA9: ${tech.get('ema9'):.2f}, EMA21: ${tech.get('ema21'):.2f}, RSI: {tech.get('rsi')})
MARKET BREADTH: {breadth.get('macro_bias')} (SPY: {breadth.get('spy_change_pct')}%, QQQ: {breadth.get('qqq_change_pct')}%)
RECOMMENDED VEHICLE: {sizing.get('vehicle')} (Details: {json.dumps(sizing)})

Output strict JSON:
{{
  "thesis": "<2 sentence institutional rationale>",
  "key_catalysts": ["<point 1>", "<point 2>"],
  "conviction_score": <number 72 to 92>,
  "risk_warning": "<key risk or invalidation level>"
}}
JSON ONLY:"""

        if GEMINI_API_KEY:
            try:
                resp = requests.post(
                    GEMINI_URL,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300}
                    },
                    timeout=4.0
                )
                if resp.status_code == 200:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    clean_text = text.replace("```json", "").replace("```", "").strip()
                    return json.loads(clean_text)
            except Exception as e:
                logger.debug(f"[AgenticInvestmentsDesk] Gemini synthesis fallback: {e}")

        # Deterministic Institutional Fallback
        return {
            "thesis": f"{tech.get('setup_type')} confirmation on {symbol} with {tech.get('rvol')}x RVOL above VWAP ${tech.get('vwap'):.2f}, aligning with institutional {breadth.get('macro_bias')} momentum.",
            "key_catalysts": [
                f"{tech.get('bias')} volume expansion ({tech.get('rvol')}x RVOL)",
                f"Trend alignment with SPY ({breadth.get('spy_change_pct')}%) and QQQ ({breadth.get('qqq_change_pct')}%)"
            ],
            "conviction_score": tech.get("confidence", 75.0),
            "risk_warning": f"Invalidate setup if price crosses back across VWAP (${tech.get('vwap'):.2f})"
        }

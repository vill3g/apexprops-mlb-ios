"""
Alpha Ideator for ShadowTrader Quant Lab.
Formulates statistical trading hypotheses while actively conditioning on
lessons and negative constraints retrieved from the Strategy Graveyard.
"""
from __future__ import annotations

import json
import logging
import os
import random
import uuid
from typing import Any, Dict, List, Optional

from backend.engine.quant_lab.graveyard import StrategyGraveyard

logger = logging.getLogger(__name__)


class AlphaIdeator:
    """Generates strategy hypotheses for financial and sports prediction markets."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def generate_hypothesis(
        self,
        asset: str = "BTC",
        target_interval: str = "15m",
        market_regime: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a quantitative strategy hypothesis.
        Injects past failures from StrategyGraveyard as negative constraints.
        """
        asset_norm = str(asset or "BTC").upper().strip()
        lessons = StrategyGraveyard.get_relevant_lessons(asset=asset_norm, limit=8)

        negative_constraints = [
            f"- {l.get('name')}: {l.get('negative_rule')} (Why failed: {l.get('post_mortem_summary')})"
            for l in lessons if l.get("negative_rule")
        ]

        logger.info(
            f"[AlphaIdeator] Generating hypothesis for {asset_norm} {target_interval} "
            f"with {len(negative_constraints)} negative constraints from Graveyard..."
        )

        # LLM ideation is a paid Gemini call per attempt. It is off unless QUANT_LAB_LLM_IDEATION=1 is set,
        # so the quant lab uses only the deterministic generator by default.
        if self.api_key and os.environ.get("QUANT_LAB_LLM_IDEATION", "0").strip() == "1":
            try:
                hypothesis = self._generate_with_llm(asset_norm, target_interval, negative_constraints, market_regime)
                if hypothesis:
                    return hypothesis
            except Exception as e:
                logger.warning(f"[AlphaIdeator] LLM ideation failed: {e}. Falling back to quantitative generator.")

        # Fallback to deterministic quantitative generator
        return self._generate_rule_based(asset_norm, target_interval, negative_constraints, market_regime=market_regime)

    def _is_sports(self, asset: str) -> bool:
        a = str(asset or "").strip().upper()
        return a in {
            "SPORTS", "SPORT", "NFL", "MLB", "NBA", "NHL", "NPB", "KBO", "NPB/KBO", "NPB_KBO", "NPB-KBO",
            "SOC", "SOCCER", "UFC", "MMA", "TEN", "TENNIS", "ALL", "WNBA", "NCAAF", "NCAAB",
            "EPL", "MLS", "BUNDESLIGA", "LALIGA", "SERIEA"
        }

    def _generate_with_llm(
        self,
        asset: str,
        target_interval: str,
        negative_constraints: List[str],
        regime: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        import urllib.request
        import urllib.error

        negative_text = "\n".join(negative_constraints) if negative_constraints else "None recorded yet."
        regime_str = json.dumps(regime or {"general_volatility": "normal", "session": "active"})
        is_sports = self._is_sports(asset)

        if is_sports:
            prompt = f"""You are a Senior Quantitative Sports Trading Strategist developing algorithmic prediction models for {asset} on Kalshi binary markets.
Return ONLY a valid JSON object defining an innovative, robust sports trading hypothesis.

CRITICAL: DO NOT repeat any of the following failed sports strategies recorded in our Strategy Graveyard:
{negative_text}

Current Market / Slate Context:
{regime_str}

Available indicators / features in sports snapshots (market-only, measured 12h before close; prices in DOLLARS 0.01-0.99):
- market_bid, market_ask: Kalshi YES bid/ask in dollars (e.g. 0.42 / 0.45)
- market_mid: midpoint price in dollars (implied win probability)
- spread: ask minus bid in dollars
- price_drift: change in mid price over the prior 12h in dollars (e.g. -0.08 to +0.08)
- ai_win_prob: AI Model projected win probability (50.0 to 90.0%)
- ai_edge: AI Model edge over Kalshi market midpoint (e.g. -15.0% to +15.0%)
- confidence_score: AI Model confidence metric (0.0 to 30.0; typical values 3.0 to 20.0, DO NOT require > 25.0)
- sim_score: Empirical simulation disparity metric
NOTE ON SIGNAL FREQUENCY: Keep rules FOCUSED and SIMPLE (max 2 to 3 entry conditions). DO NOT over-constrain with too many stacked gates (e.g. combining market_mid, price_drift, ai_edge, confidence_score, and spread simultaneously will produce zero signals). Prefer either market-level edge (mid, drift, spread) OR model discrepancy (ai_edge, ai_win_prob).

Required JSON structure:
{{
  "name": "Concise Descriptive Strategy Name",
  "hypothesis": "1-2 sentence core sports statistical edge rationale",
  "asset": "{asset}",
  "target_interval": "{target_interval}",
  "style": "FAVORITE_LONGSHOT | DRIFT_MOMENTUM | DRIFT_REVERSION | SPREAD_EFFICIENCY",
  "target_side": "YES | NO",
  "entry_conditions": [
    {{"indicator": "market_mid", "operator": "<=", "threshold": 0.30}},
    {{"indicator": "price_drift", "operator": "<", "threshold": -0.04}},
    {{"indicator": "spread", "operator": "<=", "threshold": 0.04}}
  ],
  "max_entry_price": 0.70,
  "min_entry_price": 0.05,
  "take_profit_pct": 35.0,
  "stop_loss_pct": 25.0
}}
"""
        else:
            # Asset-specific benchmark thresholds for realistic prompt guidance
            atr_ref = "100 to 300 on BTC, 5 to 20 on ETH, 0.10 to 0.60 on SOL, 0.0001 to 0.0005 on DOGE, 0.0002 to 0.0008 on EURUSD"
            cvd_ref = "-50 to +50 on BTC, -500 to +500 on ETH, -5000 to +5000 on SOL, -5000000 to +5000000 on DOGE"
            prompt = f"""You are a Senior Quantitative Researcher developing binary prediction strategies for {asset} ({target_interval} contracts).
Return ONLY a valid JSON object defining an innovative, robust trading hypothesis.

CRITICAL: DO NOT repeat any of the following failed strategies recorded in our Strategy Graveyard:
{negative_text}

Current Market Regime Context:
{regime_str}

Available indicators in market snapshots:
- rsi: Relative Strength Index (0 to 100)
- atr: Average True Range in dollars (asset scale benchmark: {atr_ref})
- cvd: Cumulative Volume Delta (buying/selling pressure in units, asset scale benchmark: {cvd_ref})
- ema_fast: 9-period EMA price in dollars (e.g. around current spot price)
- ema_slow: 21-period EMA price in dollars
- ema_trend: 50-period EMA price in dollars
- bb_upper, bb_lower: Bollinger Bands price in dollars
- delta_to_target: Distance from current spot price to strike in dollars
- spread: Bid-ask spread in cents (e.g. 1 to 5)
NOTE: For EMA comparisons, compare against another EMA indicator (e.g. ema_fast > ema_slow).
NOTE on CVD: Cumulative Volume Delta is an unbounded running sum in base currency units whose baseline can drift deeply negative (e.g. -100k on SOL, -40M on DOGE). DO NOT require cvd > 0.0 or positive cvd as a hard filter on altcoins. Prefer relative indicators like rsi, ema_fast vs ema_slow, atr, or bb_upper/bb_lower.
NOTE ON SIGNAL FREQUENCY: Keep rules FOCUSED and SIMPLE (max 2 to 3 entry conditions). NEVER combine contradictory conditions (e.g., DO NOT require oversold RSI < 38 AND bullish EMA cross ema_fast > ema_slow simultaneously, as this almost never occurs and produces 0 signals). Do NOT over-constrain with too many stacked gates.
For binary contract prices, Kalshi quotes range from 0.01 to 0.99 (use inclusive corridors such as min_entry_price: 0.15, max_entry_price: 0.85).

Required JSON structure:
{{
  "name": "Concise Descriptive Strategy Name",
  "hypothesis": "1-2 sentence core economic/statistical rationale",
  "asset": "{asset}",
  "target_interval": "{target_interval}",
  "style": "MOMENTUM | MEAN_REVERSION | VOLATILITY_BREAKOUT | ORDERBOOK_IMBALANCE",
  "target_side": "YES | NO",
  "entry_conditions": [
    {{"indicator": "rsi", "operator": "<", "threshold": 42.0}},
    {{"indicator": "atr", "operator": ">", "threshold": 25.0}}
  ],
  "max_entry_price": 0.85,
  "min_entry_price": 0.15,
  "take_profit_pct": 35.0,
  "stop_loss_pct": 25.0
}}
"""
        env_model = os.environ.get("GEMINI_MODEL")
        models = ([env_model] if env_model and not any(x in env_model for x in ("1.5", "2.5")) else []) + ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-flash-lite-latest"]
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4000}
        }
        last_err: Optional[Exception] = None
        for model_name in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=30.0) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                    text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text.startswith("```json"):
                        text = text[7:]
                    if text.startswith("```"):
                        text = text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    data = json.loads(text.strip())
                    data["strategy_id"] = f"strat_{uuid.uuid4().hex[:8]}"

                    # Post-generation hygiene: protect against low-signal pathology
                    if not is_sports:
                        # 1. Enforce wide contract price corridors
                        data["min_entry_price"] = min(float(data.get("min_entry_price", 0.15)), 0.20)
                        data["max_entry_price"] = max(float(data.get("max_entry_price", 0.85)), 0.80)

                        # 2. Prevent altcoins from using positive cvd thresholds and fix numeric EMA thresholds
                        conds = data.get("entry_conditions") or []
                        cleaned_conds = []
                        for c in conds:
                            ind = str(c.get("indicator", "")).lower()
                            thresh = c.get("threshold")
                            if ind == "cvd" and asset.upper() in ("SOL", "DOGE", "ETH"):
                                # CVD baselines drift deeply negative on altcoins; remove or soften
                                continue
                            if ind in ("ema_fast", "ema_slow", "ema_trend") and isinstance(thresh, (int, float)):
                                # LLM mistakenly compared EMA to a numeric period (e.g. > 21.0) instead of another EMA indicator
                                c["threshold"] = "ema_slow" if ind == "ema_fast" else "ema_trend"

                            # Handle Bollinger Bands threshold hygiene
                            if ind in ("bb_lower", "bb_upper"):
                                try:
                                    f_t = float(thresh)
                                    if f_t <= 10.0:
                                        c["indicator"] = "bb_percent_b"
                                        c["threshold"] = 0.15 if ind == "bb_lower" else 0.85
                                except Exception:
                                    pass

                            # Handle ATR scale hygiene per asset
                            if ind == "atr":
                                try:
                                    f_t = float(thresh)
                                    if asset.upper() == "BTC" and f_t > 300.0:
                                        c["threshold"] = 150.0
                                    elif asset.upper() == "ETH" and f_t > 30.0:
                                        c["threshold"] = 10.0
                                    elif asset.upper() in ("SOL", "GOLD") and f_t > 2.0:
                                        c["threshold"] = 0.25
                                    elif asset.upper() in ("DOGE", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY") and f_t > 0.01:
                                        c["threshold"] = 0.0002
                                except Exception:
                                    pass

                            cleaned_conds.append(c)

                        # 3. Limit to top 3 conditions to prevent over-constraining
                        if len(cleaned_conds) > 3:
                            cleaned_conds = cleaned_conds[:3]
                        data["entry_conditions"] = cleaned_conds
                    else:
                        # For sports: ensure confidence_score threshold is not unattainable
                        conds = data.get("entry_conditions") or []
                        cleaned_sports = []
                        for c in conds:
                            if str(c.get("indicator", "")).lower() == "confidence_score":
                                try:
                                    if float(c.get("threshold", 0)) > 25.0:
                                        c["threshold"] = 12.0
                                except Exception:
                                    pass
                            cleaned_sports.append(c)
                        # Cap at 3 conditions to prevent over-constraining
                        if len(cleaned_sports) > 3:
                            cleaned_sports = cleaned_sports[:3]
                        data["entry_conditions"] = cleaned_sports
                        data["min_entry_price"] = min(float(data.get("min_entry_price", 0.05)), 0.10)
                        data["max_entry_price"] = max(float(data.get("max_entry_price", 0.70)), 0.75)

                    # Ensure target_regimes and base_edge are populated
                    if "target_regimes" not in data or not data["target_regimes"]:
                        style = str(data.get("style", "")).upper()
                        if "MOMENTUM" in style or "BREAKOUT" in style:
                            data["target_regimes"] = ["TREND_EXPANSION_MOMENTUM"]
                            data["conditioned_regime"] = "Trend-Expansion/Momentum"
                        elif "REVERSION" in style or "LONGSHOT" in style:
                            data["target_regimes"] = ["COMPRESSION_MEAN_REVERSION"]
                            data["conditioned_regime"] = "Compression/Mean-Reversion"
                        else:
                            data["target_regimes"] = ["COMPRESSION_MEAN_REVERSION", "TREND_EXPANSION_MOMENTUM"]
                            data["conditioned_regime"] = "Compression/Mean-Reversion"
                    if "base_edge" not in data:
                        data["base_edge"] = 0.06

                    return data
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (404, 429, 500, 503):
                    continue  # try next model
                raise
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise last_err
        return None

    def _generate_rule_based(
        self,
        asset: str,
        target_interval: str,
        negative_constraints: List[str],
        market_regime: Optional[Dict[str, Any] | str] = None
    ) -> Dict[str, Any]:
        """Deterministic quantitative hypothesis generator that respects negative constraints and detected market regime."""
        neg_text = " ".join(negative_constraints).lower()
        candidates = []

        # Extract normalized detected regime string/slug
        reg_slug = ""
        if isinstance(market_regime, dict):
            reg_slug = str(market_regime.get("regime_slug") or market_regime.get("regime") or market_regime.get("market_regime") or "").upper()
        elif isinstance(market_regime, str):
            reg_slug = str(market_regime).upper()

        # Sports Universe Strategy Archetypes
        if self._is_sports(asset):
            # Market-only archetypes (testable on real settled-market history)
            if "underdog value" not in neg_text:
                candidates.append({
                    "name": f"{asset} Underdog Value 20-40c",
                    "hypothesis": "YES contracts priced 20-40c win more often than their implied probability (favorite-longshot bias); buy YES in that band on a tight spread.",
                    "style": "FAVORITE_LONGSHOT",
                    "target_side": "YES",
                    "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
                    "conditioned_regime": "Compression/Mean-Reversion",
                    "base_edge": 0.06,
                    "entry_conditions": [
                        {"indicator": "market_mid", "operator": ">=", "threshold": 0.20},
                        {"indicator": "market_mid", "operator": "<=", "threshold": 0.40},
                        {"indicator": "spread", "operator": "<=", "threshold": 0.05}
                    ],
                    "max_entry_price": 0.42, "min_entry_price": 0.18,
                    "take_profit_pct": 35.0, "stop_loss_pct": 25.0
                })
            if "favorite fade" not in neg_text:
                candidates.append({
                    "name": f"{asset} Mid Favorite Fade 60-80c",
                    "hypothesis": "60-80c favorites are overpriced versus how often they win; buy NO when the YES mid is in that band.",
                    "style": "FAVORITE_LONGSHOT",
                    "target_side": "NO",
                    "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
                    "conditioned_regime": "Compression/Mean-Reversion",
                    "base_edge": 0.06,
                    "entry_conditions": [
                        {"indicator": "market_mid", "operator": ">=", "threshold": 0.60},
                        {"indicator": "market_mid", "operator": "<=", "threshold": 0.80},
                        {"indicator": "spread", "operator": "<=", "threshold": 0.05}
                    ],
                    "max_entry_price": 0.99, "min_entry_price": 0.01,
                    "take_profit_pct": 35.0, "stop_loss_pct": 25.0
                })

            if "longshot" not in neg_text:
                candidates.append({
                    "name": f"{asset} Longshot Overreaction Fade",
                    "hypothesis": "Cheap YES contracts whose price just fell sharply are over-sold; buy YES when price drops on a tight spread.",
                    "style": "DRIFT_REVERSION",
                    "target_side": "YES",
                    "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
                    "conditioned_regime": "Compression/Mean-Reversion",
                    "base_edge": 0.06,
                    "entry_conditions": [
                        {"indicator": "market_mid", "operator": "<=", "threshold": 0.35},
                        {"indicator": "price_drift", "operator": "<", "threshold": -0.04},
                        {"indicator": "spread", "operator": "<=", "threshold": 0.05}
                    ],
                    "max_entry_price": 0.40, "min_entry_price": 0.05,
                    "take_profit_pct": 35.0, "stop_loss_pct": 25.0
                })
            if "steam" not in neg_text:
                candidates.append({
                    "name": f"{asset} Favorite Steam Momentum",
                    "hypothesis": "Favorites whose price has been rising into the game continue to be underpriced; buy YES on positive drift.",
                    "style": "DRIFT_MOMENTUM",
                    "target_side": "YES",
                    "target_regimes": ["TREND_EXPANSION_MOMENTUM"],
                    "conditioned_regime": "Trend-Expansion/Momentum",
                    "base_edge": 0.07,
                    "entry_conditions": [
                        {"indicator": "market_mid", "operator": ">=", "threshold": 0.55},
                        {"indicator": "price_drift", "operator": ">", "threshold": 0.03},
                        {"indicator": "spread", "operator": "<=", "threshold": 0.04}
                    ],
                    "max_entry_price": 0.80, "min_entry_price": 0.55,
                    "take_profit_pct": 25.0, "stop_loss_pct": 25.0
                })
            if "overpriced favorite" not in neg_text:
                candidates.append({
                    "name": f"{asset} Overpriced Heavy Favorite Fade",
                    "hypothesis": "Heavy favorites priced above 80c are overpaid; buy NO when the YES ask is very high.",
                    "style": "FAVORITE_LONGSHOT",
                    "target_side": "NO",
                    "target_regimes": ["HIGH_WHIPSAW_EVENT_RISK", "COMPRESSION_MEAN_REVERSION"],
                    "conditioned_regime": "High-Whipsaw/Event-Risk",
                    "base_edge": 0.07,
                    "entry_conditions": [
                        {"indicator": "market_ask", "operator": ">=", "threshold": 0.80},
                        {"indicator": "spread", "operator": "<=", "threshold": 0.05}
                    ],
                    "max_entry_price": 0.99, "min_entry_price": 0.78,
                    "take_profit_pct": 35.0, "stop_loss_pct": 25.0
                })

            # Sports Archetype 1: High Model Edge vs Market Mispricing
            if "edge" not in neg_text or "misprice" not in neg_text:
                candidates.append({
                    "name": f"{asset} High AI Model Edge Capture",
                    "hypothesis": f"When ApexProps simulation detects an edge >= 4.5% against Kalshi line with win probability >= 58%, execute YES within the 35c-65c corridor.",
                    "style": "MODEL_DISCREPANCY",
                    "target_side": "YES",
                    "target_regimes": ["TREND_EXPANSION_MOMENTUM", "HIGH_WHIPSAW_EVENT_RISK"],
                    "conditioned_regime": "Trend-Expansion/Momentum",
                    "base_edge": 0.08,
                    "entry_conditions": [
                        {"indicator": "ai_edge", "operator": ">=", "threshold": 4.5},
                        {"indicator": "ai_win_prob", "operator": ">=", "threshold": 58.0}
                    ],
                    "max_entry_price": 0.65,
                    "min_entry_price": 0.35,
                    "take_profit_pct": 35.0,
                    "stop_loss_pct": 25.0
                })

            # Sports Archetype 2: Heavy Favorite Regression Fade
            if "favorite" not in neg_text and "fade" not in neg_text:
                candidates.append({
                    "name": f"{asset} Overheated Favorite Value Fade",
                    "hypothesis": f"When a public favorite is bid above 75c but simulation model projects < 68% probability (negative edge), buy NO for asymmetric risk-reward.",
                    "style": "UNDERDOG_SHARP_EDGE",
                    "target_side": "NO",
                    "target_regimes": ["HIGH_WHIPSAW_EVENT_RISK", "COMPRESSION_MEAN_REVERSION"],
                    "conditioned_regime": "High-Whipsaw/Event-Risk",
                    "base_edge": 0.07,
                    "entry_conditions": [
                        {"indicator": "ai_edge", "operator": "<=", "threshold": -3.0},
                        {"indicator": "market_bid", "operator": ">=", "threshold": 0.74}
                    ],
                    "max_entry_price": 0.65,
                    "min_entry_price": 0.25,
                    "take_profit_pct": 40.0,
                    "stop_loss_pct": 25.0
                })

            # Sports Archetype 3: Situational Rest & Pitcher/Goaltender Advantage
            if "rest" not in neg_text or "advantage" not in neg_text:
                candidates.append({
                    "name": f"{asset} Situational Rest & Matchup Alpha",
                    "hypothesis": f"When team possesses positive rest days advantage and starting matchup score is favorable, enter YES with conservative line friction.",
                    "style": "SITUATIONAL_REST",
                    "target_side": "YES",
                    "target_regimes": ["COMPRESSION_MEAN_REVERSION", "TREND_EXPANSION_MOMENTUM"],
                    "conditioned_regime": "Compression/Mean-Reversion",
                    "base_edge": 0.06,
                    "entry_conditions": [
                        {"indicator": "ai_edge", "operator": ">=", "threshold": 3.0},
                        {"indicator": "confidence_score", "operator": ">=", "threshold": 10.0}
                    ],
                    "max_entry_price": 0.68,
                    "min_entry_price": 0.40,
                    "take_profit_pct": 30.0,
                    "stop_loss_pct": 20.0
                })

            # Sports Archetype 4: Weather Totals Suppression
            candidates.append({
                "name": f"{asset} Outdoor Weather Suppressed Total",
                "hypothesis": f"When weather impacts project scoring reduction and AI model identifies an under edge >= 4.0%, take the UNDER side.",
                "style": "WEATHER_IMPACT",
                "target_side": "NO",
                "target_regimes": ["HIGH_WHIPSAW_EVENT_RISK", "COMPRESSION_MEAN_REVERSION"],
                "conditioned_regime": "High-Whipsaw/Event-Risk",
                "base_edge": 0.06,
                "entry_conditions": [
                    {"indicator": "ai_edge", "operator": ">=", "threshold": 4.0},
                    {"indicator": "ai_win_prob", "operator": ">=", "threshold": 55.0}
                ],
                "max_entry_price": 0.62,
                "min_entry_price": 0.38,
                "take_profit_pct": 35.0,
                "stop_loss_pct": 25.0
            })

            # Condition selection on detected regime if applicable
            if reg_slug:
                norm_reg = reg_slug.replace("/", "_").replace("-", "_").replace(" ", "_")
                matching = [
                    c for c in candidates
                    if any(
                        (r.replace("/", "_").replace("-", "_").replace(" ", "_") in norm_reg) or
                        (norm_reg in r.replace("/", "_").replace("-", "_").replace(" ", "_"))
                        for r in c.get("target_regimes", [])
                    )
                ]
                if matching:
                    candidates = matching

            chosen = random.choice(candidates)
            chosen["strategy_id"] = f"strat_{uuid.uuid4().hex[:8]}"
            chosen["asset"] = asset
            chosen["target_interval"] = target_interval
            return chosen

        # Financial Universe Strategy Archetypes: calibrate scale per asset
        if asset == "BTC":
            atr_min = 25.0
        elif asset == "ETH":
            atr_min = 2.0
        elif asset == "SOL":
            atr_min = 0.05
        elif asset == "DOGE":
            atr_min = 0.00005
        elif asset in ("EURUSD", "GBPUSD", "AUDUSD"):
            atr_min = 0.0001
        else:
            atr_min = 0.00005

        # Archetype 1: Oversold Reversal with Trend / RSI Confirmation
        if "oversold" not in neg_text:
            candidates.append({
                "name": f"{asset} 15M Bullish Absorption Reversal",
                "hypothesis": f"When {asset} dips into oversold RSI with volatility expansion, enter YES ahead of mean reversion.",
                "style": "MEAN_REVERSION",
                "target_side": "YES",
                "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
                "conditioned_regime": "Compression/Mean-Reversion",
                "base_edge": 0.06,
                "entry_conditions": [
                    {"indicator": "rsi", "operator": "<", "threshold": 44.0},
                    {"indicator": "atr", "operator": ">", "threshold": atr_min}
                ],
                "max_entry_price": 0.85,
                "min_entry_price": 0.15,
                "take_profit_pct": 35.0,
                "stop_loss_pct": 25.0
            })

        # Archetype 2: Trend-Continuation EMA Pullback
        if "pullback" not in neg_text or "ema" not in neg_text:
            candidates.append({
                "name": f"{asset} 15M Trend Continuation Momentum",
                "hypothesis": f"When {asset} fast EMA is above slow EMA and RSI is in the bullish expansion zone (48-68), buy YES on pullback.",
                "style": "MOMENTUM",
                "target_side": "YES",
                "target_regimes": ["TREND_EXPANSION_MOMENTUM"],
                "conditioned_regime": "Trend-Expansion/Momentum",
                "base_edge": 0.07,
                "entry_conditions": [
                    {"indicator": "rsi", "operator": ">", "threshold": 48.0},
                    {"indicator": "rsi", "operator": "<", "threshold": 68.0},
                    {"indicator": "ema_fast", "operator": ">=", "threshold": "ema_slow"},
                    {"indicator": "atr", "operator": ">", "threshold": atr_min}
                ],
                "max_entry_price": 0.85,
                "min_entry_price": 0.15,
                "take_profit_pct": 30.0,
                "stop_loss_pct": 25.0
            })

        # Archetype 3: Overbought Bearish Exhaustion Pin
        if "overbought" not in neg_text:
            candidates.append({
                "name": f"{asset} 15M Overbought Exhaustion Fade",
                "hypothesis": f"When {asset} reaches overbought RSI with expanding volatility, buy NO as upward momentum stalls.",
                "style": "MEAN_REVERSION",
                "target_side": "NO",
                "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
                "conditioned_regime": "Compression/Mean-Reversion",
                "base_edge": 0.06,
                "entry_conditions": [
                    {"indicator": "rsi", "operator": ">", "threshold": 60.0},
                    {"indicator": "atr", "operator": ">", "threshold": atr_min}
                ],
                "max_entry_price": 0.85,
                "min_entry_price": 0.15,
                "take_profit_pct": 35.0,
                "stop_loss_pct": 25.0
            })

        # Archetype 4: Bollinger Band Volatility Squeeze Expansion
        candidates.append({
            "name": f"{asset} 15M Bollinger Expansion Breakout",
            "hypothesis": f"When {asset} expands above baseline momentum with expanding ATR, take YES for expansion continuation.",
            "style": "VOLATILITY_BREAKOUT",
            "target_side": "YES",
            "target_regimes": ["TREND_EXPANSION_MOMENTUM", "HIGH_WHIPSAW_EVENT_RISK"],
            "conditioned_regime": "Trend-Expansion/Momentum",
            "base_edge": 0.08,
            "entry_conditions": [
                {"indicator": "rsi", "operator": ">", "threshold": 52.0},
                {"indicator": "atr", "operator": ">", "threshold": atr_min}
            ],
            "max_entry_price": 0.85,
            "min_entry_price": 0.15,
            "take_profit_pct": 40.0,
            "stop_loss_pct": 30.0
        })

        # Condition selection on detected regime if applicable
        if reg_slug:
            norm_reg = reg_slug.replace("/", "_").replace("-", "_").replace(" ", "_")
            matching = [
                c for c in candidates
                if any(
                    (r.replace("/", "_").replace("-", "_").replace(" ", "_") in norm_reg) or
                    (norm_reg in r.replace("/", "_").replace("-", "_").replace(" ", "_"))
                    for r in c.get("target_regimes", [])
                )
            ]
            if matching:
                candidates = matching

        chosen = random.choice(candidates)
        chosen["strategy_id"] = f"strat_{uuid.uuid4().hex[:8]}"
        chosen["asset"] = asset
        chosen["target_interval"] = target_interval
        return chosen

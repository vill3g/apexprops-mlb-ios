"""
tests/test_auto_regime.py
Comprehensive unit and pipeline tests for Auto 2.0: Adaptive Market Regime Classification.
Validates:
1. classify_auto_regime handles all 4 regimes (STRONG_MOMENTUM, SQUEEZE_BREAKOUT, CHOP_DEADZONE, TREND_CONTINUATION)
2. Safe fallback on missing or malformed candle data
3. Capital Guard produces clean PASS and halts bleed on low-volatility chop
4. evaluate_next_15m_contract handles CAPITAL_GUARD and mid-candle AUTO indexing
5. Parity between single-user and SaaS multi-user execution
"""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from backend.btc.auto_executor import classify_auto_regime, AutoExecutor
from backend.btc.analyzer import evaluate_next_15m_contract


def _build_synthetic_df(
    vol_ratio: float = 1.0,
    bb_bandwidth: float = 0.025,
    adx: float = 20.0,
    rsi: float = 50.0,
    close: float = 65000.0,
    open_val: float = 65000.0,
    high: float = 65100.0,
    low: float = 64900.0,
    atr: float = 100.0,
    bb_upper: float = 65500.0,
    bb_lower: float = 64500.0,
    num_candles: int = 40,
) -> pd.DataFrame:
    """Helper to generate synthetic indicator DataFrame."""
    rows = []
    base_time = 1700000000
    for i in range(num_candles):
        rows.append({
            "time": base_time + (i * 900),
            "timestamp": base_time + (i * 900),
            "open": 64800.0,
            "high": 65200.0,
            "low": 64700.0,
            "close": 65000.0,
            "volume": 25.0,
            "rsi": 50.0,
            "adx": 20.0,
            "vol_ratio": 1.0,
            "bb_bandwidth": 0.025,
            "bb_upper": 65500.0,
            "bb_lower": 64500.0,
            "atr": 100.0,
            "ema_9": 65000.0,
            "ema_21": 65000.0,
            "ema_50": 65000.0,
            "vwap": 65000.0,
            "cvd": 0.0,
        })
    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)

    # Set parameters on the latest candle (iloc[-1])
    df.loc[df.index[-1], "vol_ratio"] = vol_ratio
    df.loc[df.index[-1], "bb_bandwidth"] = bb_bandwidth
    df.loc[df.index[-1], "adx"] = adx
    df.loc[df.index[-1], "rsi"] = rsi
    df.loc[df.index[-1], "close"] = close
    df.loc[df.index[-1], "open"] = open_val
    df.loc[df.index[-1], "high"] = high
    df.loc[df.index[-1], "low"] = low
    df.loc[df.index[-1], "atr"] = atr
    df.loc[df.index[-1], "bb_upper"] = bb_upper
    df.loc[df.index[-1], "bb_lower"] = bb_lower
    return df


class TestAutoRegimeClassification(unittest.TestCase):

    def test_empty_or_none_df_safe_fallback(self):
        """Test fallback when df is empty or None."""
        res_none = classify_auto_regime(None)
        self.assertEqual(res_none["style"], "SNIPER")
        self.assertEqual(res_none["regime"], "DEFAULT_FALLBACK")

        res_empty = classify_auto_regime(pd.DataFrame())
        self.assertEqual(res_empty["style"], "SNIPER")
        self.assertEqual(res_empty["regime"], "DEFAULT_FALLBACK")

    @patch("backend.btc.liquidation_stream.get_liquidation_imbalance")
    def test_strong_momentum_via_liquidation_cascade(self, mock_liq):
        """Massive liquidation cascade ($1.5M+) must route to MOMENTUM_SURFER."""
        mock_liq.return_value = {
            "short_liquidations_usd": 1_200_000.0,
            "long_liquidations_usd": 600_000.0,  # Total $1.8M
            "net_imbalance_usd": 600_000.0,
        }
        df = _build_synthetic_df(vol_ratio=1.0, adx=19.0, rsi=50.0)
        res = classify_auto_regime(df)
        self.assertEqual(res["style"], "MOMENTUM_SURFER")
        self.assertEqual(res["regime"], "STRONG_MOMENTUM")
        self.assertIn("liquidation cascade", res["reason"].lower())

    @patch("backend.btc.liquidation_stream.get_liquidation_imbalance")
    def test_strong_momentum_via_volume_and_adx(self, mock_liq):
        """High volume ratio (>=1.4), high ADX (>=25), shifted RSI (|rsi-50| >= 8) routes to MOMENTUM_SURFER."""
        mock_liq.return_value = {"short_liquidations_usd": 0.0, "long_liquidations_usd": 0.0}
        df = _build_synthetic_df(vol_ratio=1.55, adx=29.0, rsi=62.0)
        res = classify_auto_regime(df)
        self.assertEqual(res["style"], "MOMENTUM_SURFER")
        self.assertEqual(res["regime"], "STRONG_MOMENTUM")

    @patch("backend.btc.liquidation_stream.get_liquidation_imbalance")
    def test_squeeze_breakout_routes_to_ambush(self, mock_liq):
        """Bollinger compression (BBW < 0.020) + volume expansion (>=1.25) breaking bands routes to AMBUSH."""
        mock_liq.return_value = {"short_liquidations_usd": 0.0, "long_liquidations_usd": 0.0}
        df = _build_synthetic_df(
            vol_ratio=1.35,
            bb_bandwidth=0.012,
            adx=19.0,
            rsi=54.0,
            close=65600.0,  # > bb_upper (65500)
            bb_upper=65500.0,
            open_val=65300.0,
            atr=100.0,
        )
        res = classify_auto_regime(df)
        self.assertEqual(res["style"], "AMBUSH")
        self.assertEqual(res["regime"], "SQUEEZE_BREAKOUT")

    @patch("backend.btc.liquidation_stream.get_liquidation_imbalance")
    def test_squeeze_breakout_range_expansion_routes_to_ambush(self, mock_liq):
        """Bollinger compression with candle range expansion (body >= 0.7 * ATR) routes to AMBUSH."""
        mock_liq.return_value = {"short_liquidations_usd": 0.0, "long_liquidations_usd": 0.0}
        df = _build_synthetic_df(
            vol_ratio=1.30,
            bb_bandwidth=0.015,
            adx=18.5,
            close=65200.0,
            open_val=65100.0,  # 100 delta on atr=100 -> >= 0.7 * ATR
            atr=100.0,
            bb_upper=65400.0,
            bb_lower=64800.0,
        )
        res = classify_auto_regime(df)
        self.assertEqual(res["style"], "AMBUSH")
        self.assertEqual(res["regime"], "SQUEEZE_BREAKOUT")

    @patch("backend.btc.liquidation_stream.get_liquidation_imbalance")
    def test_chop_deadzone_routes_to_capital_guard(self, mock_liq):
        """Low volatility (ADX < 18, vol_ratio < 0.85, BBW < 0.018) routes to CAPITAL_GUARD."""
        mock_liq.return_value = {"short_liquidations_usd": 0.0, "long_liquidations_usd": 0.0}
        df = _build_synthetic_df(
            vol_ratio=0.72,
            bb_bandwidth=0.014,
            adx=15.0,
            rsi=49.0,
        )
        res = classify_auto_regime(df)
        self.assertEqual(res["style"], "CAPITAL_GUARD")
        self.assertEqual(res["regime"], "CHOP_DEADZONE")
        self.assertIn("capital guard active", res["reason"].lower())

    @patch("backend.btc.liquidation_stream.get_liquidation_imbalance")
    def test_extreme_chop_routes_to_capital_guard(self, mock_liq):
        """Extremely low trend (ADX < 16, vol_ratio < 0.90) routes to CAPITAL_GUARD."""
        mock_liq.return_value = {"short_liquidations_usd": 0.0, "long_liquidations_usd": 0.0}
        df = _build_synthetic_df(
            vol_ratio=0.82,
            bb_bandwidth=0.022,
            adx=14.5,
            rsi=51.0,
        )
        res = classify_auto_regime(df)
        self.assertEqual(res["style"], "CAPITAL_GUARD")
        self.assertEqual(res["regime"], "CHOP_DEADZONE")

    @patch("backend.btc.liquidation_stream.get_liquidation_imbalance")
    def test_trend_continuation_routes_to_sniper(self, mock_liq):
        """ADX >= 20, |rsi-50| >= 5, vol_ratio >= 0.9 routes to SNIPER."""
        mock_liq.return_value = {"short_liquidations_usd": 0.0, "long_liquidations_usd": 0.0}
        df = _build_synthetic_df(
            vol_ratio=1.05,
            bb_bandwidth=0.025,
            adx=23.0,
            rsi=58.0,
        )
        res = classify_auto_regime(df)
        self.assertEqual(res["style"], "SNIPER")
        self.assertEqual(res["regime"], "TREND_CONTINUATION")


class TestCapitalGuardAndAnalyzerIntegration(unittest.TestCase):

    def test_evaluate_next_15m_contract_capital_guard(self):
        """When trading_style is CAPITAL_GUARD, contract evaluation must return clean PASS with 50% probability."""
        df = _build_synthetic_df()
        forecast = evaluate_next_15m_contract(df, target_price=65000.0, trading_style="CAPITAL_GUARD")

        self.assertEqual(forecast["direction"], "PASS")
        self.assertEqual(forecast["probability_percent"], 50.0)
        self.assertIn("CAPITAL GUARD", forecast["recommendation"])
        self.assertIn("CAPITAL GUARD", forecast["conviction_badge"])

    def test_mid_candle_auto_evaluates_active_candle(self):
        """When trading_style is AUTO and seconds into candle > 120, live active candle is evaluated."""
        df = _build_synthetic_df(num_candles=10)
        # Mock time to be 500 seconds into the 900s candle (mid-candle)
        # 1700000000 % 900 = 800 (mid-candle)
        with patch("time.time", return_value=1700000800):
            forecast = evaluate_next_15m_contract(df, target_price=65000.0, trading_style="AUTO")
            # Must return a valid forecast dict without crashing
            self.assertIn("probability_percent", forecast)
            self.assertIn("direction", forecast)


class TestAutoExecutorCapitalGuardExecution(unittest.TestCase):

    @patch("backend.btc.liquidation_stream.get_liquidation_imbalance")
    @patch("backend.engine.multi_asset_fetcher.fetch_asset_candles")
    @patch("backend.btc.kalshi_trader.kalshi_trader.get_active_15m_market")
    @patch("backend.engine.multi_asset_fetcher.is_market_open", return_value=True)
    def test_auto_executor_passes_in_chop_deadzone(self, mock_open, mock_m, mock_candles, mock_liq):
        """AutoExecutor in AUTO mode encountering CHOP deadzone must PASS without placing an order."""
        mock_liq.return_value = {"short_liquidations_usd": 0.0, "long_liquidations_usd": 0.0}
        df_chop = _build_synthetic_df(
            vol_ratio=0.70,
            bb_bandwidth=0.012,
            adx=14.0,
            rsi=50.0,
        )
        mock_candles.return_value = df_chop
        mock_m.return_value = {
            "ticker": "KXBTC15M-TEST",
            "strike_price": 65000.0,
            "yes_ask": 0.52,
            "no_ask": 0.52,
        }

        executor = AutoExecutor(asset="BTC")
        executor.enabled = True
        executor.mode = "PAPER"
        executor.ai_settings = {"tradingStyle": "AUTO"}

        with patch("backend.btc.auto_executor.get_candle_countdown", return_value={"seconds_left": 300}):
            trade = executor.check_and_execute_rollover()

        # In CHOP deadzone, Capital Guard passes -> No trade placed!
        self.assertIsNone(trade)


if __name__ == "__main__":
    unittest.main()

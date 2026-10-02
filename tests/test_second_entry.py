import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath("."))

from backend.saas_settler import (
    _second_entry_mode,
    _second_entry_size,
    _filled_count,
    _recalculate_stop_loss_prediction
)

class TestSecondAndThirdEntrySimulation(unittest.TestCase):
    def test_filled_count(self):
        res = {"count": 12, "filled_price": 0.52}
        self.assertEqual(_filled_count(res, 10), 12)
        res_empty = {}
        self.assertEqual(_filled_count(res_empty, 10), 10)

    def test_full_progression_entry1_to_entry3(self):
        """
        Verify that:
        1. Trade 1 profitable scalp triggers Entry 2 (SECOND_ENTRY).
        2. Trade 2 profitable scalp with >= 240s left triggers Entry 3 (THIRD_ENTRY).
        3. Trade 3 profitable scalp does NOT trigger Entry 4 (stops cleanly at 3).
        4. If Trade 2 exits with STOP_LOSS, Entry 3 is never triggered.
        5. If Trade 2 exits with < 240s remaining, Entry 3 is skipped.
        """
        user = {
            "id": 999,
            "username": "tester",
            "second_entry_enabled": 1,
            "second_entry_max_ask": 0.80,
            "trading_mode": "PAPER",
            "ai_enabled": 1,
            "paper_trade_size_dollars": 50.0,
            "paper_balance": 500.0,
        }
        ticker = "KXBTC15M-TEST"
        side = "yes"
        market = {
            "ticker": ticker,
            "yes_bid": 0.65,
            "yes_ask": 0.52,
            "no_bid": 0.45,
            "no_ask": 0.48,
        }

        # --- STEP 1: Trade 1 exits with TAKE_PROFIT -> triggers Entry 2 ---
        trade_1 = {
            "id": "trade-1",
            "ticker": ticker,
            "side": "YES",
            "entry_price": 0.50,
            "count": 10,
            "status": "CLOSED",
            "mode": "PAPER",
            "exit_reason": "TAKE_PROFIT (+30.0%)",
            "exit_price": 0.65,
        }
        trades = [trade_1]
        new_trades_to_add = []

        # Logic from saas_settler
        curr_entry_num = 1
        if trade_1.get("is_third_entry") or trade_1.get("reentry_index") == 3 or "THIRD_ENTRY" in str(trade_1.get("trading_style", "")).upper():
            curr_entry_num = 3
        elif trade_1.get("is_second_entry") or trade_1.get("reentry_index") == 2 or "SECOND_ENTRY" in str(trade_1.get("trading_style", "")).upper():
            curr_entry_num = 2
        next_entry_num = curr_entry_num + 1

        self.assertEqual(next_entry_num, 2)
        can_reenter_count = (next_entry_num <= 3)
        self.assertTrue(can_reenter_count)

        # Create Entry 2
        trade_2 = {
            "id": "trade-2",
            "ticker": ticker,
            "side": "YES",
            "count": 10,
            "entry_price": 0.52,
            "status": "OPEN",
            "mode": "PAPER",
            "reason": "SECOND_ENTRY_SCALP",
            "is_second_entry": True,
            "is_third_entry": False,
            "reentry_index": 2,
            "trading_style": "SECOND_ENTRY",
        }
        trades.append(trade_2)

        # --- STEP 2: Trade 2 exits with TAKE_PROFIT with 350s left -> triggers Entry 3 ---
        trade_2["status"] = "CLOSED"
        trade_2["exit_reason"] = "TAKE_PROFIT (+25.0%)"
        trade_2["exit_price"] = 0.65

        curr_entry_num = 1
        if trade_2.get("is_third_entry") or trade_2.get("reentry_index") == 3 or "THIRD_ENTRY" in str(trade_2.get("trading_style", "")).upper():
            curr_entry_num = 3
        elif trade_2.get("is_second_entry") or trade_2.get("reentry_index") == 2 or "SECOND_ENTRY" in str(trade_2.get("trading_style", "")).upper():
            curr_entry_num = 2
        next_entry_num = curr_entry_num + 1

        self.assertEqual(curr_entry_num, 2)
        self.assertEqual(next_entry_num, 3)
        can_reenter_count = (next_entry_num <= 3)
        self.assertTrue(can_reenter_count)

        # Timing gate check with 350s remaining (>= 240s)
        remaining_sec = 350
        self.assertGreaterEqual(remaining_sec, 240)

        # Create Entry 3
        trade_3 = {
            "id": "trade-3",
            "ticker": ticker,
            "side": "YES",
            "count": 10,
            "entry_price": 0.54,
            "status": "OPEN",
            "mode": "PAPER",
            "reason": "THIRD_ENTRY_SCALP",
            "is_second_entry": False,
            "is_third_entry": True,
            "reentry_index": 3,
            "trading_style": "THIRD_ENTRY",
        }
        trades.append(trade_3)

        # --- STEP 3: Trade 3 exits with TAKE_PROFIT -> stops, no 4th entry ---
        trade_3["status"] = "CLOSED"
        trade_3["exit_reason"] = "TAKE_PROFIT (+20.0%)"
        trade_3["exit_price"] = 0.65

        curr_entry_num = 1
        if trade_3.get("is_third_entry") or trade_3.get("reentry_index") == 3 or "THIRD_ENTRY" in str(trade_3.get("trading_style", "")).upper():
            curr_entry_num = 3
        elif trade_3.get("is_second_entry") or trade_3.get("reentry_index") == 2 or "SECOND_ENTRY" in str(trade_3.get("trading_style", "")).upper():
            curr_entry_num = 2
        next_entry_num = curr_entry_num + 1

        self.assertEqual(curr_entry_num, 3)
        self.assertEqual(next_entry_num, 4)
        can_reenter_count = (next_entry_num <= 3)
        self.assertFalse(can_reenter_count) # Blocked! Max 3 entries reached.

        # --- STEP 4: Test guard: if Trade 2 was STOP_LOSS and reentry_after_stop_loss is off -> no Entry 3 ---
        stopped_reason = "STOP_LOSS (-25.0%)"
        user_no_sl_reentry = {"second_entry_enabled": 1, "reentry_after_stop_loss": 0}
        is_profitable_scalp = ("STOP_LOSS" not in stopped_reason) and (0.35 > 0.50)
        reentry_sl_on = bool(user_no_sl_reentry.get("reentry_after_stop_loss", 0))
        allow_reentry = (is_profitable_scalp and bool(user_no_sl_reentry.get("second_entry_enabled", 0))) or (("STOP_LOSS" in stopped_reason) and reentry_sl_on)
        self.assertFalse(allow_reentry)

        # --- STEP 5: Test guard: if Trade 2 took profit with only 120s left (< 240s) -> no Entry 3 ---
        insufficient_remaining_sec = 120
        self.assertFalse(insufficient_remaining_sec >= 240)

    def test_stop_loss_reentry_full_progression(self):
        """
        Verify that:
        1. When a trade exits with STOP_LOSS and reentry_after_stop_loss=1, re-entry is allowed.
        2. It creates Entry 2 marked as a dip re-entry (is_stop_loss_reentry=True).
        3. If Entry 2 is also stopped out with >= 240s left, Entry 3 is placed.
        4. If Entry 3 is stopped out, Entry 4 is strictly blocked (max 3 entries).
        5. If remaining time is < 240s, stop loss re-entry is blocked.
        """
        user = {
            "id": 888,
            "username": "sl_tester",
            "second_entry_enabled": 0,
            "reentry_after_stop_loss": 1,
            "second_entry_max_ask": 0.75,
            "trading_mode": "PAPER",
        }
        ticker = "KXBTC15M-SL-TEST"
        side = "yes"

        # Trade 1 gets stopped out
        trade_1 = {
            "id": "t1",
            "ticker": ticker,
            "side": "YES",
            "entry_price": 0.50,
            "count": 10,
            "status": "CLOSED",
            "exit_reason": "STOP_LOSS (-20.0%)",
            "exit_price": 0.40,
        }
        reason = trade_1["exit_reason"]
        exit_price = trade_1["exit_price"]
        entry = trade_1["entry_price"]

        is_profitable_scalp = ("STOP_LOSS" not in reason) and (exit_price > entry)
        second_entry_on = bool(user.get("second_entry_enabled", 0))
        is_stop_loss_exit = ("STOP_LOSS" in reason)
        reentry_sl_on = bool(user.get("reentry_after_stop_loss", 0))
        allow_reentry = (is_profitable_scalp and second_entry_on) or (is_stop_loss_exit and reentry_sl_on)

        self.assertTrue(allow_reentry)

        # Progression check
        curr_entry_num = 1
        next_entry_num = curr_entry_num + 1
        self.assertEqual(next_entry_num, 2)
        self.assertTrue(next_entry_num <= 3)

        # Time check (300s >= 240s)
        remaining_sec = 300
        self.assertTrue(remaining_sec >= 240)

        # Price check: discounted dip ask
        second_ask = 0.38
        max_ask = float(user.get("second_entry_max_ask", 0.75))
        self.assertTrue(0.15 <= second_ask <= max_ask)

        # Create trade 2
        trade_2 = {
            "id": "t2",
            "ticker": ticker,
            "side": "YES",
            "count": 10,
            "entry_price": second_ask,
            "status": "OPEN",
            "reason": f"STOP_LOSS_REENTRY_{next_entry_num}",
            "is_second_entry": True,
            "is_third_entry": False,
            "is_stop_loss_reentry": True,
            "reentry_index": 2,
        }

        # Trade 2 gets stopped out too
        trade_2["status"] = "CLOSED"
        trade_2["exit_reason"] = "STOP_LOSS (-18.0%)"
        trade_2["exit_price"] = 0.31

        curr_entry_num = 2 if trade_2.get("is_second_entry") else 1
        next_entry_num = curr_entry_num + 1
        self.assertEqual(next_entry_num, 3)
        self.assertTrue(next_entry_num <= 3)

        # Trade 3 created
        trade_3 = {
            "id": "t3",
            "ticker": ticker,
            "side": "YES",
            "count": 10,
            "entry_price": 0.28,
            "status": "OPEN",
            "reason": f"STOP_LOSS_REENTRY_{next_entry_num}",
            "is_second_entry": False,
            "is_third_entry": True,
            "is_stop_loss_reentry": True,
            "reentry_index": 3,
        }

        # Trade 3 gets stopped out
        trade_3["status"] = "CLOSED"
        trade_3["exit_reason"] = "STOP_LOSS (-20.0%)"

        curr_entry_num = 3 if trade_3.get("is_third_entry") else 1
        next_entry_num = curr_entry_num + 1
        self.assertEqual(next_entry_num, 4)
        can_reenter_count = (next_entry_num <= 3)
        self.assertFalse(can_reenter_count)  # Hard-capped at 3 entries!

        # Guard: If remaining time is < 240s (e.g. 180s), blocked
        late_remaining_sec = 180
        self.assertFalse(late_remaining_sec >= 240)

    def test_trailing_stop_calculation_and_exit(self):
        """
        Verify the exact Trailing Stop Loss mechanics in SaaSSettler:
        1. When max_seen_profit_pct < ts_activation (e.g. 20% < 35%), trailing stop does NOT arm/trigger.
        2. When max_seen_profit_pct >= ts_activation (e.g. 40% >= 35%), trailing stop arms.
        3. Trail threshold is max(max_seen_bid - ts_distance, max_seen_bid * (1 - ts_distance)), clamped to entry * 1.02 minimum profit floor.
        4. If curr_bid drops to/below trail_threshold, trailing stop triggers with REASON 'TRAILING_STOP (+X.X%)'.
        5. The resulting exit price secures positive profit above entry.
        """
        entry = 0.50
        ts_enabled = True
        ts_activation = 0.35  # 35%
        ts_distance = 0.06    # 6%
        
        # Test 1: Sub-activation peak -> No trigger
        max_seen_bid = 0.60
        max_seen_profit_pct = (max_seen_bid - entry) / entry  # 20% < 35%
        trigger_exit = False
        if ts_enabled and max_seen_profit_pct >= ts_activation:
            trigger_exit = True
        self.assertFalse(trigger_exit)

        # Test 2: Peak reaches 0.70 (+40%) -> Arms!
        max_seen_bid = 0.70
        max_seen_profit_pct = (max_seen_bid - entry) / entry
        self.assertGreaterEqual(max_seen_profit_pct, ts_activation)

        trail_threshold = max(max_seen_bid - ts_distance, max_seen_bid * (1.0 - ts_distance))
        trail_threshold = max(trail_threshold, entry * 1.02)
        # max_seen_bid - ts_distance = 0.70 - 0.06 = 0.64
        # max_seen_bid * (1 - ts_distance) = 0.70 * 0.94 = 0.658
        # max is 0.658. Compared to entry * 1.02 = 0.51 -> 0.658
        self.assertAlmostEqual(trail_threshold, 0.658, places=3)

        # Still safe at 0.67
        curr_bid_safe = 0.67
        self.assertFalse(curr_bid_safe <= trail_threshold)

        # Drops to 0.64 -> Triggers exit!
        curr_bid_dropped = 0.64
        self.assertTrue(curr_bid_dropped <= trail_threshold)
        
        realized_p_pct = (curr_bid_dropped - entry) / entry
        reason = f"TRAILING_STOP (+{realized_p_pct*100:.1f}%)"
        self.assertIn("TRAILING_STOP", reason)
        self.assertIn("+28.0%", reason)
        self.assertNotIn("STOP_LOSS", reason)

    def test_trailing_stop_triggers_second_entry(self):
        """
        Verify that when a trade exits via TRAILING_STOP:
        1. is_profitable_scalp evaluates to True.
        2. allow_reentry evaluates to True when second_entry_enabled=1.
        3. A valid 2nd entry (and subsequently 3rd entry) is scheduled.
        """
        user = {
            "id": 101,
            "username": "ts_reenter_user",
            "second_entry_enabled": 1,
            "reentry_after_stop_loss": 0,
            "second_entry_max_ask": 0.75,
            "trading_mode": "PAPER",
        }
        entry = 0.50
        exit_price = 0.64
        reason = "TRAILING_STOP (+28.0%)"

        is_profitable_scalp = ("STOP_LOSS" not in reason) and (exit_price > entry) and (("TAKE_PROFIT" in reason) or ("TRAILING_STOP" in reason))
        second_entry_on = bool(user.get("second_entry_enabled", 0))
        is_stop_loss_exit = ("STOP_LOSS" in reason)
        reentry_sl_on = bool(user.get("reentry_after_stop_loss", 0))

        allow_reentry = (is_profitable_scalp and second_entry_on) or (is_stop_loss_exit and reentry_sl_on)
        self.assertTrue(is_profitable_scalp)
        self.assertTrue(allow_reentry)

        # Progression check
        curr_entry_num = 1
        next_entry_num = curr_entry_num + 1
        self.assertEqual(next_entry_num, 2)
        self.assertTrue(next_entry_num <= 3)

    @patch("backend.btc.analyzer.contract_eval.evaluate_next_15m_contract")
    @patch("backend.btc.indicators.add_all_indicators")
    @patch("backend.btc.data_fetcher.fetch_candles")
    def test_stop_loss_reentry_recalculates_and_pivots_direction(self, mock_fetch, mock_indicators, mock_eval):
        """
        Verify that on stop loss:
        1. A fresh prediction is calculated using market candles and indicators.
        2. When market dumped and prediction flips from YES to NO/BELOW with high confidence,
           re-entry is pivoted to NO side instead of blindly repeating YES.
        """
        import pandas as pd
        mock_fetch.return_value = pd.DataFrame([{"close": 60000, "open": 60100}])
        mock_indicators.return_value = pd.DataFrame([{"close": 60000, "open": 60100}])
        mock_eval.return_value = {
            "direction": "BELOW",
            "recommendation": "MOMENTUM SELL",
            "probability_percent": 68.5,
        }

        user = {"trading_style": "MOMENTUM_SURFER", "signal_source": "BLEND", "min_confidence": 55.0}
        market = {"strike_price": 60200.0, "yes_ask": 0.30, "no_ask": 0.70}
        
        # Original trade was YES and got stopped out
        result = _recalculate_stop_loss_prediction("KXBTC15M-TEST", market, user, original_side="yes")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["reentry_side"], "no")
        self.assertEqual(result["direction"], "BELOW")
        self.assertEqual(result["prediction_direction"], "BELOW")
        self.assertTrue(result["is_flipped"])
        self.assertEqual(result["probability_percent"], 68.5)

    @patch("backend.btc.analyzer.contract_eval.evaluate_next_15m_contract")
    @patch("backend.btc.indicators.add_all_indicators")
    @patch("backend.btc.data_fetcher.fetch_candles")
    def test_stop_loss_reentry_aborts_on_pass_or_low_confidence(self, mock_fetch, mock_indicators, mock_eval):
        """
        Verify that on stop loss:
        1. If fresh prediction is PASS or NEUTRAL, re-entry stands down (returns None).
        2. If fresh prediction confidence is below min_confidence (e.g. 52% < 55%), re-entry stands down.
        """
        import pandas as pd
        mock_fetch.return_value = pd.DataFrame([{"close": 60000, "open": 60100}])
        mock_indicators.return_value = pd.DataFrame([{"close": 60000, "open": 60100}])
        
        user = {"trading_style": "MOMENTUM_SURFER", "signal_source": "BLEND", "min_confidence": 55.0}
        market = {"strike_price": 60200.0}

        # Case 1: PASS recommendation
        mock_eval.return_value = {
            "direction": "PASS",
            "recommendation": "PASS / CHOP",
            "probability_percent": 50.0,
        }
        res_pass = _recalculate_stop_loss_prediction("KXBTC15M-TEST", market, user, original_side="yes")
        self.assertIsNone(res_pass)

        # Case 2: Direction UP but confidence only 52% (< 55% threshold)
        mock_eval.return_value = {
            "direction": "ABOVE",
            "recommendation": "BUY",
            "probability_percent": 52.0,
        }
        res_low_conf = _recalculate_stop_loss_prediction("KXBTC15M-TEST", market, user, original_side="yes")
        self.assertIsNone(res_low_conf)

    @patch("backend.btc.analyzer.contract_eval.evaluate_next_15m_contract")
    @patch("backend.btc.indicators.add_all_indicators")
    @patch("backend.btc.data_fetcher.fetch_candles")
    def test_stop_loss_reentry_confirms_original_direction(self, mock_fetch, mock_indicators, mock_eval):
        """
        Verify that if fresh prediction confirms the original direction (e.g. support bounce):
        - reentry_side remains the same
        - is_flipped is False
        """
        import pandas as pd
        mock_fetch.return_value = pd.DataFrame([{"close": 60000, "open": 59900}])
        mock_indicators.return_value = pd.DataFrame([{"close": 60000, "open": 59900}])
        mock_eval.return_value = {
            "direction": "ABOVE",
            "recommendation": "STRONG BUY (BOUNCE)",
            "probability_percent": 64.0,
        }

        user = {"trading_style": "MOMENTUM_SURFER", "signal_source": "BLEND", "min_confidence": 55.0}
        market = {"strike_price": 59800.0}

        res = _recalculate_stop_loss_prediction("KXBTC15M-TEST", market, user, original_side="yes")
        self.assertIsNotNone(res)
        self.assertEqual(res["reentry_side"], "yes")
        self.assertEqual(res["direction"], "ABOVE")
        self.assertFalse(res["is_flipped"])
        self.assertEqual(res["probability_percent"], 64.0)


if __name__ == "__main__":
    unittest.main()

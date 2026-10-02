"""Regression tests for audit finding M1 (settlement.py `is_win`).

`is_win` used to be assigned only inside the official-result branch but read after it, so:
  * with several trades waiting, a pending trade reused the previous trade's `is_win` -> a
    false "Won" push and a paper credit while it was still OPEN (then a 2nd credit later);
  * an official LOSS fell through into the old candle fallback, which could overwrite
    Kalshi's result.
"""
import time
from unittest.mock import MagicMock, patch

import pandas as pd

import backend.btc.auto_executor.settlement as settlement


class _Bot(settlement.SettlementMixin):
    def __init__(self):
        self.mode = "PAPER"
        self.asset = "BTC"
        self._guest_id = None
        self._settled_since_drift_check = 0
        self.saved = None

    def get_trades_history(self):
        return []

    def _save_trades_history(self, trades):
        self.saved = [dict(t) for t in trades]

    def check_live_calibration_drift(self):
        pass


def _trade(tid, ticker, side="YES", entry=0.40, count=5, closed_secs_ago=60, strike=80000.0):
    return {"id": tid, "ticker": ticker, "side": side, "entry_price": entry, "count": count,
            "status": "OPEN", "mode": "PAPER", "close_epoch": time.time() - closed_secs_ago,
            "strike": strike, "prediction_kind": "AUTO"}


def _run(trades, results, candles=None):
    bot = _Bot()
    get_result = MagicMock(side_effect=lambda tk: results.get(tk, {"success": False}))
    with patch.object(settlement.kalshi_trader, "get_market_result", get_result), \
         patch.object(settlement, "update_balance") as credit, \
         patch.object(settlement, "send_web_push") as push, \
         patch.object(settlement, "update_shadow_settlements"), \
         patch.object(settlement, "fetch_candles", return_value=candles) as fc:
        bot.check_settlements(trades)
    return bot, credit, push, fc


def test_pending_trade_does_not_inherit_the_previous_trades_win():
    win = _trade("a", "KXBTC15M-26SEP281000-00", side="YES", count=5)
    pending = _trade("b", "KXBTC15M-26SEP281015-15", side="YES", count=7)
    results = {"KXBTC15M-26SEP281000-00": {"success": True, "result": "yes"}}  # 2nd: no result yet

    _, credit, _, _ = _run([win, pending], results)

    assert win["status"] == "SETTLED" and win["result"] == "WIN"
    assert pending["status"] == "OPEN"
    credit.assert_called_once()
    assert credit.call_args.args[0] == 5.0  # only the real win's $1 x 5 contracts


def test_pending_trade_alone_is_left_open_without_errors():
    pending = _trade("c", "KXBTC15M-26SEP281030-30")
    _, credit, push, _ = _run([pending], {})
    assert pending["status"] == "OPEN"
    credit.assert_not_called()
    push.assert_not_called()


def test_official_loss_is_final_and_never_reaches_the_candle_fallback():
    # Settled > 10 min late, and candles would say it WON - the official LOSS must stand.
    loss = _trade("d", "KXBTC15M-26SEP280900-00", side="YES", strike=80000.0, closed_secs_ago=1200)
    candles = pd.DataFrame({"close": [90000.0, 90000.0, 90000.0]})
    _, credit, _, fetch = _run([loss], {"KXBTC15M-26SEP280900-00": {"success": True, "result": "no"}}, candles)

    assert loss["result"] == "LOSS"
    assert loss["settlement_source"] == "kalshi_official"
    fetch.assert_not_called()
    credit.assert_not_called()


def test_official_win_credits_exactly_once_across_repeated_checks():
    win = _trade("e", "KXBTC15M-26SEP280930-30", side="NO", count=3)
    results = {"KXBTC15M-26SEP280930-30": {"success": True, "result": "no"}}
    _, credit1, _, _ = _run([win], results)
    _, credit2, _, _ = _run([win], results)  # already SETTLED - must not pay again
    assert credit1.call_count == 1 and credit1.call_args.args[0] == 3.0
    credit2.assert_not_called()


def test_candle_fallback_win_is_paid_once():
    old = _trade("f", "BTC-LEGACY-1", side="YES", strike=80000.0, closed_secs_ago=1200)
    old["prediction_kind"] = "MANUAL"
    candles = pd.DataFrame({"close": [81000.0, 81000.0, 81000.0]})
    _, credit, _, _ = _run([old], {}, candles)
    assert old["status"] == "SETTLED" and old["result"] == "WIN"
    assert old["settlement_source"] == "legacy_exchange_candle"
    credit.assert_called_once()

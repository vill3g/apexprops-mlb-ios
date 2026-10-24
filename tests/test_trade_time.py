"""Trade timestamps are sorted as real times, not text: "07:00 PM" is after "11:00 AM", and ISO
stamps are compared against the bot's 12-hour stamps correctly."""
import datetime
from zoneinfo import ZoneInfo

from backend.btc.auto_executor.risk_manager import RiskManagerMixin
from backend.core.trade_time import trade_epoch

ET = ZoneInfo("America/New_York")


def _today():
    return datetime.datetime.now(ET).strftime("%Y-%m-%d")


def test_parses_bot_12_hour_format():
    assert trade_epoch("2026-10-23 07:32:22 PM ET") == datetime.datetime(2026, 10, 23, 19, 32, 22, tzinfo=ET).timestamp()
    assert trade_epoch("2026-10-23 12:05:00 AM ET") == datetime.datetime(2026, 10, 23, 0, 5, tzinfo=ET).timestamp()


def test_parses_iso_and_rejects_garbage():
    assert trade_epoch("2026-10-23T19:33:53-04:00") == datetime.datetime(2026, 10, 23, 19, 33, 53, tzinfo=ET).timestamp()
    assert trade_epoch("") == 0.0
    assert trade_epoch(None) == 0.0
    assert trade_epoch("not a time") == 0.0
    assert trade_epoch(1700000000) == 1700000000.0


def test_twelve_hour_stamps_sort_by_real_time():
    stamps = ["2026-10-23 07:00:00 PM ET", "2026-10-23 11:00:00 AM ET", "2026-10-23 12:30:00 PM ET"]
    assert sorted(stamps, key=trade_epoch) == [stamps[1], stamps[2], stamps[0]]
    # The text sort gets this wrong (it puts "07:00 PM" first):
    assert sorted(stamps) != sorted(stamps, key=trade_epoch)


class _Bot(RiskManagerMixin):
    mode = "PAPER"
    max_daily_trades = 100
    max_daily_risk = 100.0

    def get_trades_history(self):
        return []


def _loss(ticker, stamp, pnl=-1.0):
    return {"ticker": ticker, "timestamp": stamp, "status": "SETTLED", "pnl": pnl, "mode": "PAPER"}


def test_circuit_breaker_halts_on_three_losses_in_real_time_order():
    # Real order: win 9:00 AM, then three losses at 11:30 AM, 12:30 PM and 1:15 PM.
    # Sorted as text the 1:15 PM loss comes first and a win lands between losses, so the
    # breaker used to miss the streak.
    d = _today()
    trades = [
        _loss("KXBTC15M-A", f"{d} 09:00:00 AM ET", pnl=+2.0),
        _loss("KXBTC15M-B", f"{d} 11:30:00 AM ET"),
        _loss("KXBTC15M-C", f"{d} 12:30:00 PM ET"),
        _loss("KXBTC15M-D", f"{d} 01:15:00 PM ET"),
    ]
    reason = _Bot().check_risk_budget(trades)
    assert reason is not None and "Circuit Breaker" in reason


def test_circuit_breaker_does_not_halt_when_the_last_loss_was_followed_by_a_win():
    d = _today()
    trades = [
        _loss("KXBTC15M-A", f"{d} 11:30:00 AM ET"),
        _loss("KXBTC15M-B", f"{d} 12:30:00 PM ET"),
        _loss("KXBTC15M-C", f"{d} 01:15:00 PM ET", pnl=+3.0),
    ]
    assert _Bot().check_risk_budget(trades) is None

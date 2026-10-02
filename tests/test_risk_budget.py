import pytest
from backend.btc.auto_executor import AutoExecutor

def test_compute_effective_daily_risk():
    ex = AutoExecutor("BTC")
    
    # Mock some trades
    today_trades = [
        {"pnl": 10.0, "status": "CLOSED"},
        {"pnl": -5.0, "status": "CLOSED"},
        {"pnl": 0.0, "status": "OPEN", "exit_price": 50.0, "count": 1, "mode": "PAPER"}
    ]
    
    net_pnl, open_risk, eff_risk = ex._compute_effective_daily_risk(today_trades)
    
    assert isinstance(net_pnl, float)
    assert isinstance(open_risk, float)
    assert isinstance(eff_risk, float)

def test_check_risk_budget():
    ex = AutoExecutor("BTC")
    ex.set_risk_limits(max_daily_risk=50.0, max_daily_trades=1)
    
    # 2 closed trades already hit max trades (which is 1)
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("America/New_York")).isoformat()
    today_trades = [
        {"pnl": -10.0, "status": "CLOSED", "timestamp": now_et, "mode": ex.mode},
        {"pnl": -50.0, "status": "CLOSED", "timestamp": now_et, "mode": ex.mode}
    ]
    
    res = ex.check_risk_budget(today_trades)
    assert res is not None
    assert "Hit max daily trades" in res or "budget" in res.lower() or "trades" in res.lower() or "limit" in res.lower()

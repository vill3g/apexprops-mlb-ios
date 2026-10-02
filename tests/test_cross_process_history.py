"""Regression tests for audit finding H4: the web server and the worker are separate
processes that both rewrite the owner bot's trade history and paper_balance.json. With only
thread locks, a stale save could revert a settled trade to OPEN (it was then settled and paid
again) or drop a trade the other process had just recorded."""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.btc.auto_executor.executor import AutoExecutor
from backend.btc.proc_lock import ReentrantProcessLock

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run_py(code: str, env_extra=None) -> subprocess.Popen:
    # Same import path as this test process (venv, repo root, anything conftest added).
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([REPO] + [p for p in sys.path if p]))
    env.update(env_extra or {})
    return subprocess.Popen([sys.executable, "-c", textwrap.dedent(code)], cwd=REPO, env=env)


# ── the lock itself ──────────────────────────────────────────────────────────

def test_lock_is_reentrant_in_one_thread(tmp_path):
    lock = ReentrantProcessLock("reentrant_test", lock_dir=str(tmp_path))
    with lock:
        with lock:
            pass
    with lock:
        pass


def test_lock_excludes_another_process(tmp_path):
    marker = tmp_path / "held"
    holder = _run_py(f"""
        import time, pathlib
        from backend.btc.proc_lock import ReentrantProcessLock
        lock = ReentrantProcessLock("xproc_test", lock_dir={str(tmp_path)!r})
        with lock:
            pathlib.Path({str(marker)!r}).write_text("1")
            time.sleep(1.5)
    """)
    try:
        deadline = time.time() + 20
        while not marker.exists() and time.time() < deadline:
            time.sleep(0.05)
        assert marker.exists(), "helper process never took the lock"
        start = time.time()
        with ReentrantProcessLock("xproc_test", lock_dir=str(tmp_path)):
            waited = time.time() - start
        assert waited > 0.5, "acquired the lock while another process held it"
    finally:
        holder.wait(timeout=30)


# ── paper balance: no lost updates across processes ─────────────────────────

def test_paper_balance_credits_from_two_processes_are_never_lost(tmp_path):
    bal = tmp_path / "paper_balance.json"
    bal.write_text(json.dumps({"balance": 100.0}))
    code = f"""
        import backend.btc.paper_balance as pb
        pb.BALANCE_PATH = {str(bal)!r}
        for _ in range(40):
            pb.update_balance(1.0)
    """
    procs = [_run_py(code), _run_py(code)]
    for p in procs:
        assert p.wait(timeout=120) == 0
    assert json.loads(bal.read_text())["balance"] == pytest.approx(180.0)


# ── history saves merge instead of clobbering ────────────────────────────────

def _bare_executor(history_file):
    ae = AutoExecutor.__new__(AutoExecutor)
    ae._history_file = str(history_file)
    ae.trade_db = None
    ae.asset = "BTC"
    return ae


def test_stale_save_never_reverts_a_settled_trade_or_drops_a_new_one(tmp_path):
    hist = tmp_path / "trades_history.json"
    # What the OTHER process has on disk now: trade 'a' settled, plus a brand-new trade 'c'.
    hist.write_text(json.dumps([
        {"id": "a", "status": "SETTLED", "result": "WIN", "pnl": 3.0},
        {"id": "b", "status": "OPEN"},
        {"id": "c", "status": "OPEN", "ticker": "NEW"},
    ]))
    ae = _bare_executor(hist)
    # This process read the file earlier (before 'a' settled and before 'c' existed) and now
    # saves its stale list with one new trade of its own.
    stale = [{"id": "a", "status": "OPEN"}, {"id": "b", "status": "OPEN"}, {"id": "d", "status": "OPEN"}]
    ae._save_trades_history(stale)

    on_disk = {t["id"]: t for t in json.loads(hist.read_text())}
    assert on_disk["a"]["status"] == "SETTLED" and on_disk["a"]["pnl"] == 3.0
    assert set(on_disk) == {"a", "b", "c", "d"}
    assert {t["id"] for t in stale} == {"a", "b", "c", "d"}  # caller's list sees the merge


def test_our_own_close_still_wins_over_an_open_copy_on_disk(tmp_path):
    hist = tmp_path / "trades_history.json"
    hist.write_text(json.dumps([{"id": "x", "status": "OPEN"}]))
    ae = _bare_executor(hist)
    ae._save_trades_history([{"id": "x", "status": "CLOSED", "exit_reason": "STOP_LOSS"}])
    assert json.loads(hist.read_text())[0]["status"] == "CLOSED"


def test_settlement_decides_on_the_file_not_the_callers_stale_list(tmp_path):
    """The web process passes the list it read for the status page; meanwhile the worker
    settled and paid the trade. The web process must not settle (and pay) it again."""
    hist = tmp_path / "trades_history.json"
    settled = {"id": "s1", "ticker": "KXBTC15M-26SEP281000-00", "side": "YES", "entry_price": 0.4,
               "count": 5, "status": "SETTLED", "result": "WIN", "mode": "PAPER",
               "close_epoch": time.time() - 120}
    hist.write_text(json.dumps([settled]))
    ae = _bare_executor(hist)
    ae.mode = "PAPER"
    ae._guest_id = None
    ae._settled_since_drift_check = 0
    stale = [dict(settled, status="OPEN", result="PENDING")]

    import backend.btc.auto_executor.settlement as settlement
    with patch.object(settlement.kalshi_trader, "get_market_result",
                      return_value={"success": True, "result": "yes"}), \
         patch.object(settlement, "update_balance") as credit, \
         patch.object(settlement, "send_web_push"), \
         patch.object(settlement, "update_shadow_settlements"):
        ae.check_settlements(stale)

    credit.assert_not_called()
    assert stale[0]["status"] == "SETTLED"  # caller's list now shows the real state

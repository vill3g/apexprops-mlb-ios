"""Verify the audit fixes described in CHANGES_FOR_REVIEW.md are present and working.

Run from the repo root:   python scripts/verify_audit_fixes.py
  1. Checks each fix's code marker is still in its file (catches a fix that was
     overwritten, e.g. by an editor saving an older copy of the file).
  2. Runs the regression test files that go with the fixes.
Exit code 0 = everything present and passing.
"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# (change id, file, exact text that must be present)
MARKERS = [
    # Paper-trading realism
    ("PAPER", "backend/btc/kalshi_trader.py", "PAPER_LATENCY_TAX_DOLLARS ="),
    ("PAPER", "backend/btc/kalshi_trader.py", "def _simulated_book_depth("),
    ("PAPER", "backend/btc/auto_executor/executor.py", "paper_avail_bal = load_balance("),
    ("PAPER", "backend/btc/auto_executor/stop_manager.py", "Kalshi only quotes/fills in whole cents"),
    # Pattern Watch
    ("PATTERN", "backend/btc/pattern_analyzer.py", "def get_pattern_signal("),
    ("PATTERN", "backend/btc/analyzer/contract_eval.py", "get_pattern_signal"),
    # M-DUP: one automated LIVE entry per account per market
    ("M-DUP", "backend/database/order_intents.py", "def claim("),
    ("M-DUP", "backend/btc/auto_executor/executor.py", "order_intents.claim(intent_key, current_interval_id, side)"),
    ("M-DUP", "backend/btc/auto_executor/executor.py", "order_intents.settle_outcome(intent_key, current_interval_id, order_res)"),
    ("M-DUP", "backend/btc/auto_executor/saas_broadcaster.py", "intent_key = order_intents.account_key_for_user(user['id'])"),
    ("M-DUP", "backend/btc/auto_executor/saas_broadcaster.py", "order_intents.settle_outcome(intent_key, current_interval_id, res)"),
    # M-AMBIG: lost responses are confirmed or ambiguous, never a clean rejection
    ("M-AMBIG", "backend/btc/kalshi_trader.py", "def _resolve_uncertain_buy("),
    ("M-AMBIG", "backend/btc/kalshi_trader.py", "def _lookup_order_fill("),
    ("M-AMBIG", "backend/btc/kalshi_trader.py", "sent_cid = retry_cid"),
    ("M-AMBIG", "backend/btc/kalshi_trader.py", "except requests.exceptions.ConnectTimeout as e:"),
    # H1: record filled contracts, not requested
    ("H1", "backend/btc/kalshi_trader.py", "def filled_count("),
    ("H1", "backend/btc/auto_executor/saas_broadcaster.py", "contracts = _filled_count(res, contracts)"),
    ("H1", "backend/btc/auto_executor/saas_broadcaster.py", '"requested_count": requested_contracts or contracts'),
    ("H1", "backend/auth/routes.py", 'trade_rec["count"] = _filled_count(res, count)'),
    ("H1", "backend/auth/routes.py", "count = _filled_count(res, count)"),
    ("H1", "backend/btc/auto_executor/stop_manager.py", "count = _filled_count(order_res, count)"),
    ("H1", "backend/btc/auto_executor/stop_manager.py", "contracts_to_buy = _filled_count(order_res, contracts_to_buy)"),
    ("H1", "backend/saas_settler.py", "second_count = filled_count(order_res, second_count)"),
    # H2: second entries follow the trade's own mode, respect AI switch, size with slippage+fee
    ("H2", "backend/saas_settler.py", "def _second_entry_mode("),
    ("H2", "backend/saas_settler.py", "def _second_entry_size("),
    ("H2", "backend/saas_settler.py", 'f"{ticker}#second_entry"'),
    ("H2", "backend/saas_settler.py", "paper_kalshi_trader.place_order("),
    # H3: settler uses each trade's own market (BTC / ETH)
    ("H3", "backend/saas_settler.py", "def _market_for_ticker("),
    ("H3", "backend/saas_settler.py", "market = _market_for_ticker(ticker, _market_cache)"),
    ("H3", "backend/saas_settler.py", 'market = _market_for_ticker(t.get("ticker"), markets)'),
    # M1: settlement.py is_win
    ("M1", "backend/btc/auto_executor/settlement.py", "def _pay_out("),
    ("M1", "backend/btc/auto_executor/settlement.py", "continue  # Kalshi's official result is final"),
    # H4: cross-process locking + merge-on-save for the owner bot
    ("H4", "backend/btc/proc_lock.py", "class ReentrantProcessLock"),
    ("H4", "backend/btc/auto_executor/shared.py", 'ReentrantProcessLock("owner_trades_history")'),
    ("H4", "backend/btc/auto_executor/executor.py", "def _merge_with_disk("),
    ("H4", "backend/btc/auto_executor/executor.py", "trades[:] = self._merge_with_disk("),
    ("H4", "backend/btc/auto_executor/settlement.py", "caller_list[:] = trades"),
    ("H4", "backend/btc/paper_balance.py", 'ReentrantProcessLock("paper_balance")'),
    ("H4", "backend/btc/paper_balance.py", "def _read_balance_file("),
]

TEST_FILES = [
    "tests/test_paper_trading_realism.py",
    "tests/test_pattern_analyzer.py",
    "tests/test_order_dedup_and_ambiguity.py",
    "tests/test_partial_fill_recording.py",
    "tests/test_second_entry_guards.py",
    "tests/test_settler_multi_asset.py",
    "tests/test_settlement_is_win.py",
    "tests/test_cross_process_history.py",
]


def main() -> int:
    missing = []
    for change, rel, text in MARKERS:
        path = os.path.join(ROOT, rel)
        try:
            with open(path, "r", encoding="utf-8") as f:
                ok = text in f.read()
        except OSError:
            ok = False
        print(f"[{'OK ' if ok else 'MISSING'}] {change:8} {rel}: {text}")
        if not ok:
            missing.append((change, rel, text))

    print(f"\n{len(MARKERS) - len(missing)}/{len(MARKERS)} code markers present.")
    if missing:
        print("A MISSING marker means that fix is not in the file (was it overwritten?).")

    tests = [t for t in TEST_FILES if os.path.exists(os.path.join(ROOT, t))]
    absent = sorted(set(TEST_FILES) - set(tests))
    if absent:
        print(f"Test files not found: {absent}")
    print("\nRunning regression tests:", " ".join(tests))
    rc = subprocess.call([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT)
    return 0 if (not missing and not absent and rc == 0) else 1


if __name__ == "__main__":
    sys.exit(main())

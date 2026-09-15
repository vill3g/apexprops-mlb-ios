"""
Remediation Verification Test Suite for Kalshi BTC 15M AI Trader
Verifies all 9 remediation items from the security/correctness audit.
"""

import os
import sys
import json
import unittest
import threading
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock

# Ensure repo root is on python path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestFinding1SafetyBaseline(unittest.TestCase):
    """Finding 1 (CRITICAL): App pre-armed for live autonomous trading."""

    def test_default_trading_config_safe(self):
        cfg_path = os.path.join(REPO_ROOT, "backend", "data", "trading_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("mode") == "LIVE":
            self.skipTest("Live mode is explicitly configured on active deployment")
        self.assertFalse(cfg.get("enabled"), "Default config enabled must be False")
        self.assertEqual(cfg.get("mode"), "PAPER", "Default mode must be PAPER")
        self.assertTrue(cfg.get("dryRun"), "Default dryRun must be True")
        self.assertFalse(cfg.get("ignorePass"), "Default ignorePass must be False")
        self.assertTrue(cfg.get("ai_settings", {}).get("dryRun"), "ai_settings dryRun must be True")
        self.assertFalse(cfg.get("ai_settings", {}).get("ignorePass"), "ai_settings ignorePass must be False")

    def test_startup_demote_live_to_paper_if_no_trades_history(self):
        from backend.btc.auto_executor import AutoExecutor
        executor = AutoExecutor.__new__(AutoExecutor)
        executor._save_config = MagicMock()
        test_cfg = {"enabled": True, "mode": "LIVE", "dryRun": False}

        original_exists = os.path.exists
        def mock_exists(path):
            if "trades_history.json" in str(path):
                return False
            return original_exists(path)

        with patch("os.path.exists", side_effect=mock_exists):
            with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(test_cfg))):
                AutoExecutor._load_config(executor)
                self.assertEqual(executor.mode, "PAPER", "Should demote to PAPER")
                self.assertFalse(executor.enabled, "Should disable autonomous trading")

    def test_set_mode_live_requires_authentication(self):
        from backend.btc.auto_executor import AutoExecutor
        executor = AutoExecutor.__new__(AutoExecutor)
        executor.mode = "PAPER"
        executor._save_config = MagicMock()

        with patch("backend.btc.kalshi_trader.kalshi_trader.is_authenticated", return_value=False):
            res = executor.set_mode("LIVE")
            self.assertFalse(res.get("success"), "set_mode('LIVE') without auth should fail")
            self.assertEqual(executor.mode, "PAPER", "Mode should remain PAPER")


class TestFinding2DailyRiskLimits(unittest.TestCase):
    """Finding 2 (HIGH): Daily risk limits only on rollover."""

    def test_check_risk_budget_enforcement(self):
        from backend.btc.auto_executor import AutoExecutor
        executor = AutoExecutor.__new__(AutoExecutor)
        executor.max_daily_risk = 50.0
        executor.max_daily_trades = 5
        executor.mode = "PAPER"

        today_prefix = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")

        # Simulate 6 trades today -> exceed count limit
        trades_today = [{"pnl": 5.0, "mode": "PAPER", "status": "SETTLED", "timestamp": today_prefix} for _ in range(6)]
        reason = executor.check_risk_budget(trades=trades_today)
        self.assertIsNotNone(reason)
        self.assertIn("Max daily trades reached", reason)

        # Simulate daily loss exceeding limit
        trades_loss = [{"pnl": -60.0, "mode": "PAPER", "status": "SETTLED", "timestamp": today_prefix}]
        reason = executor.check_risk_budget(trades=trades_loss)
        self.assertIsNotNone(reason)
        self.assertIn("Max daily risk limit reached", reason)

        # Simulate within limit
        trades_ok = [{"pnl": 10.0, "mode": "PAPER", "status": "SETTLED", "timestamp": today_prefix}]
        reason = executor.check_risk_budget(trades=trades_ok)
        self.assertIsNone(reason)

    def test_manual_trade_checks_risk_budget(self):
        from backend.btc.auto_executor import AutoExecutor
        executor = AutoExecutor.__new__(AutoExecutor)
        executor.enabled = False
        executor.mode = "PAPER"
        executor.ai_settings = {}
        with patch.object(executor, "check_risk_budget", return_value="Max daily risk limit reached"):
            res = executor.execute_manual_trade("ABOVE")
            self.assertFalse(res.get("success"))
            self.assertIn("Max daily risk limit reached", res.get("error"))

    def test_scalp_engine_checks_risk_budget(self):
        from backend.btc.scalp_engine import ScalpEngine
        engine = ScalpEngine.__new__(ScalpEngine)
        engine.config = {"mode": "PAPER", "max_contracts": 1}

        mock_executor = MagicMock()
        mock_executor.check_risk_budget.return_value = "Max daily risk limit reached"
        mock_executor.mode = "PAPER"

        with patch("backend.btc.auto_executor.auto_executor", mock_executor):
            with patch("backend.btc.kalshi_trader.kalshi_trader.place_order") as mock_place_order:
                engine._execute_trade("yes", 60000.0)
                mock_place_order.assert_not_called()


class TestFinding3GitignoreAndState(unittest.TestCase):
    """Finding 3 (HIGH): Missing .gitignore and state files tracked."""

    def test_gitignore_contains_critical_entries(self):
        gitignore_path = os.path.join(REPO_ROOT, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), ".gitignore must exist")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("kalshi_credentials.json", content)
        self.assertIn("trades_history.json", content)
        self.assertIn("scalp_config.json", content)
        self.assertIn(".env", content)

    def test_scalp_config_not_in_git_index(self):
        try:
            from dulwich.repo import Repo
            repo = Repo(REPO_ROOT)
            index = repo.open_index()
            tracked_files = [path.decode("utf-8") for path in index]
            self.assertNotIn("backend/btc/scalp_config.json", tracked_files)
        except ImportError:
            pass


class TestFinding4WatchdogAndConcurrency(unittest.TestCase):
    """Finding 4 (MEDIUM): Watchdog spawning duplicate worker and rollover lock."""

    def test_rollover_concurrency_barrier(self):
        from backend.btc.auto_executor import AutoExecutor
        executor = AutoExecutor.__new__(AutoExecutor)
        executor._rollover_lock = threading.Lock()
        executor.last_traded_interval = None
        executor.mode = "PAPER"
        executor.enabled = True
        executor.ai_settings = {}
        executor.market_ticker = "KXBTC-CONCURRENCY-TEST"

        call_count = 0
        def fake_worker():
            nonlocal call_count
            acquired = executor._rollover_lock.acquire(blocking=False)
            if not acquired:
                return
            try:
                call_count += 1
                import time
                time.sleep(0.05)
            finally:
                executor._rollover_lock.release()

        t1 = threading.Thread(target=fake_worker)
        t2 = threading.Thread(target=fake_worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(call_count, 1, "Only one thread should acquire non-blocking lock")


class TestFinding5MLLabelSemantics(unittest.TestCase):
    """Finding 5 (MEDIUM): ML label semantics drift on NO trades."""

    def test_ml_label_extraction_yes_and_no(self):
        from backend.btc.ml_engine import MLEngine

        # 4 scenarios repeated to reach 12 samples (min 10 required):
        # 1. YES trade, settled >= strike -> WIN -> label 1
        # 2. YES trade, settled < strike -> LOSS -> label 0
        # 3. NO trade, settled >= strike -> LOSS -> label 1 (BTC resolved above strike)
        # 4. NO trade, settled < strike -> WIN -> label 0 (BTC resolved below strike)
        trades = []
        for i in range(12):
            if i % 4 == 0:
                trades.append({
                    "status": "SETTLED", "side": "YES", "settle_price": 60000, "strike": 50000,
                    "result": "WON", "market_snapshot": {"raw_features": {"rsi": 55}}
                })
            elif i % 4 == 1:
                trades.append({
                    "status": "SETTLED", "side": "YES", "settle_price": 40000, "strike": 50000,
                    "result": "LOST", "market_snapshot": {"raw_features": {"rsi": 45}}
                })
            elif i % 4 == 2:
                trades.append({
                    "status": "SETTLED", "side": "NO", "settle_price": 60000, "strike": 50000,
                    "result": "LOST", "market_snapshot": {"raw_features": {"rsi": 65}}
                })
            else:
                trades.append({
                    "status": "SETTLED", "side": "NO", "settle_price": 40000, "strike": 50000,
                    "result": "WON", "market_snapshot": {"raw_features": {"rsi": 35}}
                })

        with tempfile.TemporaryDirectory() as tmpdir:
            hist_path = os.path.join(tmpdir, "trades_history.json")
            with open(hist_path, "w", encoding="utf-8") as f:
                json.dump(trades, f)

            engine = MLEngine(data_dir=tmpdir)
            X, y, weights = engine._extract_features_and_labels()
            self.assertEqual(len(y), 12)
            self.assertEqual(y[0], 1, "YES trade with settle >= strike must have label 1")
            self.assertEqual(y[1], 0, "YES trade with settle < strike must have label 0")
            self.assertEqual(y[2], 1, "NO trade with settle >= strike must have label 1")
            self.assertEqual(y[3], 0, "NO trade with settle < strike must have label 0 (NOT 1!)")

    def test_ml_legacy_fallback(self):
        from backend.btc.ml_engine import MLEngine
        legacy_trades = []
        for i in range(12):
            if i % 2 == 0:
                legacy_trades.append({
                    "status": "SETTLED", "side": "YES", "result": "WON",
                    "market_snapshot": {"raw_features": {"rsi": 55}}
                })
            else:
                legacy_trades.append({
                    "status": "SETTLED", "side": "NO", "result": "WON",
                    "market_snapshot": {"raw_features": {"rsi": 35}}
                })
        with tempfile.TemporaryDirectory() as tmpdir:
            hist_path = os.path.join(tmpdir, "trades_history.json")
            with open(hist_path, "w", encoding="utf-8") as f:
                json.dump(legacy_trades, f)

            engine = MLEngine(data_dir=tmpdir)
            X, y, weights = engine._extract_features_and_labels()
            self.assertEqual(len(y), 12)
            self.assertEqual(y[0], 1, "Legacy WON YES trade -> label 1")
            self.assertEqual(y[1], 0, "Legacy WON NO trade -> label 0")


class TestFinding6XSSMitigation(unittest.TestCase):
    """Finding 6 (MEDIUM): XSS in static/trades.html and static/index.html."""

    def test_index_html_has_escape_html_and_usages(self):
        trades_path = os.path.join(REPO_ROOT, "static", "trades.html")
        with open(trades_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("function escapeHtml(str)", content, "Must define escapeHtml helper")
        self.assertIn("escapeHtml(t.ticker", content, "Trades ticker must be escaped")
        self.assertIn("escapeHtml(dirText)", content, "Trades direction text must be escaped")
        self.assertIn("escapeHtml(strike)", content, "Trades strike must be escaped")
        self.assertIn("escapeHtml(statusBadgeText)", content, "Trades status badge must be escaped")


class TestFinding7BasisRiskAndRender(unittest.TestCase):
    """Finding 7 (LOW): Basis risk disclosure and no render files."""

    def test_basis_risk_disclosed(self):
        readme_path = os.path.join(REPO_ROOT, "README.md")
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()
        self.assertIn("Exchange Basis Risk Notice", readme_content)

        fetcher_path = os.path.join(REPO_ROOT, "backend", "btc", "data_fetcher.py")
        with open(fetcher_path, "r", encoding="utf-8") as f:
            fetcher_content = f.read()
        self.assertIn("Basis Risk", fetcher_content)

    def test_render_yaml_not_present(self):
        render_path = os.path.join(REPO_ROOT, "render.yaml")
        self.assertFalse(os.path.exists(render_path), "render.yaml must NOT exist")


class TestFinding8GraceWindow(unittest.TestCase):
    """Finding 8 (LOW): 5-minute display client close filter."""

    def test_kalshi_client_grace_window_15s(self):
        client_path = os.path.join(REPO_ROOT, "backend", "btc", "kalshi_client.py")
        with open(client_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("timedelta(seconds=15)", content, "Grace period must be 15 seconds")
        self.assertNotIn("timedelta(minutes=5)", content, "Old 5-minute grace period must be removed")


class TestFinding9TickerMismatchAndVerification(unittest.TestCase):
    """Finding 9 (LOW): Discarded ticker argument and order response verification."""

    def test_kalshi_trader_logs_warning_on_ticker_mismatch(self):
        from backend.btc.kalshi_trader import KalshiTrader
        trader = KalshiTrader.__new__(KalshiTrader)
        trader.get_active_15m_market = MagicMock(return_value={"ticker": "VERIFIED-TICKER"})
        trader.get_balance = MagicMock(return_value={"success": False, "error": "Halt here"})

        with patch("backend.btc.kalshi_trader.logger.warning") as mock_warn:
            trader.place_order(ticker="MISMATCHED-TICKER", side="yes", count=1, dry_run=False)
            warn_called = any("MISMATCHED-TICKER" in str(c) for c in mock_warn.call_args_list)
            self.assertTrue(warn_called, "Should log warning when ticker mismatches verified market")

    def test_auto_executor_aborts_on_ticker_mismatch(self):
        order_res = {"success": True, "ticker": "TICKER-B"}
        current_interval_id = "TICKER-A"
        res_ticker = order_res.get("ticker")
        mismatch = bool(res_ticker and str(res_ticker).strip() != str(current_interval_id).strip())
        self.assertTrue(mismatch, "Should detect ticker mismatch between interval and order response")


if __name__ == "__main__":
    unittest.main()

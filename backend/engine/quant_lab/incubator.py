"""
Paper Incubator for ShadowTrader Quant Lab.
Runs live forward-testing on strategies that successfully cleared backtest hurdles.
Simulates paper trades on incoming real-time market ticks without risking capital.
Graduates winners to production readiness and retires degrading strategies to the Graveyard.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.engine.quant_lab.auditor import PostMortemAuditor
from backend.engine.quant_lab.graveyard import DB_PATH, StrategyRegistry, _now_str
from backend.engine.quant_lab.strategy_coder import StrategyCoder

logger = logging.getLogger(__name__)

_inc_lock = threading.Lock()

# Incubation graduation and retirement rules
MAX_INCUBATION_DRAWDOWN = 0.18
GRADUATION_MIN_TRADES = 20
GRADUATION_MIN_WIN_RATE = 0.60


def init_incubation_table() -> None:
    with _inc_lock, sqlite3.connect(DB_PATH, timeout=15.0) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS strategy_incubation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                asset TEXT NOT NULL,
                code TEXT NOT NULL,
                trades_count INTEGER DEFAULT 0,
                wins_count INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0.0,
                max_drawdown REAL DEFAULT 0.0,
                status TEXT DEFAULT 'ACTIVE',
                started_at TEXT NOT NULL,
                last_evaluated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS incubation_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                asset TEXT NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                strike_price REAL NOT NULL,
                status TEXT DEFAULT 'OPEN',
                pnl REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                settled_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_inc_trades_ticker ON incubation_trades(ticker, status);
        """)
        conn.commit()


class PaperIncubator:
    """Manages forward-testing lifecycle for validated strategies."""

    def __init__(self):
        init_incubation_table()
        self._compiled_cache: Dict[str, Any] = {}

    def incubate_strategy(self, strategy_id: str, name: str, asset: str, code: str) -> None:
        """Adds a newly validated strategy to the incubator."""
        now = _now_str()
        with _inc_lock, sqlite3.connect(DB_PATH, timeout=15.0) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO strategy_incubation (
                    strategy_id, name, asset, code, trades_count, wins_count,
                    total_pnl, max_drawdown, status, started_at, last_evaluated_at
                ) VALUES (?, ?, ?, ?, 0, 0, 0.0, 0.0, 'ACTIVE', ?, ?)
            """, (strategy_id, name, asset.upper(), code, now, now))
            conn.commit()

        StrategyRegistry.update_status(strategy_id, "INCUBATING")
        logger.info(f"[PaperIncubator] Strategy '{name}' ({strategy_id}) added to live incubation.")

    def get_active_incubating(self, asset: Optional[str] = None) -> List[Dict[str, Any]]:
        with _inc_lock, sqlite3.connect(DB_PATH, timeout=15.0) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if asset:
                rows = cur.execute("""
                    SELECT * FROM strategy_incubation
                    WHERE status = 'ACTIVE' AND asset = ?
                    ORDER BY id DESC
                """, (asset.upper(),)).fetchall()
            else:
                rows = cur.execute("""
                    SELECT * FROM strategy_incubation
                    WHERE status = 'ACTIVE'
                    ORDER BY id DESC
                """).fetchall()

            return [dict(r) for r in rows]

    def get_graduated_strategies(self, asset: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all strategies that successfully passed live forward incubation."""
        with _inc_lock, sqlite3.connect(DB_PATH, timeout=15.0) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if asset:
                rows = cur.execute("""
                    SELECT * FROM strategy_incubation
                    WHERE status = 'GRADUATED' AND asset = ?
                    ORDER BY id DESC
                """, (asset.upper(),)).fetchall()
            else:
                rows = cur.execute("""
                    SELECT * FROM strategy_incubation
                    WHERE status = 'GRADUATED'
                    ORDER BY id DESC
                """).fetchall()

            return [dict(r) for r in rows]

    def evaluate_graduated_signals(self, asset: str, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluates all graduated strategies for an asset against an incoming live market snapshot.
        Returns active executable signals from proven models for live production execution.
        """
        graduated = self.get_graduated_strategies(asset=asset)
        signals = []
        for strat in graduated:
            code = strat.get("code")
            strat_id = strat.get("strategy_id")
            name = strat.get("name")
            if not code or not strat_id:
                continue
            try:
                if strat_id not in self._compiled_cache:
                    from backend.engine.quant_lab.strategy_coder import StrategyCoder
                    self._compiled_cache[strat_id] = StrategyCoder.compile_strategy(code)
                fn = self._compiled_cache[strat_id]
                sig = fn(snapshot)
                if isinstance(sig, dict) and sig.get("action") == "BUY":
                    sig["strategy_id"] = strat_id
                    sig["strategy_name"] = name
                    sig["asset"] = asset
                    sig["is_graduated"] = True
                    t_cnt = max(1, strat.get("trades_count", 1))
                    sig["live_win_rate"] = strat.get("wins_count", 0) / t_cnt
                    sig["live_trades_count"] = t_cnt
                    signals.append(sig)
            except Exception as e:
                logger.debug(f"[PaperIncubator] Graduated eval error for {name}: {e}")
        return signals

    def _is_sports_asset(self, asset: str) -> bool:
        a = str(asset or "").strip().upper()
        return a in {
            "SPORTS", "SPORT", "NFL", "MLB", "NBA", "NHL", "NPB", "KBO", "NPB/KBO", "NPB_KBO", "NPB-KBO",
            "SOC", "SOCCER", "UFC", "MMA", "TEN", "TENNIS", "ALL", "WNBA", "NCAAF", "NCAAB",
            "EPL", "MLS", "BUNDESLIGA", "LALIGA", "SERIEA"
        }

    def evaluate_snapshot(self, asset: str, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Runs all active incubating strategies against an incoming live market snapshot.
        Cross-evaluates signals against DualMLEngine (Financial) or Monte Carlo Simulation (Sports).
        Returns list of triggered trade signals enriched with model confidence and Kelly sizing.
        """
        active = self.get_active_incubating(asset=asset)
        signals = []
        is_sports = self._is_sports_asset(asset)

        try:
            from backend.engine.quant_lab.regime_classifier import MarketRegimeClassifier
            MarketRegimeClassifier.classify_snapshot(snapshot, asset=asset)
        except Exception as e:
            logger.debug(f"[PaperIncubator] Regime classification error: {e}")

        # Lazy load ML engine for financial consensus verification
        ml_engine = None
        if not is_sports:
            try:
                from backend.btc.ml_engine import get_ml_engine
                ml_engine = get_ml_engine(asset=asset)
            except Exception as e:
                logger.debug(f"[PaperIncubator] Could not load ML engine for confirmation: {e}")

        raw_features = snapshot.get("raw_features") or snapshot.get("indicators") or {}
        model_consensus = None

        if not is_sports and ml_engine and raw_features:
            try:
                model_consensus = ml_engine.predict_consensus(raw_features)
            except Exception as e:
                logger.debug(f"[PaperIncubator] ML consensus error: {e}")
        elif is_sports and raw_features:
            # Build sports simulation consensus structure
            prob = float(raw_features.get("ai_win_prob", 50.0))
            edge = float(raw_features.get("ai_edge", 0.0))
            conf = float(raw_features.get("confidence_score", 50.0))
            is_unan = (conf >= 70.0 and abs(edge) >= 5.0)
            model_consensus = {
                "ensemble_prob": round(prob / 100.0, 3),
                "p_ensemble": round(prob / 100.0, 3),
                "consensus_direction": "YES" if prob > 50.0 else ("NO" if prob < 50.0 else "NEUTRAL"),
                "agreement_ratio": round(min(1.0, max(0.5, conf / 100.0 + abs(edge) / 50.0)), 2),
                "is_unanimous": is_unan,
                "ai_edge": edge,
                "confidence_score": conf
            }

        for strat in active:
            s_id = strat["strategy_id"]
            code = strat["code"]
            if s_id not in self._compiled_cache:
                try:
                    self._compiled_cache[s_id] = StrategyCoder.compile_strategy(code)
                except Exception as e:
                    logger.error(f"[PaperIncubator] Compilation error for {s_id}: {e}")
                    continue

            fn = self._compiled_cache[s_id]
            try:
                sig = fn(snapshot)
                if isinstance(sig, dict) and sig.get("action") == "BUY":
                    chosen_side = sig.get("side", "YES").upper()
                    cur_price = float(snapshot.get("cur_price") or snapshot.get("yes_bid") or 0.50)

                    # Dynamic Kelly contract sizing scaled by ML consensus
                    kelly_res = {}
                    if not is_sports and ml_engine and raw_features:
                        try:
                            kelly_res = ml_engine.calculate_kelly_wager(
                                current_raw_features=raw_features,
                                market_price=cur_price,
                                available_capital=1000.0,
                                max_position_cap=150.0
                            )
                        except Exception as e:
                            logger.debug(f"[PaperIncubator] Kelly calculation warning: {e}")
                    elif is_sports and model_consensus:
                        try:
                            from backend.btc.fees import calculate_binary_kelly_position
                            p_win = model_consensus["p_ensemble"] if chosen_side == "YES" else (1.0 - model_consensus["p_ensemble"])
                            kelly_res = calculate_binary_kelly_position(
                                win_prob=p_win,
                                ask_price=cur_price,
                                available_capital=1000.0,
                                max_position_cap=150.0,
                                is_unanimous=model_consensus.get("is_unanimous", False),
                                agreement_ratio=model_consensus.get("agreement_ratio", 0.70)
                            )
                        except Exception as e:
                            logger.debug(f"[PaperIncubator] Sports Kelly calculation warning: {e}")

                    signals.append({
                        "strategy_id": s_id,
                        "name": strat["name"],
                        "asset": asset,
                        "signal": sig,
                        "cur_price": cur_price,
                        "model_consensus": model_consensus,
                        "kelly_sizing": kelly_res
                    })

                    # If this snapshot has a valid ticker, track forward paper execution
                    tkr = snapshot.get("ticker")
                    if tkr:
                        try:
                            strike_p = float(snapshot.get("strike_price") or snapshot.get("strike") or 0.0)
                            self.record_forward_entry(
                                strategy_id=s_id,
                                asset=asset,
                                ticker=tkr,
                                side=chosen_side,
                                entry_price=cur_price,
                                strike_price=strike_p
                            )
                        except Exception as fe_err:
                            logger.debug(f"[PaperIncubator] Forward entry record warning: {fe_err}")
            except Exception as e:
                logger.error(f"[PaperIncubator] Error evaluating {s_id}: {e}")

        return signals

    def record_forward_entry(
        self,
        strategy_id: str,
        asset: str,
        ticker: str,
        side: str,
        entry_price: float,
        strike_price: float = 0.0
    ) -> Optional[int]:
        """Records an opened paper trade for an incubating strategy in forward-testing."""
        if not ticker or not strategy_id:
            return None
        now = _now_str()
        with _inc_lock, sqlite3.connect(DB_PATH, timeout=15.0) as conn:
            cur = conn.cursor()
            existing = cur.execute("""
                SELECT id FROM incubation_trades
                WHERE strategy_id = ? AND ticker = ? AND status = 'OPEN'
            """, (strategy_id, ticker)).fetchone()
            if existing:
                return existing[0]

            cur.execute("""
                INSERT INTO incubation_trades (
                    strategy_id, asset, ticker, side, entry_price, strike_price,
                    status, pnl, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'OPEN', 0.0, ?)
            """, (strategy_id, asset.upper(), ticker, side.upper(), entry_price, strike_price, now))
            trade_id = cur.lastrowid
            conn.commit()
            logger.info(f"[PaperIncubator] Forward trade #{trade_id} opened for {strategy_id} on {ticker} ({side} @ ${entry_price:.2f})")
            return trade_id

    def settle_live_contract(self, ticker: str, winning_side: str, exit_price: float = 1.0) -> List[Dict[str, Any]]:
        """
        Settles all open incubation forward trades on ticker and triggers record_outcome().
        winning_side: 'YES' or 'NO'
        """
        win_side = str(winning_side or "").strip().upper()
        if win_side not in ("YES", "NO"):
            return []

        now = _now_str()
        settled_results = []
        trades_to_process = []

        with _inc_lock, sqlite3.connect(DB_PATH, timeout=15.0) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            rows = cur.execute("""
                SELECT * FROM incubation_trades
                WHERE ticker = ? AND status = 'OPEN'
            """, (ticker,)).fetchall()
            for r in rows:
                trades_to_process.append(dict(r))

        for t in trades_to_process:
            trade_id = t["id"]
            strategy_id = t["strategy_id"]
            t_side = t["side"].upper()
            entry_price = float(t["entry_price"])
            is_win = (t_side == win_side)
            # Binary contract payoff: if win: 1.0 - entry_price, else -entry_price
            pnl = (1.0 - entry_price) if is_win else (-entry_price)
            pnl = round(pnl, 4)

            with _inc_lock, sqlite3.connect(DB_PATH, timeout=15.0) as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE incubation_trades
                    SET status = 'SETTLED', pnl = ?, settled_at = ?
                    WHERE id = ?
                """, (pnl, now, trade_id))
                conn.commit()

            snap = {
                "ticker": ticker,
                "winning_side": win_side,
                "exit_price": exit_price,
                "asset": t.get("asset")
            }
            res = self.record_outcome(strategy_id, pnl, is_win, snap)
            logger.info(f"[PaperIncubator] Trade #{trade_id} ({strategy_id}) settled on {ticker}: {'WIN' if is_win else 'LOSS'} (PnL: ${pnl:.2f})")
            settled_results.append(res)

        return settled_results

    def settle_all_open_contracts(self) -> List[Dict[str, Any]]:
        """
        Polls Kalshi official resolution for all tickers with OPEN incubation trades.
        """
        tickers = []
        with _inc_lock, sqlite3.connect(DB_PATH, timeout=15.0) as conn:
            cur = conn.cursor()
            rows = cur.execute("""
                SELECT DISTINCT ticker FROM incubation_trades WHERE status = 'OPEN'
            """).fetchall()
            tickers = [r[0] for r in rows if r[0]]

        if not tickers:
            return []

        from backend.btc.kalshi_trader import kalshi_trader
        all_settled = []
        for tk in tickers:
            try:
                res = kalshi_trader.get_market_result(tk)
                ans = str(res.get("result") or "").lower().strip()
                if ans in ("yes", "no"):
                    settled = self.settle_live_contract(tk, ans.upper(), exit_price=1.0)
                    all_settled.extend(settled)
            except Exception as e:
                logger.debug(f"[PaperIncubator] Settle poll error for {tk}: {e}")
        return all_settled

    def get_incubation_trades(self, limit: int = 50, strategy_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns recent forward incubation paper trades."""
        with _inc_lock, sqlite3.connect(DB_PATH, timeout=15.0) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if strategy_id:
                rows = cur.execute("""
                    SELECT * FROM incubation_trades
                    WHERE strategy_id = ?
                    ORDER BY id DESC LIMIT ?
                """, (strategy_id, limit)).fetchall()
            else:
                rows = cur.execute("""
                    SELECT * FROM incubation_trades
                    ORDER BY id DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def record_outcome(
        self,
        strategy_id: str,
        trade_pnl: float,
        is_win: bool,
        snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Records the outcome of an incubated paper trade and checks graduation / retirement.
        """
        now = _now_str()
        retired_data = None
        new_status = "ACTIVE"
        trades = 0
        wins = 0
        pnl = 0.0
        new_dd = 0.0

        with _inc_lock, sqlite3.connect(DB_PATH, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            row = cur.execute(
                "SELECT * FROM strategy_incubation WHERE strategy_id = ?",
                (strategy_id,)
            ).fetchone()
            if not row:
                return {}

            strat = dict(row)
            trades = strat["trades_count"] + 1
            wins = strat["wins_count"] + (1 if is_win else 0)
            pnl = strat["total_pnl"] + trade_pnl
            win_rate = wins / trades if trades > 0 else 0.0

            # Estimate drawdown
            old_dd = strat["max_drawdown"]
            new_dd = max(old_dd, abs(min(0.0, pnl)) / 100.0)
            new_status = strat["status"]

            # 1. Retirement Check (Failed in forward incubation)
            if new_dd > MAX_INCUBATION_DRAWDOWN or (trades >= 10 and win_rate < 0.40):
                new_status = "RETIRED"
                retired_data = (strat, win_rate, pnl, trades)

            # 2. Graduation Check (Met all live forward testing criteria)
            elif trades >= GRADUATION_MIN_TRADES and win_rate >= GRADUATION_MIN_WIN_RATE and pnl > 0:
                new_status = "GRADUATED"
                logger.info(
                    f"[PaperIncubator] 🌟 Strategy {strategy_id} GRADUATED! (Trades={trades}, WinRate={win_rate*100:.1f}%, PnL=${pnl:.2f})"
                )

            cur.execute("""
                UPDATE strategy_incubation
                SET trades_count = ?, wins_count = ?, total_pnl = ?,
                    max_drawdown = ?, status = ?, last_evaluated_at = ?
                WHERE strategy_id = ?
            """, (trades, wins, round(pnl, 2), round(new_dd, 3), new_status, now, strategy_id))
            conn.commit()

        # Perform audits and status updates outside incubator connection
        if retired_data:
            strat, win_rate, pnl, trades = retired_data
            logger.warning(
                f"[PaperIncubator] Strategy {strategy_id} failed incubation (DD={new_dd*100:.1f}%, WinRate={win_rate*100:.1f}%). Retiring to Graveyard."
            )
            try:
                PostMortemAuditor.audit_incubation_loss(
                    strategy_id=strategy_id,
                    name=strat["name"],
                    hypothesis=f"Forward incubation trade on {strat['asset']}",
                    asset=strat["asset"],
                    trade_data={"side": "YES" if is_win else "NO", "metrics": {"win_rate": win_rate, "pnl": pnl, "trades": trades}},
                    snapshot=snapshot
                )
            except Exception as audit_err:
                logger.error(f"[PaperIncubator] Audit error: {audit_err}")

        StrategyRegistry.update_status(
            strategy_id,
            new_status,
            incubation_metrics={"trades": trades, "win_rate": round(win_rate, 3), "pnl": round(pnl, 2), "max_drawdown": round(new_dd, 3)}
        )

        return {
            "strategy_id": strategy_id,
            "status": new_status,
            "trades": trades,
            "win_rate": round(wins / trades if trades > 0 else 0.0, 3),
            "total_pnl": round(pnl, 2),
            "drawdown": round(new_dd, 3)
        }


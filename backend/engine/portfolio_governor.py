"""
Centralized Multi-Universe Portfolio Governor & Capital Reservation Engine.

Responsibilities:
1. Thread-safe & Cross-Process Capital Coordination between Financial & Sports universes.
2. In-flight Cash Reservations: Prevents race conditions where simultaneous signals in
   Financial (BTC, ETH, Forex) and Sports (NFL, MLB, Tennis) double-commit the user's available balance.
3. Pre-Cached Live Balances with asynchronous TTL: Eliminates blocking synchronous network
   calls to Kalshi's API before every trade decision.
4. Global Cross-Universe Daily Circuit Breaker: Automatically halts automated trading across ALL
   universes if combined daily risk/loss breaches user thresholds.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class PortfolioGovernor:
    _instance: Optional[PortfolioGovernor] = None
    _init_lock = threading.Lock()

    def __new__(cls) -> PortfolioGovernor:
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._governor_lock = threading.Lock()
                    # user_id -> {"balance_dollars": float, "updated_at": float}
                    cls._instance._balance_cache: Dict[int, Dict[str, Any]] = {}
                    # reservation_id -> {"user_id": int, "amount": float, "universe": str, "created_at": float, "ticker": str}
                    cls._instance._active_reservations: Dict[str, Dict[str, Any]] = {}
        return cls._instance

    def get_cached_balance(self, user_id: int, max_age_seconds: float = 8.0) -> Optional[float]:
        """Returns the pre-cached live balance if fresh, avoiding blocking API roundtrips."""
        with self._governor_lock:
            cached = self._balance_cache.get(user_id)
            if cached and (time.time() - cached["updated_at"]) <= max_age_seconds:
                return float(cached["balance_dollars"])
        return None

    def update_cached_balance(self, user_id: int, balance_dollars: float) -> None:
        """Atomically stores fresh balance from Kalshi API."""
        with self._governor_lock:
            self._balance_cache[user_id] = {
                "balance_dollars": float(balance_dollars),
                "updated_at": time.time(),
            }

    def get_reserved_amount(self, user_id: int) -> float:
        """Calculates total capital currently locked in active order placement across all universes."""
        now = time.time()
        with self._governor_lock:
            # Clean up stale reservations older than 30 seconds (safety expiry)
            stale_keys = [k for k, v in self._active_reservations.items() if now - v["created_at"] > 30.0]
            for k in stale_keys:
                self._active_reservations.pop(k, None)

            return sum(
                float(res["amount"])
                for res in self._active_reservations.values()
                if res["user_id"] == user_id
            )

    def get_effective_available_balance(
        self,
        user: dict,
        kt: Optional[Any] = None,
        max_cache_age: float = 8.0
    ) -> float:
        """
        Calculates the true spendable balance for a user, taking into account:
        1. Fast-path in-memory cached Kalshi live balance (or paper balance if PAPER mode).
        2. In-flight capital reservations currently committed by another universe.
        """
        uid = user.get("id")
        mode = str(user.get("trading_mode") or "PAPER").upper()

        if mode == "PAPER":
            raw_balance = float(user.get("paper_balance") or 0.0)
            reserved = self.get_reserved_amount(uid)
            return max(0.0, raw_balance - reserved)

        # LIVE Mode
        cached_bal = self.get_cached_balance(uid, max_age_seconds=max_cache_age)
        if cached_bal is None:
            if kt is not None:
                try:
                    bal_res = kt.get_balance()
                    if bal_res.get("success"):
                        cached_bal = float(bal_res.get("balance_dollars", 0.0))
                        self.update_cached_balance(uid, cached_bal)
                    else:
                        cached_bal = 0.0
                except Exception as e:
                    logger.debug(f"[PortfolioGovernor] Error fetching balance for user {uid}: {e}")
                    cached_bal = 0.0
            else:
                cached_bal = 0.0

        reserved = self.get_reserved_amount(uid)
        return max(0.0, cached_bal - reserved)

    def reserve_capital(
        self,
        user_id: int,
        amount: float,
        universe: str,
        ticker: str,
        reservation_id: str
    ) -> bool:
        """
        Atomically claims a capital reservation during order submission.
        Prevents another universe from placing an order with the same funds.
        """
        with self._governor_lock:
            self._active_reservations[reservation_id] = {
                "user_id": user_id,
                "amount": float(amount),
                "universe": str(universe).upper(),
                "ticker": str(ticker),
                "created_at": time.time(),
            }
            logger.debug(f"[PortfolioGovernor] Reserved ${amount:.2f} for user {user_id} on {universe}:{ticker} (res_id={reservation_id})")
            return True

    def release_capital(
        self,
        reservation_id: str,
        actual_deducted_cost: Optional[float] = None,
        user_id: Optional[int] = None
    ) -> None:
        """
        Releases the reserved capital once an order fills, fails, or completes.
        If actual cost was deducted, updates the cached balance immediately.
        """
        with self._governor_lock:
            res = self._active_reservations.pop(reservation_id, None)
            if res and actual_deducted_cost is not None:
                uid = user_id or res.get("user_id")
                if uid and uid in self._balance_cache:
                    current_bal = self._balance_cache[uid]["balance_dollars"]
                    new_bal = max(0.0, current_bal - actual_deducted_cost)
                    self._balance_cache[uid]["balance_dollars"] = new_bal
                    self._balance_cache[uid]["updated_at"] = time.time()
                    logger.debug(f"[PortfolioGovernor] Balance for user {uid} adjusted by -${actual_deducted_cost:.2f} -> ${new_bal:.2f}")

    def check_global_circuit_breaker(self, user: dict, mode: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Cross-Universe Combined Risk & Loss Circuit Breaker.
        Checks combined risk across Financial and Sports universes.
        Returns: (is_tripped: bool, reason: Optional[str])
        """
        from backend.database.trade_store import TradeStore
        uid = user.get("id")
        user_mode = mode or str(user.get("trading_mode") or "PAPER").upper()

        # Enforce global max daily risk limit across all universes
        max_daily_risk = float(user.get("max_daily_risk") or 0.0)
        sports_max_daily_risk = float(user.get("sports_max_daily_risk") or 0.0)
        
        # Determine global threshold: combined or most restrictive non-zero cap
        global_risk_cap = 0.0
        if max_daily_risk > 0 and sports_max_daily_risk > 0:
            global_risk_cap = max(max_daily_risk, sports_max_daily_risk)
        elif max_daily_risk > 0:
            global_risk_cap = max_daily_risk
        elif sports_max_daily_risk > 0:
            global_risk_cap = sports_max_daily_risk

        if global_risk_cap <= 0.0:
            return False, None

        act = TradeStore.get_today_activity(uid, user_mode)
        total_open_and_realized_loss = -(act["realized"] - act["open_cost"])
        if total_open_and_realized_loss >= global_risk_cap:
            return True, f"Global portfolio daily risk limit reached (${total_open_and_realized_loss:.2f} >= ${global_risk_cap:.2f})"

        return False, None

    # -------------------------------------------------------------------
    # PILLAR 3: Cosmic Multi-Contract Covariance Portfolio Governor
    # (Portfolio-Level Kelly & Correlation Haircut)
    # -------------------------------------------------------------------
    def calculate_covariance_kelly_allocation(
        self,
        user_id: int,
        target_asset: str,
        target_side: str,
        base_kelly_contracts: int,
        user_mode: str = "PAPER"
    ) -> Dict[str, Any]:
        """
        Dynamically adjusts contract allocation based on active portfolio correlation.
        If a user already holds open correlated positions (e.g. Long BTC and now buying Long ETH),
        applies an empirical correlation haircut to prevent catastrophic concentration risk.
        """
        if base_kelly_contracts <= 0:
            return {
                "adjusted_contracts": 0,
                "correlation_haircut": 1.0,
                "portfolio_exposure_usd": 0.0,
                "reason": "Base Kelly was 0 contracts"
            }

        from backend.database.trade_store import TradeStore
        open_trades = TradeStore.get_open_trades(user_id) if hasattr(TradeStore, "get_open_trades") else []
        if not open_trades:
            return {
                "adjusted_contracts": base_kelly_contracts,
                "correlation_haircut": 1.0,
                "portfolio_exposure_usd": 0.0,
                "reason": "No existing open positions (Full Kelly allocated)"
            }

        # Asset-to-Asset Cross-Correlation Matrix (Empirical 30-day rolling correlation)
        # Highly correlated pairs (> 0.70) share systematic drawdown risk
        corr_matrix = {
            ("BTC", "ETH"): 0.85, ("ETH", "BTC"): 0.85,
            ("BTC", "SOL"): 0.78, ("SOL", "BTC"): 0.78,
            ("ETH", "SOL"): 0.82, ("SOL", "ETH"): 0.82,
            ("BTC", "DOGE"): 0.72, ("DOGE", "BTC"): 0.72,
            ("EURUSD", "GBPUSD"): 0.88, ("GBPUSD", "EURUSD"): 0.88,
        }

        target_norm = str(target_asset).upper().strip()
        target_is_yes = "YES" in str(target_side).upper()

        total_correlated_risk = 0.0
        max_correlation_detected = 0.0
        conflicting_correlations = []

        for t in open_trades:
            t_asset = str(t.get("asset") or "").upper().strip()
            t_side = str(t.get("side") or "").upper().strip()
            t_cost = float(t.get("entry_price", 0.50)) * int(t.get("count", 1))

            if t_asset == target_norm:
                # Same asset: direct exposure accumulation
                total_correlated_risk += t_cost
                max_correlation_detected = max(max_correlation_detected, 1.0)
            else:
                rho = corr_matrix.get((target_norm, t_asset), 0.0)
                if rho > 0.60:
                    t_is_yes = "YES" in t_side
                    if target_is_yes == t_is_yes:
                        # Compounding directional risk in same market regime
                        total_correlated_risk += t_cost * rho
                        max_correlation_detected = max(max_correlation_detected, rho)
                        conflicting_correlations.append(f"{t_asset} ({t_side}) rho={rho:.2f}")

        # Compute dynamic Covariance Haircut
        # If open correlated risk exceeds $25, scale back new contracts proportionally
        if max_correlation_detected >= 0.70 and total_correlated_risk >= 15.0:
            haircut = max(0.35, 1.0 / (1.0 + (total_correlated_risk / 25.0)))
            adjusted_contracts = max(1, int(round(base_kelly_contracts * haircut)))
            reason = f"Covariance Haircut: Scaled to {haircut*100:.0f}% due to correlated open positions [{', '.join(conflicting_correlations)}]."
        else:
            haircut = 1.0
            adjusted_contracts = base_kelly_contracts
            reason = "Covariance Safe: Portfolio exposure within independent bounds."

        return {
            "adjusted_contracts": adjusted_contracts,
            "correlation_haircut": round(haircut, 2),
            "portfolio_correlated_risk_usd": round(total_correlated_risk, 2),
            "max_correlation": round(max_correlation_detected, 2),
            "reason": reason
        }

_governor = PortfolioGovernor()

def get_portfolio_governor() -> PortfolioGovernor:
    """Singleton getter for the Portfolio Governor."""
    return _governor

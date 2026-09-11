"""
Kalshi Authenticated Trading Service
Handles RSA-PSS signed API communications, portfolio balance checks,
market discovery for KXBTC15M contracts, and live/paper order execution.
"""

import os
import time
import json
import uuid
import base64
import requests
from urllib.parse import quote
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from zoneinfo import ZoneInfo
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# Kalshi's documented production Trade API host.
BASE_URL = "https://external-api.kalshi.com"
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kalshi_credentials.json")


class KalshiTrader:
    def __init__(self, key_id: Optional[str] = None, private_key_pem: Optional[str] = None):
        self.key_id = key_id or os.environ.get("KALSHI_KEY_ID")
        self.private_key_pem = private_key_pem or os.environ.get("KALSHI_PRIVATE_KEY")
        self._private_key_obj = None

        if not self.key_id or not self.private_key_pem:
            self._load_from_credentials_file()

        self._cached_balance = None
        self._cached_balance_time = 0.0
        self._cached_market = None
        self._cached_market_time = 0.0

        if self.private_key_pem:
            try:
                self._private_key_obj = load_pem_private_key(self.private_key_pem.encode("utf-8"), password=None)
            except Exception as e:
                print(f"[KalshiTrader] Error loading private key: {e}")

    def _load_from_credentials_file(self):
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.key_id = data.get("key_id", self.key_id)
                    self.private_key_pem = data.get("private_key", self.private_key_pem)
            except Exception as e:
                print(f"[KalshiTrader] Error reading credentials file: {e}")

    def is_authenticated(self) -> bool:
        return bool(self.key_id and self._private_key_obj)

    def _sign_headers(self, method: str, path: str) -> Dict[str, str]:
        if not self.is_authenticated():
            raise ValueError("Kalshi API credentials not configured or private key invalid.")

        timestamp = str(int(time.time() * 1000))
        msg_string = timestamp + method.upper() + path

        signature = self._private_key_obj.sign(
            msg_string.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": signature_b64,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def get_balance(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Retrieves live portfolio balance and dollar breakdown (cached for 4.0s for sub-ms polling).
        """
        now = time.time()
        if not force_refresh and self._cached_balance and (now - self._cached_balance_time < 4.0):
            return self._cached_balance

        path = "/trade-api/v2/portfolio/balance"
        try:
            headers = self._sign_headers("GET", path)
            resp = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                dollars = float(data.get("balance_dollars", 0.0))
                cents = int(data.get("balance", 0))
                port_val = float(data.get("portfolio_value", 0.0))
                res = {
                    "success": True,
                    "balance_dollars": dollars,
                    "balance_cents": cents,
                    "portfolio_value": port_val,
                    "updated_ts": data.get("updated_ts"),
                    "raw": data
                }
                self._cached_balance = res
                self._cached_balance_time = now
                return res
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text}",
                "balance_dollars": 0.0,
                "balance_cents": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "balance_dollars": 0.0,
                "balance_cents": 0
            }

    def get_active_15m_market(self, allow_synthetic: bool = True, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Finds the active KXBTC15M market (cached for 2.5s for ultra-low latency real-time feeds).
        """
        now_ts = time.time()
        if not force_refresh and self._cached_market and (now_ts - self._cached_market_time < 2.5):
            # Synthetic contracts are useful only for paper trading. Never
            # surface one to the live-order path from the short-lived cache.
            if allow_synthetic or not self._cached_market.get("is_synthetic"):
                return self._cached_market

        path = "/trade-api/v2/markets"
        try:
            resp = requests.get(
                f"{BASE_URL}{path}",
                params={"series_ticker": "KXBTC15M", "status": "open", "limit": 100},
                headers={"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"},
                timeout=3.0
            )
            if resp.status_code == 200:
                data = resp.json()
                markets = data.get("markets", [])
                import datetime
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                valid_m = []
                for m in markets:
                    ct_str = m.get("close_time")
                    if ct_str:
                        try:
                            ct = datetime.datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                            if ct > now_utc and m.get("status") in ["active", "open"]:
                                valid_m.append((ct, m))
                        except Exception:
                            pass
                if valid_m:
                    valid_m.sort(key=lambda x: x[0])
                    active_m = valid_m[0][1]
                    floor_strike = active_m.get("floor_strike")
                    yes_bid = float(active_m.get("yes_bid_dollars") or (float(active_m.get("yes_bid") or 0) / 100.0))
                    yes_ask = float(active_m.get("yes_ask_dollars") or (float(active_m.get("yes_ask") or 0) / 100.0))
                    no_bid = float(active_m.get("no_bid_dollars") or (float(active_m.get("no_bid") or 0) / 100.0))
                    no_ask = float(active_m.get("no_ask_dollars") or (float(active_m.get("no_ask") or 0) / 100.0))
                    last_price = float(active_m.get("last_price_dollars") or (float(active_m.get("last_price") or 0) / 100.0))
                    if yes_ask == 0.0: yes_ask = 0.58
                    if no_ask == 0.0: no_ask = 0.42

                    res_market = {
                        "ticker": active_m.get("ticker", ""),
                        "title": active_m.get("title", ""),
                        "strike_price": float(floor_strike) if floor_strike is not None else None,
                        "close_time": active_m.get("close_time", ""),
                        "yes_bid": yes_bid,
                        "yes_ask": yes_ask,
                        "no_bid": no_bid,
                        "no_ask": no_ask,
                        "last_price": last_price,
                        "volume_24h": float(active_m.get("volume_24h_fp") or 0.0),
                        "status": active_m.get("status", "open"),
                        "is_synthetic": False,
                    }
                    self._cached_market = res_market
                    self._cached_market_time = now_ts
                    return res_market
        except Exception as e:
            print(f"[KalshiTrader] Error getting active 15M market: {e}")

        if not allow_synthetic:
            return None

        # Interval Fallback: active contract for current 15M interval
        try:
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            mins = (now.minute // 15 + 1) * 15
            close_dt = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(minutes=mins)
            close_time_iso = close_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            ticker_suffix = close_dt.strftime("%y%b%d%H%M").upper()
            ticker = f"KXBTC15M-{ticker_suffix}"

            from backend.btc.data_fetcher import get_btc_ticker, get_live_15m_target_data
            target_data = get_live_15m_target_data()
            target_pr = target_data.get("target_price") or get_btc_ticker().get("price", 78000.0)

            return {
                "ticker": ticker,
                "title": f"Bitcoin above ${target_pr:,.2f} at {close_dt.strftime('%H:%M')} UTC",
                "strike_price": target_pr,
                "close_time": close_time_iso,
                "yes_bid": 0.55,
                "yes_ask": 0.58,
                "no_bid": 0.42,
                "no_ask": 0.45,
                "last_price": 0.58,
                "volume_24h": 1250.0,
                "status": "active",
                "is_synthetic": True,
            }
        except Exception as e:
            print(f"[KalshiTrader] Error generating interval contract: {e}")
            return None

    def get_positions(self) -> Dict[str, Any]:
        """
        Fetch current portfolio open positions.
        """
        path = "/trade-api/v2/portfolio/positions"
        try:
            headers = self._sign_headers("GET", path)
            resp = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                return {"success": True, "positions": data.get("market_positions", [])}
            return {"success": False, "error": resp.text, "positions": []}
        except Exception as e:
            return {"success": False, "error": str(e), "positions": []}

    def place_order(
        self,
        ticker: str,
        side: str,  # 'yes' or 'no'
        count: int = 1,
        limit_price_dollars: Optional[float] = None,
        dry_run: bool = True,
        order_type: str = "limit"
    ) -> Dict[str, Any]:
        """
        Executes a buy order on the specified contract side (YES = above target, NO = below target).
        In dry_run=True, simulates the trade and returns immediate simulated fill.
        In dry_run=False, signs and sends the order to the Kalshi live API with strict safety bounds.
        """
        side_clean = side.lower().strip()
        if side_clean not in ["yes", "no"]:
            return {"success": False, "error": f"Invalid side: {side}. Must be 'yes' or 'no'."}

        client_order_id = str(uuid.uuid4())
        count = max(1, min(count, 5))  # Safety limit: never trade more than 5 contracts per signal

        # 1. PAPER TRADING (SIMULATION)
        if dry_run:
            simulated_price = limit_price_dollars if limit_price_dollars else 0.50
            cost = round(simulated_price * count, 4)
            return {
                "success": True,
                "mode": "PAPER",
                "order_id": f"sim_{client_order_id[:8]}",
                "client_order_id": client_order_id,
                "ticker": ticker,
                "side": side_clean.upper(),
                "action": "BUY",
                "count": count,
                "filled_price": simulated_price,
                "total_cost": cost,
                "status": "FILLED (SIMULATED)",
                "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                "message": f"Simulated BUY of {count} {side_clean.upper()} on {ticker} @ ${simulated_price:.2f}"
            }

        # 2. LIVE TRADING EXECUTION
        # Never submit a live order against a locally constructed ticker. Fetch
        # Kalshi's open market immediately before ordering and require an exact
        # ticker match to prevent market_not_found orders around contract rollover.
        verified_market = self.get_active_15m_market(allow_synthetic=False, force_refresh=True)
        if not verified_market or verified_market.get("is_synthetic"):
            return {
                "success": False,
                "error": "No verified open Kalshi BTC 15M market is available. Live order was not submitted."
            }
        verified_ticker = verified_market.get("ticker", "")
        if not verified_ticker or ticker != verified_ticker:
            return {
                "success": False,
                "error": "Kalshi market changed or expired before submission. Refresh and select the currently open market.",
                "requested_ticker": ticker,
                "verified_ticker": verified_ticker
            }

        # Confirm the exact ticker still exists and is open. The list endpoint
        # can cross a 15-minute rollover between discovery and submission.
        market_path = f"/trade-api/v2/markets/{quote(verified_ticker, safe='')}"
        try:
            market_resp = requests.get(
                f"{BASE_URL}{market_path}",
                headers={"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"},
                timeout=3.0,
            )
            market_data = market_resp.json().get("market", {}) if market_resp.status_code == 200 else {}
            market_status = str(market_data.get("status", "")).lower()
            if market_resp.status_code != 200 or market_status not in {"active", "open"}:
                return {
                    "success": False,
                    "error": "Kalshi market expired or is no longer open. Live order was not submitted.",
                    "verified_ticker": verified_ticker,
                }
        except Exception as e:
            return {"success": False, "error": f"Cannot re-verify Kalshi market: {e}. Live order was not submitted."}

        # Clamp the outcome price before using it for balance validation.
        outcome_price = max(0.01, min(float(limit_price_dollars if limit_price_dollars else 0.65), 0.99))

        # Double check balance before submitting
        bal_res = self.get_balance(force_refresh=True)
        if not bal_res.get("success", False):
            return {"success": False, "error": f"Cannot verify live balance: {bal_res.get('error')}"}

        live_balance = bal_res.get("balance_dollars", 0.0)
        est_cost = outcome_price * count

        if live_balance < est_cost:
            return {
                "success": False,
                "error": f"Insufficient funds: Balance ${live_balance:.2f} is less than required ${est_cost:.2f}."
            }

        # V2 endpoint: POST /portfolio/events/orders
        # The V2 event book is always quoted from the YES side. "ask" is
        # economically a buy-NO, so a NO price must be converted to its
        # complementary YES price before submission.
        # count: fixed-point count string e.g. "1.00"
        v2_side = "bid" if side_clean == "yes" else "ask"
        book_price = outcome_price if side_clean == "yes" else (1.0 - outcome_price)
        v2_payload = {
            "ticker": ticker,
            "client_order_id": client_order_id,
            "side": v2_side,
            "count": f"{int(count)}.00",
            "price": f"{book_price:.4f}",
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": False,
            "cancel_order_on_pause": True,
            "reduce_only": False,
            "subaccount": 0,
            "exchange_index": 0
        }

        path = "/trade-api/v2/portfolio/events/orders"
        try:
            headers = self._sign_headers("POST", path)
            resp = requests.post(f"{BASE_URL}{path}", json=v2_payload, headers=headers, timeout=5.0)

            if resp.status_code in [200, 201]:
                self._cached_balance_time = 0.0
                self._cached_market_time = 0.0
                res_data = resp.json()
                fill_count = float(res_data.get("fill_count", "0") or "0")
                avg_book_fill = float(res_data.get("average_fill_price", str(book_price)) or str(book_price))
                avg_outcome_fill = round(
                    avg_book_fill if side_clean == "yes" else (1.0 - avg_book_fill),
                    4,
                )
                return {
                    "success": True,
                    "mode": "LIVE",
                    "order_id": res_data.get("order_id", client_order_id),
                    "client_order_id": res_data.get("client_order_id", client_order_id),
                    "ticker": ticker,
                    "side": side_clean.upper(),
                    "action": "BUY",
                    "count": count,
                    "filled_price": avg_outcome_fill if fill_count > 0 else outcome_price,
                    "fill_count": fill_count,
                    "total_cost": round(avg_outcome_fill * fill_count if fill_count > 0 else outcome_price * count, 4),
                    "status": "FILLED" if fill_count > 0 else "RESTING",
                    "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "raw_response": res_data
                }
            else:
                err_text = resp.text
                if resp.status_code == 409 and "trading_is_paused" in err_text:
                    user_msg = "Kalshi Exchange Maintenance: Trading is paused for weekly maintenance until 5:00 AM EDT. Orders will resume at 5:00 AM EDT."
                elif "market_not_open" in err_text or "not open" in err_text.lower():
                    user_msg = "Kalshi Market Not Open: Waiting for 15M contract open window."
                else:
                    user_msg = err_text
                return {
                    "success": False,
                    "error": f"Kalshi Order Rejected (HTTP {resp.status_code}): {user_msg}",
                    "payload_sent": v2_payload
                }
        except Exception as e:
            return {"success": False, "error": f"Order execution exception: {str(e)}"}


# Global singleton instance
kalshi_trader = KalshiTrader()

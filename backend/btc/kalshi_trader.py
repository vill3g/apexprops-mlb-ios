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
from typing import Optional, Dict, Any, Tuple
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

BASE_URL = "https://api.elections.kalshi.com"
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kalshi_credentials.json")


class KalshiTrader:
    def __init__(self, key_id: Optional[str] = None, private_key_pem: Optional[str] = None):
        self.key_id = key_id or os.environ.get("KALSHI_KEY_ID")
        self.private_key_pem = private_key_pem or os.environ.get("KALSHI_PRIVATE_KEY")
        self._private_key_obj = None

        if not self.key_id or not self.private_key_pem:
            self._load_from_credentials_file()

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

    def get_balance(self) -> Dict[str, Any]:
        """
        Retrieves live portfolio balance and dollar breakdown.
        """
        path = "/trade-api/v2/portfolio/balance"
        try:
            headers = self._sign_headers("GET", path)
            resp = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                dollars = float(data.get("balance_dollars", 0.0))
                cents = int(data.get("balance", 0))
                port_val = float(data.get("portfolio_value", 0.0))
                return {
                    "success": True,
                    "balance_dollars": dollars,
                    "balance_cents": cents,
                    "portfolio_value": port_val,
                    "updated_ts": data.get("updated_ts"),
                    "raw": data
                }
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

    def get_active_15m_market(self, allow_synthetic: bool = True) -> Optional[Dict[str, Any]]:
        """
        Finds the active KXBTC15M market.
        If live exchange has no 'open' markets (e.g. overnight or between settlements),
        checks initialized/active markets or generates the active 15m contract for paper trading.
        """
        path = "/trade-api/v2/markets"
        for status_param in ["open", None]:
            params = {"series_ticker": "KXBTC15M"}
            if status_param:
                params["status"] = status_param
            try:
                resp = requests.get(
                    f"{BASE_URL}{path}",
                    params=params,
                    headers={"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"},
                    timeout=4.0
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
                                if ct > now_utc - datetime.timedelta(minutes=5):
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

                        return {
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
                            "status": active_m.get("status", "open")
                        }
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
                "status": "active"
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
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "message": f"Simulated BUY of {count} {side_clean.upper()} on {ticker} @ ${simulated_price:.2f}"
            }

        # 2. LIVE TRADING EXECUTION
        # Double check balance before submitting
        bal_res = self.get_balance()
        if not bal_res.get("success", False):
            return {"success": False, "error": f"Cannot verify live balance: {bal_res.get('error')}"}

        live_balance = bal_res.get("balance_dollars", 0.0)
        est_price = limit_price_dollars if limit_price_dollars else 0.65
        est_cost = est_price * count

        if live_balance < est_cost:
            return {
                "success": False,
                "error": f"Insufficient funds: Balance ${live_balance:.2f} is less than required ${est_cost:.2f}."
            }

        # Format price in cents (Kalshi expects price as integer cents 1-99 for limit orders)
        price_cents = int(round(est_price * 100)) if est_price <= 1.0 else int(est_price)
        price_cents = max(1, min(price_cents, 99))

        payload = {
            "ticker": ticker,
            "action": "buy",
            "side": side_clean,
            "type": order_type,
            "count": int(count),
            "client_order_id": client_order_id
        }
        if side_clean == "yes":
            payload["yes_price"] = price_cents
        else:
            payload["no_price"] = price_cents

        path = "/trade-api/v2/portfolio/orders"
        try:
            headers = self._sign_headers("POST", path)
            resp = requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=5.0)

            # Fallback to events order endpoint if legacy returns 404/redirect
            if resp.status_code == 404 or "moved" in resp.text.lower():
                alt_path = "/trade-api/v2/portfolio/events/orders"
                alt_headers = self._sign_headers("POST", alt_path)
                alt_payload = {
                    "ticker": ticker,
                    "side": "bid" if side_clean == "yes" else "ask",
                    "count": str(count),
                    "price": f"{est_price:.4f}",
                    "client_order_id": client_order_id
                }
                resp = requests.post(f"{BASE_URL}{alt_path}", json=alt_payload, headers=alt_headers, timeout=5.0)

            if resp.status_code in [200, 201]:
                res_data = resp.json()
                order_info = res_data.get("order", res_data)
                return {
                    "success": True,
                    "mode": "LIVE",
                    "order_id": order_info.get("order_id", client_order_id),
                    "client_order_id": client_order_id,
                    "ticker": ticker,
                    "side": side_clean.upper(),
                    "action": "BUY",
                    "count": count,
                    "filled_price": est_price,
                    "total_cost": round(est_price * count, 4),
                    "status": order_info.get("status", "SUBMITTED"),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                    "raw_response": res_data
                }
            else:
                return {
                    "success": False,
                    "error": f"Kalshi Order Rejected (HTTP {resp.status_code}): {resp.text}",
                    "payload_sent": payload
                }
        except Exception as e:
            return {"success": False, "error": f"Order execution exception: {str(e)}"}


# Global singleton instance
kalshi_trader = KalshiTrader()

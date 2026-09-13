"""
Kalshi Authenticated Trading Service
Handles RSA-PSS signed API communications, portfolio balance checks,
market discovery for KXBTC15M contracts, and live/paper order execution.
"""

import logging
logger = logging.getLogger(__name__)
import os
import time
import json
import uuid
import base64
import threading
import requests
from urllib.parse import quote
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
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
        self._lock = threading.Lock()

        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Dedicated session for order-mutating endpoints (place_order, close_position)
        # with max_retries=0 to prevent duplicate fills on network timeouts.
        self.order_session = requests.Session()
        order_adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
        self.order_session.mount("https://", order_adapter)
        self.order_session.mount("http://", order_adapter)

        if self.private_key_pem:
            try:
                self._private_key_obj = load_pem_private_key(self.private_key_pem.encode("utf-8"), password=None)
            except Exception as e:
                logger.error(f"[KalshiTrader] Error loading private key: {e}")

    def _load_from_credentials_file(self):
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.key_id = data.get("key_id", self.key_id)
                    self.private_key_pem = data.get("private_key", self.private_key_pem)
            except Exception as e:
                logger.error(f"[KalshiTrader] Error reading credentials file: {e}")

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
        with self._lock:
            if not force_refresh and self._cached_balance and (now - self._cached_balance_time < 4.0):
                return self._cached_balance

        path = "/trade-api/v2/portfolio/balance"
        try:
            headers = self._sign_headers("GET", path)
            resp = self.session.get(f"{BASE_URL}{path}", headers=headers, timeout=5.0)
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
                with self._lock:
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
        with self._lock:
            if not force_refresh and self._cached_market and (now_ts - self._cached_market_time < 2.5):
                # Synthetic contracts are useful only for paper trading. Never
                # surface one to the live-order path from the short-lived cache.
                if allow_synthetic or not self._cached_market.get("is_synthetic"):
                    return self._cached_market

        path = "/trade-api/v2/markets"
        try:
            # Retrieve market list with signed authentication
            headers = self._sign_headers('GET', path)
            resp = self.session.get(
                f"{BASE_URL}{path}",
                params={"series_ticker": "KXBTC15M", "status": "open", "limit": 100},
                headers=headers,
                timeout=5.0,
            )
            if resp.status_code != 200:
                raise Exception(f"Market list request failed with status {resp.status_code}")
            data = resp.json()
            markets = data.get("markets", [])
            now_utc = datetime.now(timezone.utc)
            valid = []
            for m in markets:
                ct_str = m.get("close_time")
                if ct_str:
                    try:
                        ct = datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                        if ct > now_utc and m.get("status") in ["active", "open"]:
                            valid.append((ct, m))
                    except Exception:
                        pass
            if valid:
                ct, active_m = min(valid, key=lambda x: x[0])

                def _to_dollars(val):
                    """Convert a Kalshi bid/ask value: if > 1.0 assume cents, divide by 100."""
                    try:
                        v = float(val or 0.0)
                        return round(v / 100.0, 4) if v > 1.0 else v
                    except Exception:
                        return 0.0

                yes_bid = _to_dollars(active_m.get("yes_bid") or active_m.get("yes_bid_dollars"))
                yes_ask = _to_dollars(active_m.get("yes_ask") or active_m.get("yes_ask_dollars"))
                no_bid  = _to_dollars(active_m.get("no_bid")  or active_m.get("no_bid_dollars"))
                no_ask  = _to_dollars(active_m.get("no_ask")  or active_m.get("no_ask_dollars"))
                last_price = _to_dollars(active_m.get("last_price") or active_m.get("last_price_dollars"))

                # If the authenticated API returned all zeros, fallback to public client
                if yes_bid == 0.0 and yes_ask == 0.0:
                    try:
                        from backend.btc.kalshi_client import get_kalshi_15m_market
                        pub = get_kalshi_15m_market()
                        if pub:
                            yes_bid    = float(pub.get("yes_bid")  or yes_bid)
                            yes_ask    = float(pub.get("yes_ask")  or yes_ask)
                            no_bid     = float(pub.get("no_bid")   or no_bid)
                            no_ask     = float(pub.get("no_ask")   or no_ask)
                            last_price = float(pub.get("last_price") or pub.get("yes_bid") or last_price)
                    except Exception:
                        pass

                floor_strike = active_m.get("floor_strike")
                strike_price = active_m.get("strike_price")
                if not strike_price and floor_strike is not None:
                    strike_price = floor_strike

                res_market = {
                    "ticker": active_m.get("ticker") or active_m.get("event_ticker"),
                    "event_ticker": active_m.get("event_ticker", ""),
                    "title": active_m.get("title", ""),
                    "strike_price": float(strike_price or 0.0),
                    "close_time": active_m.get("close_time", ""),
                    "yes_bid": yes_bid,
                    "yes_ask": yes_ask,
                    "no_bid": no_bid,
                    "no_ask": no_ask,
                    "last_price": last_price,
                    "volume_24h": float(active_m.get("volume_24h_fp") or 0.0),
                    "status": active_m.get("status", "open"),
                    "exchange_index": active_m.get("exchange_index"),
                    "is_synthetic": False,
                }
                with self._lock:
                    self._cached_market = res_market
                    self._cached_market_time = now_ts
                return res_market
        except Exception as e:
            logger.error(f"[KalshiTrader] Error getting active 15M market: {e}")
        # Synthetic fallback if allowed — enrich with public client data for live P&L
        if allow_synthetic:
            pub_yes_bid, pub_yes_ask, pub_no_bid, pub_no_ask = 0.0, 0.0, 0.0, 0.0
            pub_strike = 0.0
            try:
                from backend.btc.kalshi_client import get_kalshi_15m_market
                from backend.btc.data_fetcher import get_btc_ticker
                pub = get_kalshi_15m_market()
                if pub:
                    pub_yes_bid = float(pub.get("yes_bid") or 0.0)
                    pub_yes_ask = float(pub.get("yes_ask") or 0.0)
                    pub_no_bid  = float(pub.get("no_bid")  or 0.0)
                    pub_no_ask  = float(pub.get("no_ask")  or 0.0)
                    pub_strike  = float(pub.get("target_price") or pub.get("strike") or pub.get("floor_strike") or 0.0)
                
                if pub_strike <= 0.0:
                    pub_strike = float(get_btc_ticker().get("price", 0.0))
            except Exception:
                pass
            return {
                "ticker": "KXBTC15M_SYNTH",
                "title": "Synthetic BTC 15M",
                "strike_price": pub_strike,
                "close_time": "",
                "yes_bid": pub_yes_bid,
                "yes_ask": pub_yes_ask,
                "no_bid": pub_no_bid,
                "no_ask": pub_no_ask,
                "last_price": pub_yes_bid,
                "volume_24h": 0.0,
                "status": "synthetic",
                "is_synthetic": True,
            }
        return None

    def get_market_result(self, ticker: str) -> Dict[str, Any]:
        """Return Kalshi's official result for one exact market ticker."""
        clean_ticker = str(ticker or "").strip()
        if not clean_ticker or clean_ticker.endswith("_SYNTH"):
            return {"success": False, "result": "", "error": "No official Kalshi ticker available."}

        path = f"/trade-api/v2/markets/{quote(clean_ticker, safe='')}"
        try:
            resp = self.session.get(
                f"{BASE_URL}{path}",
                headers={"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"},
                timeout=5.0,
            )
            if resp.status_code != 200:
                return {
                    "success": False,
                    "result": "",
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                }
            market = resp.json().get("market", {})
            result = str(market.get("result") or "").strip().lower()
            return {
                "success": True,
                "result": result if result in {"yes", "no"} else "",
                "status": str(market.get("status") or "").lower(),
                "market": market,
            }
        except Exception as e:
            return {"success": False, "result": "", "error": str(e)}

    def get_market_quote(self, ticker: str) -> Dict[str, Any]:
        """Return executable YES/NO bid prices for one exact open market."""
        clean_ticker = str(ticker or "").strip()
        if not clean_ticker or clean_ticker.endswith("_SYNTH"):
            return {"success": False, "error": "No official Kalshi ticker available."}

        def as_dollars(market: Dict[str, Any], field: str) -> float:
            value = market.get(f"{field}_dollars")
            if value is None:
                value = market.get(field)
            try:
                price = float(value)
                return round(price / 100.0, 4) if price > 1.0 else round(price, 4)
            except (TypeError, ValueError):
                return 0.0

        path = f"/trade-api/v2/markets/{quote(clean_ticker, safe='')}"
        try:
            resp = self.session.get(
                f"{BASE_URL}{path}",
                headers={"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"},
                timeout=5.0,
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
            market = resp.json().get("market", {})
            status = str(market.get("status") or "").lower()
            if status not in {"active", "open"}:
                return {"success": False, "error": f"Market is not open (status: {status or 'unknown'})."}
            return {
                "success": True,
                "ticker": clean_ticker,
                "yes_bid": as_dollars(market, "yes_bid"),
                "no_bid": as_dollars(market, "no_bid"),
                "exchange_index": market.get("exchange_index"),
                "market": market,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_position(
        self,
        ticker: str,
        purchased_side: str,
        count: float,
        dry_run: bool = True,
        estimated_exit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Exit an existing YES/NO position at its current executable bid.

        Event-market V2 orders are quoted on the YES price scale.  Reducing a
        YES position means submitting an ask at the YES bid; reducing a NO
        position means submitting a bid at ``1 - no_bid``.  ``reduce_only``
        prevents this endpoint from opening an opposite position on a stale or
        partially closed trade.
        """
        side = str(purchased_side or "").upper().strip()
        if side not in {"YES", "NO"}:
            return {"success": False, "error": "Position side must be YES or NO."}
        try:
            requested_count = float(count)
        except (TypeError, ValueError):
            return {"success": False, "error": "Position count is invalid."}
        if requested_count <= 0:
            return {"success": False, "error": "Position count must be positive."}

        quote_data = self.get_market_quote(ticker)
        exit_price = 0.0
        if quote_data.get("success"):
            raw_exit_price = quote_data.get("yes_bid") if side == "YES" else quote_data.get("no_bid")
            try:
                exit_price = float(raw_exit_price or 0.0)
            except (TypeError, ValueError):
                exit_price = 0.0

        if dry_run:
            if not (0.0 < exit_price < 1.0):
                if estimated_exit_price is not None and 0.0 < estimated_exit_price < 1.0:
                    exit_price = round(float(estimated_exit_price), 4)
                else:
                    exit_price = 0.50
            return {
                "success": True,
                "mode": "PAPER",
                "filled_count": requested_count,
                "remaining_count": 0.0,
                "exit_price": exit_price,
                "fee_paid": 0.0,
                "source": "kalshi_public_bid" if quote_data.get("success") else "simulated_dynamic_quote",
            }

        if not quote_data.get("success"):
            return quote_data
        if not 0.0 < exit_price < 1.0:
            return {"success": False, "error": f"No executable {side} bid is available to close this position."}

        if not self.is_authenticated():
            return {"success": False, "error": "Kalshi credentials are not configured."}

        # V2 prices always use the YES-price scale. See Kalshi's event order API:
        # To sell YES: submit an ask at YES bid (with 0.02 slippage cushion to cross book immediately)
        # To sell NO: submit a bid on YES at 1 - no_bid (with 0.02 slippage cushion)
        book_side = "ask" if side == "YES" else "bid"
        if side == "YES":
            book_price = max(0.01, min(0.99, exit_price - 0.02))
        else:
            book_price = min(0.99, max(0.01, (1.0 - exit_price) + 0.02))

        client_order_id = str(uuid.uuid4())
        path = "/trade-api/v2/portfolio/events/orders"
        payload = {
            "ticker": quote_data["ticker"],
            "client_order_id": client_order_id,
            "side": book_side,
            "count": f"{requested_count:.2f}",
            "price": f"{book_price:.4f}",
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": False,
            "cancel_order_on_pause": True,
            "reduce_only": True,
        }
        if quote_data.get("exchange_index") is not None:
            payload["exchange_index"] = quote_data["exchange_index"]
        try:
            resp = self.order_session.post(f"{BASE_URL}{path}", json=payload, headers=self._sign_headers("POST", path), timeout=5.0)
            if resp.status_code not in {200, 201}:
                return {"success": False, "error": f"Kalshi close rejected (HTTP {resp.status_code}): {resp.text}"}
            data = resp.json()
            filled_count = float(data.get("fill_count", "0") or "0")
            if filled_count <= 0:
                return {"success": False, "error": "Close order received no fill; the local trade remains open."}
            average_book_price = float(data.get("average_fill_price", str(book_price)) or book_price)
            realized_exit_price = average_book_price if side == "YES" else (1.0 - average_book_price)
            average_fee = float(data.get("average_fee_paid", "0") or "0")
            self._cached_balance_time = 0.0
            return {
                "success": True,
                "mode": "LIVE",
                "order_id": data.get("order_id", client_order_id),
                "client_order_id": data.get("client_order_id", client_order_id),
                "filled_count": filled_count,
                "remaining_count": max(0.0, requested_count - filled_count),
                "exit_price": round(realized_exit_price, 4),
                "fee_paid": round(average_fee * filled_count, 4),
                "source": "kalshi_reduce_only_exit",
            }
        except Exception as e:
            return {"success": False, "error": f"Kalshi close request failed: {e}"}

    def get_positions(self) -> Dict[str, Any]:
        """
        Fetch current portfolio open positions.
        """
        path = "/trade-api/v2/portfolio/positions"
        try:
            headers = self._sign_headers("GET", path)
            resp = self.session.get(f"{BASE_URL}{path}", headers=headers, timeout=5.0)
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
        order_type: str = "limit",
        slippage_buffer_cents: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes a buy order on the specified contract side (YES = above target, NO = below target).
        In dry_run=True, simulates the trade and returns immediate simulated fill.
        In dry_run=False, signs and sends the order to the Kalshi live API with strict safety bounds.
        """
        # H5: Validate contract count is a strictly positive whole integer
        try:
            if not isinstance(count, (int, float)) or count <= 0:
                return {"success": False, "error": f"Invalid order count: {count}. Must be a positive whole integer."}
            if isinstance(count, float) and not count.is_integer():
                return {"success": False, "error": f"Invalid fractional contract count: {count}. Kalshi event contracts require whole integers."}
            count_int = int(count)
        except Exception:
            return {"success": False, "error": f"Invalid order count: {count}."}

        side_clean = side.lower().strip()
        if side_clean not in ["yes", "no"]:
            return {"success": False, "error": f"Invalid side: {side}. Must be 'yes' or 'no'."}

        client_order_id = str(uuid.uuid4())

        # Slippage buffer: Default 0.04 or configurable value clamped safely [0.00, 0.15]
        buf = 0.04
        if slippage_buffer_cents is not None:
            try:
                buf = max(0.0, min(float(slippage_buffer_cents), 0.15))
            except (ValueError, TypeError):
                buf = 0.04

        # 1. PAPER TRADING (SIMULATION)
        if dry_run:
            simulated_price = limit_price_dollars if limit_price_dollars is not None else 0.50
            cost = round(simulated_price * count_int, 4)
            return {
                "success": True,
                "mode": "PAPER",
                "order_id": f"sim_{client_order_id[:8]}",
                "client_order_id": client_order_id,
                "ticker": ticker,
                "side": side_clean.upper(),
                "action": "BUY",
                "count": count_int,
                "requested_price": simulated_price,
                "filled_price": simulated_price,
                "total_cost": cost,
                "slippage_buffer": buf,
                "status": "FILLED (SIMULATED)",
                "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                "message": f"Simulated BUY of {count_int} {side_clean.upper()} on {ticker} @ ${simulated_price:.2f}"
            }

        # Fast-Path: Use active market (from cache or fast fetch) without redundant GET roundtrips
        verified_market = self.get_active_15m_market(allow_synthetic=False, force_refresh=False)
        if not verified_market or verified_market.get("is_synthetic"):
            # Fallback to force refresh if cache empty
            verified_market = self.get_active_15m_market(allow_synthetic=False, force_refresh=True)
            if not verified_market or verified_market.get("is_synthetic"):
                return {
                    "success": False,
                    "error": "No verified open Kalshi BTC 15M market is available. Live order was not submitted."
                }
        
        verified_ticker = verified_market.get("ticker") or verified_market.get("event_ticker", "")
        if not verified_ticker:
            return {"success": False, "error": "Verified market missing ticker information."}
            
        ticker = verified_ticker
        
        # Clamp price with slippage buffer to guarantee Immediate-Or-Cancel (IOC) book cross
        raw_price = float(limit_price_dollars if limit_price_dollars else 0.65)
        outcome_price = max(0.01, min(raw_price + buf, 0.99))

        # H4: Fail-closed balance check on live trading
        bal_res = self.get_balance(force_refresh=True)
        if not bal_res.get("success"):
            return {
                "success": False,
                "error": f"Live order aborted: Unable to verify Kalshi account balance ({bal_res.get('error', 'Balance check failed')})."
            }
        live_balance = float(bal_res.get("balance_dollars", 0.0))
        est_cost = outcome_price * count_int

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
            "count": f"{count_int}.00",
            "price": f"{book_price:.4f}",
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": False,
            "cancel_order_on_pause": True,
            "reduce_only": False,
        }
        if "exchange_index" in verified_market and verified_market["exchange_index"] is not None:
            v2_payload["exchange_index"] = verified_market["exchange_index"]

        path = "/trade-api/v2/portfolio/events/orders"
        try:
            headers = self._sign_headers("POST", path)
            # H6: Use order_session (max_retries=0) for mutating orders
            resp = self.order_session.post(f"{BASE_URL}{path}", json=v2_payload, headers=headers, timeout=5.0)

            if resp.status_code in [200, 201]:
                self._cached_balance_time = 0.0
                self._cached_market_time = 0.0
                res_data = resp.json()
                fill_count = float(res_data.get("fill_count", "0") or "0")
                if fill_count == 0:
                    return {
                        "success": False,
                        "error": "Kalshi Order Unfilled: IOC limit order did not cross the book due to price movement or low liquidity.",
                        "raw_response": res_data
                    }

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
                    "count": fill_count,
                    "requested_price": raw_price,
                    "filled_price": avg_outcome_fill,
                    "total_cost": round(avg_outcome_fill * fill_count, 4),
                    "slippage_buffer": buf,
                    "status": "FILLED",
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

kalshi_trader = KalshiTrader()


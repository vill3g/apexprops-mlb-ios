"""
Unit & Integration Test Suite for the INVESTMENTS Universe (Robinhood Stocks, ETFs & Options)
Tests:
1. RobinhoodMarketSession detection (RTH, Pre, After, Flatten window, Weekend)
2. Black-Scholes theoretical pricing & delta calculation
3. Dual Adapter & Paper Broker functionality (buying power, stock order, option order, buying power deduction)
4. Intraday Multi-factor scanner (ORB, VWAP, Squeeze, RVOL)
5. Options contract selection (Delta targeting, DTE window, spread filter)
6. Agentic Desk reasoning & Gemini synthesis fallback
7. InvestmentsExecutor cycle execution & position settlement
8. REST API endpoints (/session, /scanner, /portfolio, /trade/stock, /trade/option, /close, /config)
"""

import datetime
import pytest
from zoneinfo import ZoneInfo

from backend.investments.robinhood_client import (
    RobinhoodMarketSession,
    black_scholes_price,
    InvestmentsPaperBroker,
    RobinhoodClientFactory
)
from backend.investments.intraday_scanner import IntradayStockScanner
from backend.investments.options_selector import OptionsContractSelector
from backend.investments.agentic_desk import AgenticInvestmentsDesk
from backend.investments.executor import InvestmentsExecutor
from backend.database.models import (
    get_user_by_id,
    credit_user_investments_paper_balance,
    deduct_user_investments_paper_balance,
    update_user_investments_config
)


def test_robinhood_market_session():
    sess = RobinhoodMarketSession.get_current_session()
    assert "state" in sess
    assert "description" in sess
    assert "can_daytrade" in sess
    assert "ny_time" in sess


def test_black_scholes_pricing():
    # Call option with spot=100, strike=100, DTE=2 days
    price, delta, theta = black_scholes_price(spot=100.0, strike=100.0, dte_days=2.0, option_type="CALL")
    assert price > 0.0
    assert 0.40 <= delta <= 0.60
    assert theta <= 0.0

    # Put option with spot=100, strike=100, DTE=2 days
    put_price, put_delta, put_theta = black_scholes_price(spot=100.0, strike=100.0, dte_days=2.0, option_type="PUT")
    assert put_price > 0.0
    assert -0.60 <= put_delta <= -0.40


def test_investments_paper_broker():
    # Create or ensure test user exists in current DB (handles pytest temporary DB)
    from backend.database.models import create_user, get_user_by_id, credit_user_investments_paper_balance
    user_id = 7
    if not get_user_by_id(user_id):
        created_id = create_user("investments_tester", "hashed_pw")
        user_id = created_id if created_id else 7
    credit_user_investments_paper_balance(user_id, 10000.0)

    broker = InvestmentsPaperBroker(user_id)
    bp_data = broker.get_buying_power()
    assert bp_data["success"] is True
    assert bp_data["buying_power"] >= 0.0
    assert "UNRESTRICTED" in bp_data["pdt_status"]

    # Place paper stock order
    res_stock = broker.place_stock_order(symbol="SPY", action="BUY", shares=1.0)
    assert res_stock["success"] is True
    assert res_stock["symbol"] == "SPY"
    assert res_stock["action"] == "BUY"
    assert res_stock["filled_price"] > 0

    # Place paper option order with strike near current spot price
    exp = (datetime.datetime.now(ZoneInfo("America/New_York")).date() + datetime.timedelta(days=2)).isoformat()
    spot_px = res_stock["filled_price"]
    res_opt = broker.place_option_order(
        symbol="SPY",
        strike=round(spot_px),
        expiration=exp,
        option_type="CALL",
        action="BUY",
        contracts=1
    )
    assert res_opt["success"] is True
    assert res_opt["contracts"] == 1
    assert res_opt["filled_price"] > 0


def test_intraday_scanner():
    scanner = IntradayStockScanner()
    breadth = scanner.get_market_breadth()
    assert "macro_bias" in breadth

    spy_analysis = scanner.analyze_symbol("SPY")
    assert spy_analysis["symbol"] == "SPY"
    assert spy_analysis["price"] > 0
    assert spy_analysis["rvol"] >= 0
    assert "vwap" in spy_analysis


def test_options_contract_selector():
    selector = OptionsContractSelector()
    best_call = selector.select_best_contract(
        symbol="SPY",
        bias="BULLISH",
        target_delta=0.45,
        dte_window="0DTE_WEEKLY"
    )
    assert best_call is not None
    assert best_call["option_type"] == "CALL"
    assert best_call["strike"] > 0
    assert best_call["theo_price"] > 0


def test_agentic_desk_evaluation():
    desk = AgenticInvestmentsDesk()
    user_cfg = {
        "investments_min_confidence": 60.0,
        "investments_asset_classes": "STOCKS,ETFS,OPTIONS",
        "investments_trade_size_dollars": 250.0,
        "investments_max_daily_risk": 500.0,
        "investments_allow_fractional": 1
    }
    opp = desk.evaluate_opportunity("SPY", user_cfg, buying_power=10000.0)
    assert "decision" in opp
    assert opp["symbol"] == "SPY"


def test_investments_executor_cycle():
    executor = InvestmentsExecutor()
    res = executor.run_cycle()
    assert res["success"] is True
    assert "session" in res


def test_investments_api_routes_and_classifier():
    import json
    from backend.routes.engine_investments import (
        _is_investment_trade_dict,
        get_options_chain,
        get_investments_portfolio,
        manual_stock_trade,
        manual_option_trade,
        close_investment_trade,
        ManualStockOrderRequest,
        ManualOptionOrderRequest,
    )
    from backend.database.models import create_user

    # Verify classifier strictly distinguishes INVESTMENTS from CRYPTO/FOREX and SPORTS
    assert _is_investment_trade_dict({"ticker": "NVDA", "metadata": {"universe": "INVESTMENTS"}}) is True
    assert _is_investment_trade_dict({"ticker": "SPY $580 CALL (2026-10-22)", "metadata": {"vehicle": "OPTION"}}) is True
    assert _is_investment_trade_dict({"ticker": "KXBTCD-26OCT20", "metadata": {"universe": "CRYPTO"}}) is False
    assert _is_investment_trade_dict({"ticker": "SPORT-NBA-LAL-BOS", "metadata": {"universe": "SPORTS"}}) is False

    uid = create_user("inv_api_route_tester", "hashed_pw") or 7
    credit_user_investments_paper_balance(uid, 10000.0)
    mock_user = {"id": uid, "username": "inv_api_route_tester", "trading_mode": "PAPER"}

    # Test options-chain endpoint
    chain = get_options_chain(symbol="NVDA", option_type="CALL", dte_window="0DTE_WEEKLY", current_user=mock_user)
    assert chain["symbol"] == "NVDA"
    assert chain["spot_price"] > 0
    assert "optimal_call" in chain
    assert "optimal_put" in chain

    # Test notional stock order execution
    stock_req = ManualStockOrderRequest(
        symbol="NVDA",
        action="BUY",
        shares=0.0,
        notional_dollars=250.0,
        tp_pct=2.5,
        sl_pct=1.2,
    )
    stock_res = manual_stock_trade(req=stock_req, current_user=mock_user)
    assert stock_res["success"] is True
    assert stock_res["trade"]["count"] > 0
    meta_stock = json.loads(stock_res["trade"]["metadata"]) if isinstance(stock_res["trade"]["metadata"], str) else stock_res["trade"]["metadata"]
    assert meta_stock["universe"] == "INVESTMENTS"

    # Test option order execution with TP/SL
    exp_str = chain["optimal_call"]["expiration"]
    strike_val = chain["optimal_call"]["strike"]
    opt_req = ManualOptionOrderRequest(
        symbol="NVDA",
        strike=strike_val,
        expiration=exp_str,
        option_type="CALL",
        action="BUY",
        contracts=1,
        tp_pct=35.0,
        sl_pct=20.0,
    )
    opt_res = manual_option_trade(req=opt_req, current_user=mock_user)
    assert opt_res["success"] is True
    meta_opt = json.loads(opt_res["trade"]["metadata"]) if isinstance(opt_res["trade"]["metadata"], str) else opt_res["trade"]["metadata"]
    assert meta_opt["vehicle"] == "OPTION"

    # Test enriched portfolio endpoint
    port = get_investments_portfolio(current_user=mock_user)
    assert port["open_count"] >= 2
    assert "portfolio_value" in port
    assert "open_market_value" in port
    assert "day_pnl_dollars" in port
    assert "win_rate" in port
    assert "recent_orders" in port
    assert all(_is_investment_trade_dict(o) for o in port["recent_orders"])

    # Close the stock trade and verify settlement
    close_res = close_investment_trade(trade_id=stock_res["trade"]["id"], current_user=mock_user)
    assert close_res["success"] is True
    assert "pnl" in close_res

    # Test LIMIT stock order execution with explicit limit_price
    limit_req = ManualStockOrderRequest(
        symbol="SPY",
        action="BUY",
        shares=1.0,
        order_type="LIMIT",
        limit_price=500.25,
        tp_pct=3.0,
        sl_pct=1.5,
    )
    limit_res = manual_stock_trade(req=limit_req, current_user=mock_user)
    assert limit_res["success"] is True
    assert limit_res["trade"]["entry_price"] == 500.25

    # Verify portfolio mode isolation: switching user to LIVE mode should not return PAPER positions/orders
    live_mock_user = {"id": uid, "username": "inv_api_route_tester", "trading_mode": "LIVE"}
    port_live = get_investments_portfolio(current_user=live_mock_user)
    assert port_live["mode"] == "LIVE"
    assert port_live["open_count"] == 0
    assert len(port_live["recent_orders"]) == 0

    # Verify PAPER mode portfolio still returns the PAPER positions & recent_orders with tp_price/sl_price
    port_paper = get_investments_portfolio(current_user=mock_user)
    assert port_paper["mode"] == "PAPER"
    assert port_paper["open_count"] >= 2
    assert all("tp_price" in o and "sl_price" in o for o in port_paper["recent_orders"])


def test_robinhood_mcp_adapter_and_routes():
    from backend.investments.robinhood_client import (
        RobinhoodMCPAdapter,
        RobinhoodClientFactory,
        DEFAULT_ROBINHOOD_MCP_URL,
        ROBINHOOD_MCP_STANDARD_TOOLS,
    )
    from backend.routes.engine_investments import (
        get_robinhood_mcp_status,
        test_robinhood_mcp_connection,
        MCPTestRequest,
    )
    from backend.database.models import create_user, save_user_robinhood_credentials, get_user_by_id
    from backend.auth.security import encrypt_kalshi_key

    uid = create_user("mcp_tester", "hashed_pw") or 7
    save_user_robinhood_credentials(
        user_id=uid,
        mcp_url=DEFAULT_ROBINHOOD_MCP_URL,
        mcp_token_enc=encrypt_kalshi_key("test-mcp-token-xyz"),
        auth_mode="ROBINHOOD_MCP",
        account_type="CASH"
    )
    u = get_user_by_id(uid)
    assert u["rh_auth_mode"] == "ROBINHOOD_MCP"
    assert u["rh_mcp_url"] == DEFAULT_ROBINHOOD_MCP_URL
    assert bool(u["rh_mcp_token_enc"]) is True

    # Factory in LIVE mode with ROBINHOOD_MCP should return RobinhoodMCPAdapter
    client = RobinhoodClientFactory.get_client(uid, mode_override="LIVE")
    assert isinstance(client, RobinhoodMCPAdapter)
    assert client.mcp_url == DEFAULT_ROBINHOOD_MCP_URL
    assert client.mcp_token == "test-mcp-token-xyz"

    # Status route
    status = get_robinhood_mcp_status(current_user=u)
    assert status["success"] is True
    assert status["mcp_url"] == DEFAULT_ROBINHOOD_MCP_URL
    assert status["has_mcp_token"] is True
    assert "place_equity_order" in status["standard_tools"]
    assert "review_equity_order" in status["standard_tools"]

    # Unauthenticated probe test (empty token override)
    adapter_no_tok = RobinhoodMCPAdapter(uid, token_override="")
    # Fallback buying power when no token
    bp = adapter_no_tok.get_buying_power()
    assert bp["success"] is True
    assert "ROBINHOOD_MCP" in bp["account_type"]

    # Test OAuth 2.0 PKCE start & callback state management
    from backend.routes.engine_investments import (
        start_robinhood_mcp_oauth,
        robinhood_mcp_oauth_callback,
        MCPOAuthStartRequest,
        _mcp_oauth_states,
    )
    from starlette.requests import Request as StarletteRequest

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/engine/investments/mcp/oauth/start",
        "headers": [(b"host", b"localhost:8058")],
        "scheme": "http",
        "server": ("localhost", 8058),
    }
    dummy_req = StarletteRequest(scope)
    oauth_res = start_robinhood_mcp_oauth(
        request=dummy_req,
        req=MCPOAuthStartRequest(origin="http://localhost:8058"),
        current_user=u
    )
    assert oauth_res["success"] is True
    assert "https://robinhood.com/oauth?" in oauth_res["auth_url"]
    assert "code_challenge_method=S256" in oauth_res["auth_url"]
    assert oauth_res["client_id"]
    assert oauth_res["state"] in _mcp_oauth_states

    # Test error callback HTML rendering
    err_html = robinhood_mcp_oauth_callback(error="access_denied", error_description="User cancelled")
    assert err_html.status_code == 200
    assert "Robinhood OAuth Authorization Declined" in err_html.body.decode("utf-8")







# ---------------------------------------------------------------------------
# LIVE safety tests (mocked Robinhood MCP adapter - no network, no real orders)
# ---------------------------------------------------------------------------
import json as _json
import uuid as _uuid


def _make_fake_mcp(uid, place_state="queued", avg_price=None, review_checks=None,
                   place_success=True, instruments=None):
    from backend.investments.robinhood_client import RobinhoodMCPAdapter

    class FakeMCP(RobinhoodMCPAdapter):
        def __init__(self):
            super().__init__(uid, token_override="fake-token")
            self._agentic_acct = "ACCT-TEST"
            self.calls = []
            self.orders = {}

        def call_tool(self, name, arguments=None):
            args = dict(arguments or {})
            self.calls.append((name, args))
            if name == "get_equity_quotes":
                sym = args["symbols"][0]
                return {"success": True, "data": {"data": {"results": [{"quote": {
                    "symbol": sym, "last_trade_price": "100.00", "bid_price": "99.90",
                    "ask_price": "100.10", "previous_close": "99.00",
                    "venue_last_trade_time": "2026-10-20T19:59:59Z"}}]}}}
            if name in ("review_equity_order", "review_option_order"):
                return {"success": True, "data": {"data": {"order_checks": review_checks or []}}}
            if name in ("place_equity_order", "place_option_order"):
                if not place_success:
                    return {"success": False, "error": "Rejected by broker (test)"}
                oid = str(_uuid.uuid4())
                order = {"id": oid, "state": place_state, "average_price": avg_price,
                         "quantity": args.get("quantity") or "0", "cumulative_quantity":
                         (args.get("quantity") or "0") if place_state == "filled" else "0"}
                self.orders[oid] = order
                return {"success": True, "data": {"data": order}}
            if name in ("get_equity_orders", "get_option_orders"):
                o = self.orders.get(args.get("order_id"))
                return {"success": True, "data": {"data": {"orders": [o] if o else []}}}
            if name == "get_option_instruments":
                return {"success": True, "data": {"data": {"results": instruments or []}}}
            return {"success": False, "error": f"unexpected tool {name}"}

        def placed(self):
            return [c for c in self.calls if c[0] in ("place_equity_order", "place_option_order")]

    return FakeMCP()


def _live_user(name):
    from backend.database.models import create_user
    uid = create_user(name + "_" + _uuid.uuid4().hex[:6], "pw")
    return uid, {"id": uid, "username": name, "trading_mode": "LIVE"}


def _insert_live_trade(uid, side="BUY", vehicle="STOCK", entry=100.0, count=2.0, extra_meta=None):
    from backend.database.trade_store import TradeStore
    tid = "LIVE-" + _uuid.uuid4().hex[:10]
    meta = {"universe": "INVESTMENTS", "vehicle": vehicle, "symbol": "SPY", "tp_pct": 2.5, "sl_pct": 1.0}
    if vehicle == "OPTION":
        meta.update({"strike": 500.0, "expiration": "2026-10-23", "option_type": "CALL"})
    meta.update(extra_meta or {})
    trade = {"id": tid, "user_id": uid, "ticker": "SPY", "side": side, "entry_price": entry, "count": count,
             "status": "OPEN", "pnl": 0.0, "mode": "LIVE", "asset": "INVESTMENTS",
             "timestamp": "2026-10-20T10:00:00-04:00", "metadata": _json.dumps(meta)}
    TradeStore.insert_trade(uid, trade)
    return tid


def _patch_factory(monkeypatch, client):
    from backend.investments.robinhood_client import RobinhoodClientFactory
    monkeypatch.setattr(RobinhoodClientFactory, "get_client", staticmethod(lambda uid, mode_override=None: client))


def test_fallback_quote_is_never_usable(monkeypatch):
    import backend.investments.robinhood_client as rc

    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(rc.requests, "get", boom)
    rc._quote_cache.pop("ZZZQ", None)
    q = rc.get_live_stock_quote("ZZZQ")
    assert q.get("fallback") is True
    assert rc.quote_is_usable(q) is False
    assert rc.get_decision_quote("ZZZQ") is None
    res = InvestmentsPaperBroker(1).place_stock_order(symbol="ZZZQ", action="BUY", shares=1)
    assert res["success"] is False


def test_live_close_queued_keeps_open_then_reconciles(monkeypatch):
    from backend.routes.engine_investments import close_investment_trade
    from backend.database.trade_store import TradeStore
    from backend.investments.live_ops import reconcile_live_trades, parse_meta
    uid, user = _live_user("live_close")
    fake = _make_fake_mcp(uid, place_state="queued")
    _patch_factory(monkeypatch, fake)
    tid = _insert_live_trade(uid, side="BUY", entry=100.0, count=2.0)

    res = close_investment_trade(tid, user, allow_queue=True)
    assert res["status"] == "PENDING_CLOSE"
    placed = fake.placed()
    assert len(placed) == 1 and placed[0][1]["side"] == "sell" and placed[0][1]["quantity"] == "2"
    t = TradeStore.get_trade_by_id(tid)
    assert str(t["status"]).upper() == "OPEN"
    assert parse_meta(t)["pending_close"]["order_id"] == res["order_id"]

    # second close must not send another order
    res2 = close_investment_trade(tid, user, allow_queue=True)
    assert res2["status"] == "PENDING_CLOSE" and len(fake.placed()) == 1

    # broker fills -> reconcile closes at the broker average price
    fake.orders[res["order_id"]].update({"state": "filled", "average_price": "103.00", "cumulative_quantity": "2"})
    stats = reconcile_live_trades(uid, fake)
    assert stats["closed"] == 1
    t = TradeStore.get_trade_by_id(tid)
    assert str(t["status"]).upper() == "CLOSED"
    assert float(t["exit_price"]) == 103.0 and float(t["pnl"]) == 6.0


def test_live_close_short_buys_to_cover_and_filled_closes(monkeypatch):
    from backend.routes.engine_investments import close_investment_trade
    from backend.database.trade_store import TradeStore
    uid, user = _live_user("live_short")
    fake = _make_fake_mcp(uid, place_state="filled", avg_price="95.00")
    _patch_factory(monkeypatch, fake)
    tid = _insert_live_trade(uid, side="SELL", entry=100.0, count=1.0)
    res = close_investment_trade(tid, user, allow_queue=True)
    assert fake.placed()[0][1]["side"] == "buy"
    assert res["status"] == "CLOSED" and res["pnl"] == 5.0
    assert str(TradeStore.get_trade_by_id(tid)["status"]).upper() == "CLOSED"


def test_live_close_rejected_surfaces_and_close_all_reports(monkeypatch):
    from fastapi import HTTPException
    from backend.routes.engine_investments import close_investment_trade, close_all_investment_trades
    from backend.database.trade_store import TradeStore
    uid, user = _live_user("live_reject")
    fake = _make_fake_mcp(uid, place_success=False)
    _patch_factory(monkeypatch, fake)
    tid = _insert_live_trade(uid)
    with pytest.raises(HTTPException) as ei:
        close_investment_trade(tid, user, allow_queue=True)
    assert ei.value.status_code == 400
    assert str(TradeStore.get_trade_by_id(tid)["status"]).upper() == "OPEN"
    out = close_all_investment_trades(user)
    assert out["success"] is False and out["error_count"] == 1 and out["closed_count"] == 0


def test_live_entry_pending_then_reconciled_fill(monkeypatch):
    from backend.routes.engine_investments import manual_stock_trade, ManualStockOrderRequest
    from backend.database.trade_store import TradeStore
    from backend.investments.live_ops import reconcile_live_trades, parse_meta
    uid, user = _live_user("live_entry")
    fake = _make_fake_mcp(uid, place_state="queued")
    _patch_factory(monkeypatch, fake)
    res = manual_stock_trade(ManualStockOrderRequest(symbol="SPY", action="BUY", shares=0.0, notional_dollars=5.0), user)
    assert res["pending_fill"] is True
    tid = res["trade"]["id"]
    assert "dollar_amount" in fake.placed()[0][1]
    fake.orders[tid].update({"state": "filled", "average_price": "101.50", "cumulative_quantity": "0.049"})
    reconcile_live_trades(uid, fake)
    t = TradeStore.get_trade_by_id(tid)
    assert float(t["entry_price"]) == 101.5 and float(t["count"]) == 0.049
    assert parse_meta(t)["pending_fill"] is False

    # a pending entry that gets cancelled at the broker is marked CANCELLED
    res2 = manual_stock_trade(ManualStockOrderRequest(symbol="SPY", action="BUY", shares=0.0, notional_dollars=5.0), user)
    fake.orders[res2["trade"]["id"]].update({"state": "cancelled"})
    reconcile_live_trades(uid, fake)
    assert str(TradeStore.get_trade_by_id(res2["trade"]["id"])["status"]).upper() == "CANCELLED"


def test_executor_live_exit_gated_on_fill_and_hours(monkeypatch):
    from backend.database.trade_store import TradeStore
    from backend.investments.live_ops import parse_meta
    uid, user = _live_user("live_exec")
    fake = _make_fake_mcp(uid, place_state="queued")
    _patch_factory(monkeypatch, fake)
    tid = _insert_live_trade(uid, entry=90.0, count=1.0)  # quote 99.9 bid -> TP hit
    ex = InvestmentsExecutor()
    cfg = {"trading_mode": "LIVE", "investments_eod_auto_flatten": 1}

    # After-hours: no orders at all (no EOD flatten, no TP market orders)
    after = {"state": "AFTER_HOURS", "is_open": False, "can_daytrade": False, "is_flatten_window": False}
    assert ex._monitor_and_manage_positions(uid, cfg, after) == 0
    assert fake.placed() == []

    # RTH: TP triggers a real SELL, but queued -> trade stays OPEN with pending_close
    rth = {"state": "REGULAR_OPEN", "is_open": True, "can_daytrade": True, "is_flatten_window": False}
    assert ex._monitor_and_manage_positions(uid, cfg, rth) == 0
    assert len(fake.placed()) == 1 and fake.placed()[0][1]["side"] == "sell"
    t = TradeStore.get_trade_by_id(tid)
    assert str(t["status"]).upper() == "OPEN" and parse_meta(t)["pending_close"]

    # next cycle: no duplicate exit order
    ex._monitor_and_manage_positions(uid, cfg, rth)
    assert len(fake.placed()) == 1


def test_mcp_option_order_schema_and_no_silent_fallback():
    from backend.database.models import create_user
    uid = create_user("opt_schema_" + _uuid.uuid4().hex[:6], "pw")
    inst = [{"id": "OPT-UUID-1", "strike_price": "500.0000", "expiration_date": "2026-10-23", "type": "call"}]
    fake = _make_fake_mcp(uid, place_state="queued", instruments=inst)
    res = fake.place_option_order(symbol="SPY", strike=500.0, expiration="2026-10-23", option_type="CALL",
                                  action="SELL", contracts=2, position_effect="close")
    assert res["success"] is True and res["filled_price"] is None and res["state"] == "queued"
    name, args = fake.placed()[0]
    assert name == "place_option_order"
    assert args["account_number"] == "ACCT-TEST" and args["quantity"] == "2"
    assert args["legs"] == [{"option_id": "OPT-UUID-1", "side": "sell", "position_effect": "close", "ratio_quantity": 1}]
    assert "price" not in args and "ref_id" in args
    assert any(c[0] == "review_option_order" for c in fake.calls)

    # unresolvable instrument -> clear error, nothing placed, no fallback tools
    fake2 = _make_fake_mcp(uid, instruments=[])
    res2 = fake2.place_option_order(symbol="SPY", strike=501.0, expiration="2026-10-23", option_type="CALL",
                                    action="BUY", contracts=1)
    assert res2["success"] is False and "NOT sent" in res2["error"]
    assert fake2.placed() == [] and not any(c[0] == "place_order" for c in fake2.calls)


def test_subsecond_tape_engine_and_websocket():
    from backend.investments.subsecond_tape_engine import SubSecondTapeEngine

    # 1. Ingest prints
    p1 = SubSecondTapeEngine.ingest_print("SPY", price=580.50, size=100, bid=580.45, ask=580.50)
    assert p1["side"] == "BUY"
    assert p1["is_block"] is False

    # Block print
    p2 = SubSecondTapeEngine.ingest_print("SPY", price=580.40, size=6000, bid=580.40, ask=580.45)
    assert p2["side"] == "SELL"
    assert p2["is_block"] is True

    # Order flow analytics
    flow = SubSecondTapeEngine.get_order_flow_analytics("SPY")
    assert flow["symbol"] == "SPY"
    assert flow["block_sweeps_count"] >= 1
    assert "cvd" in flow
    assert "delta_ratio" in flow
    assert "flow_bias" in flow

    # WebSocket subscriber registration
    class FakeWS:
        def __init__(self):
            self.sent = []
        async def send_json(self, data):
            self.sent.append(data)

    fws = FakeWS()
    SubSecondTapeEngine.register_subscriber(fws)
    assert fws in SubSecondTapeEngine._active_subscribers
    SubSecondTapeEngine.unregister_subscriber(fws)
    assert fws not in SubSecondTapeEngine._active_subscribers


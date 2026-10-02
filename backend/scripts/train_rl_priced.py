"""
Train the priced RL DQN (backend/btc/rl_priced.py) on real Kalshi history.

Steps
  1. Download every settled KXBTC15M market (result + 1-minute YES bid/ask for the
     first minutes of each market) from Kalshi's public API. Cached and resumable in
     backend/data/kalshi_btc15m_history.jsonl, so later runs only fetch new markets.
  2. Download Coinbase BTC-USD 15m candles covering the same period.
  3. Build one sample per market per entry time (60s, 120s, 180s after the open):
     features from candles before the interval + the real quote at that moment, and
     the exact net profit after fees of PASS / BUY YES / BUY NO.
  4. Train an ensemble of dueling Q-networks on the oldest ~70% of markets, pick the
     trading threshold on the next ~15% (validation), then measure once on the newest
     ~15% (test) that played no part in training or threshold choice.
  5. Save the model. It is ENABLED for live trading only if the test period was
     profitable after fees with enough trades; otherwise it is saved disabled and
     the live RL keeps passing.

Usage (project root, app venv):   python backend/scripts/train_rl_priced.py
Options: --no-download (reuse cached data), --seeds 5, --min-test-trades 100
"""
import argparse
import datetime
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_DIR)

from backend.btc import rl_priced as rp  # noqa: E402
from backend.btc.indicators import add_all_indicators  # noqa: E402

DATA_DIR = os.path.join(REPO_DIR, "backend", "data")
KALSHI_CACHE = os.path.join(DATA_DIR, "kalshi_btc15m_history.jsonl")
CANDLE_CACHE = os.path.join(DATA_DIR, "coinbase_btc15m_history.csv")
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = "KXBTC15M"
OFFSETS = (60, 120, 180)


def _get(url, tries=8):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "kalshi-ai-trader"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 or e.code >= 500:
                time.sleep(min(30, 1.5 * (i + 1)))
                continue
            raise
        except Exception:
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET failed: {url}")


def _iso(s):
    return int(datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def _list_markets(path, extra):
    out, cursor = [], None
    while True:
        params = dict(series_ticker=SERIES, limit=1000, **extra)
        if cursor:
            params["cursor"] = cursor
        d = _get(f"{KALSHI}{path}?{urllib.parse.urlencode(params)}") or {}
        ms = d.get("markets", [])
        out += ms
        cursor = d.get("cursor")
        if not cursor or not ms:
            return out


def download_kalshi(workers=8):
    done = set()
    if os.path.exists(KALSHI_CACHE):
        with open(KALSHI_CACHE, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["ticker"])
                except (ValueError, KeyError):
                    pass
    jobs = [(m, "/historical/markets/{t}/candlesticks") for m in _list_markets("/historical/markets", {})]
    jobs += [(m, f"/series/{SERIES}/markets/{{t}}/candlesticks") for m in _list_markets("/markets", {"status": "settled"})]
    jobs = [j for j in jobs if j[0]["ticker"] not in done and j[0].get("result") in ("yes", "no")]
    print(f"[kalshi] {len(done)} cached, {len(jobs)} to download")
    if not jobs:
        return

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    def pick(d, k):
        return None if d is None else num(d.get(k, d.get(k + "_dollars")))

    lock = threading.Lock()
    with open(KALSHI_CACHE, "a", encoding="utf-8") as out:
        def work(job):
            m, path = job
            o = _iso(m["open_time"])
            q = urllib.parse.urlencode({"start_ts": o, "end_ts": o + 240, "period_interval": 1})
            d = _get(f"{KALSHI}{path.format(t=m['ticker'])}?{q}") or {}
            cs = [{"off": c["end_period_ts"] - o, "ask": pick(c.get("yes_ask"), "close"),
                   "bid": pick(c.get("yes_bid"), "close")} for c in d.get("candlesticks", [])]
            rec = {"ticker": m["ticker"], "open_ts": o, "strike": m.get("floor_strike"),
                   "result": m.get("result"), "c": cs}
            with lock:
                out.write(json.dumps(rec) + "\n")
                out.flush()

        t0 = time.time()
        with ThreadPoolExecutor(workers) as ex:
            for n, fu in enumerate(as_completed([ex.submit(work, j) for j in jobs]), 1):
                if fu.exception():
                    print("[kalshi] error:", fu.exception())
                if n % 2000 == 0:
                    print(f"[kalshi] {n}/{len(jobs)} ({time.time() - t0:.0f}s)")


def download_candles(start_ts):
    rows = {}
    if os.path.exists(CANDLE_CACHE):
        for r in pd.read_csv(CANDLE_CACHE).itertuples(index=False):
            rows[int(r.time)] = [int(r.time), r.open, r.high, r.low, r.close, r.volume]
        start_ts = max(start_ts, max(rows) - 900 * 10) if rows else start_ts
    t, end = start_ts, int(time.time())
    while t < end:
        e = min(end, t + 300 * 900)
        fmt = lambda x: datetime.datetime.fromtimestamp(x, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=900&start={fmt(t)}&end={fmt(e)}"
        for r in _get(url) or []:  # [time, low, high, open, close, volume]
            rows[int(r[0])] = [int(r[0]), r[3], r[2], r[1], r[4], r[5]]
        t = e
        time.sleep(0.15)
    df = pd.DataFrame(sorted(rows.values()), columns=["time", "open", "high", "low", "close", "volume"])
    df.to_csv(CANDLE_CACHE, index=False)
    return df


def build_dataset(candles: pd.DataFrame):
    df_ind = add_all_indicators(candles.copy()).reset_index(drop=True)
    pos = {int(t): i for i, t in enumerate(df_ind["time"].astype("int64"))}
    X, R, T, feat_names = [], [], [], None
    feat_cache = {}
    with open(KALSHI_CACHE, encoding="utf-8") as f:
        by_ticker = {}
        for l in f:
            if l.strip():
                m = json.loads(l)
                by_ticker[m["ticker"]] = m  # de-duplicate (a market can appear in both listings)
        markets = list(by_ticker.values())
    for m in markets:
        i = pos.get(int(m["open_ts"]))
        if i is None or i < 300 or m.get("result") not in ("yes", "no"):
            continue
        if i not in feat_cache:
            feat_cache[i] = rp.market_features(df_ind, i)
        by_off = {c["off"]: c for c in m["c"]}
        for off in OFFSETS:
            c = by_off.get(off)
            if not c or not rp.valid_quote(c.get("ask"), c.get("bid")):
                continue
            feats = dict(feat_cache[i])
            feats.update(rp.price_features(c["ask"], c["bid"]))
            feats["elapsed_min"] = off / 60.0
            if feat_names is None:
                feat_names = list(feats.keys())
            X.append([feats[k] for k in feat_names])
            R.append(rp.action_rewards(c["ask"], c["bid"], m["result"] == "yes"))
            T.append(int(m["open_ts"]))
    order = np.argsort(T, kind="stable")
    return (np.array(X, dtype=np.float64)[order], np.array(R)[order],
            np.array(T)[order], feat_names)


def evaluate(model, Xs, R, threshold):
    q = model.q_values(Xs)
    side = np.where(q[:, 1] >= q[:, 2], 1, 2)
    best = q[np.arange(len(q)), side]
    trade = best > threshold
    pnl = R[np.arange(len(R)), side][trade]
    return {"trades": int(trade.sum()), "net_per_contract": float(pnl.mean()) if len(pnl) else 0.0,
            "total_net": float(pnl.sum()), "win_rate": float((pnl > 0).mean()) if len(pnl) else 0.0,
            "yes_share": float((side[trade] == 1).mean()) if len(pnl) else 0.0,
            "pnl": pnl}


def one_trade_per_market(T, mask):
    """Keep only the first qualifying entry per market (the bot trades once per interval)."""
    keep = np.zeros(len(T), dtype=bool)
    seen = set()
    for k in np.where(mask)[0]:
        if T[k] not in seen:
            seen.add(T[k])
            keep[k] = True
    return keep


def realistic(model, Xs, R, T, threshold):
    q = model.q_values(Xs)
    side = np.where(q[:, 1] >= q[:, 2], 1, 2)
    best = q[np.arange(len(q)), side]
    keep = one_trade_per_market(T, best > threshold)
    pnl = R[np.arange(len(R)), side][keep]
    res = {"trades": int(keep.sum()), "net_per_contract": float(pnl.mean()) if len(pnl) else 0.0,
           "total_net_per_1_contract_bets": float(pnl.sum()), "win_rate": float((pnl > 0).mean()) if len(pnl) else 0.0}
    if len(pnl) >= 10:
        rng = np.random.default_rng(0)
        boots = [rng.choice(pnl, len(pnl)).mean() for _ in range(2000)]
        res["ci95_net_per_contract"] = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--min-val-trades", type=int, default=100)
    ap.add_argument("--min-test-trades", type=int, default=100)
    args = ap.parse_args()

    if not args.no_download:
        download_kalshi()
    with open(KALSHI_CACHE, encoding="utf-8") as f:
        first = min(json.loads(l)["open_ts"] for l in f if l.strip())
    candles = download_candles(first - 400 * 900) if not args.no_download else pd.read_csv(CANDLE_CACHE)

    X, R, T, names = build_dataset(candles)
    markets = np.unique(T)
    t_val, t_test = markets[int(len(markets) * 0.70)], markets[int(len(markets) * 0.85)]
    tr, va, te = T < t_val, (T >= t_val) & (T < t_test), T >= t_test
    fmt = lambda x: datetime.datetime.fromtimestamp(int(x), datetime.timezone.utc).strftime("%Y-%m-%d")
    print(f"[data] {len(X)} samples from {len(markets)} markets | train {fmt(T[tr].min())}..{fmt(T[tr].max())} "
          f"({tr.sum()}) | val ..{fmt(T[va].max())} ({va.sum()}) | test ..{fmt(T[te].max())} ({te.sum()})")

    # Market-only baselines on the test period (what you get with no model at all)
    first_off = one_trade_per_market(T, te)
    for name, col in (("always BUY YES", 1), ("always BUY NO", 2)):
        print(f"[baseline] {name}: net/contract {R[first_off, col].mean():+.4f} over {first_off.sum()} markets")

    mean, std = X[tr].mean(0), X[tr].std(0) + 1e-9
    Z = np.clip((X - mean) / std, -6, 6)
    nets = []
    for sd in range(args.seeds):
        net, hist = rp.train_qnet(Z[tr], R[tr], Z[va], R[va], seed=sd)
        nets.append(net)
        print(f"[train] seed {sd}: {len(hist)} epochs, best val MSE {min(hist):.5f}")
    model = rp.PricedDQN(names, mean, std, nets, {})

    # Threshold chosen on validation only
    best_thr, best_val = None, None
    for thr in np.round(np.arange(0.0, 0.151, 0.005), 3):
        r = realistic(model, Z[va], R[va], T[va], thr)
        if r["trades"] >= args.min_val_trades and (best_val is None or r["total_net_per_1_contract_bets"] > best_val["total_net_per_1_contract_bets"]):
            best_thr, best_val = float(thr), r
    if best_thr is None:
        best_thr, best_val = float("inf"), {"trades": 0, "total_net_per_1_contract_bets": 0.0}
    print(f"[val] chosen threshold {best_thr} -> {best_val}")

    test = realistic(model, Z[te], R[te], T[te], best_thr) if np.isfinite(best_thr) else {"trades": 0}
    print(f"[test] (untouched) -> {test}")
    # Enable only with statistical evidence: the untouched test period must be profitable
    # after fees with the LOWER end of its 95% confidence interval above zero. A positive
    # average whose interval straddles zero is indistinguishable from luck.
    ci_low = test.get("ci95_net_per_contract", [-1.0, 0.0])[0]
    enabled = bool(np.isfinite(best_thr) and best_val["total_net_per_1_contract_bets"] > 0
                   and test.get("trades", 0) >= args.min_test_trades and ci_low > 0)

    model.meta = {
        "enabled": enabled,
        "threshold": best_thr if np.isfinite(best_thr) else 1e9,
        "max_entry_seconds": max(OFFSETS),
        "entry_offsets": list(OFFSETS),
        "trained_at": time.time(),
        "periods": {"train_end": fmt(t_val), "val_end": fmt(t_test), "test_end": fmt(T.max())},
        "validation": {k: v for k, v in best_val.items() if k != "pnl"},
        "test": {k: v for k, v in test.items() if k != "pnl"},
        "n_samples": int(len(X)),
    }
    model.save()
    print(f"[save] {rp.MODEL_PATH} (enabled={enabled})")
    if not enabled:
        print("The model did NOT show a statistically reliable profit on the untouched test period "
              f"(95% interval lower bound {ci_low:+.4f}/contract), so it was saved DISABLED. "
              "The live RL will keep passing.")


if __name__ == "__main__":
    main()

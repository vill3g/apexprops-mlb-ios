"""
Priced RL DQN for Kalshi KXBTC15M ("RL v2").

Why this exists
---------------
The original DQN (rl_agent.py) never saw the contract price and was trained on
made-up rewards, so it could not know whether a bet was worth its price. This
model is trained on real Kalshi history: for every settled 15-minute market we
know the YES/NO prices shortly after the open and the official result, so the
true net profit of each action (BUY YES, BUY NO, PASS), after Kalshi fees, is
known exactly. The network learns Q(state, action) = expected net profit per
$1 contract and only trades when the best expected profit clears a threshold
that was chosen on a validation period and checked on an untouched test period.

Everything (features, network, training, inference) is pure numpy, and the same
feature function is used for training and live decisions, so there is no
train/serve skew and no PyTorch dependency.
"""
import json
import logging
import math
import os
import threading
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "model_cache")
MODEL_PATH = os.path.join(MODEL_DIR, "rl_priced_dqn.npz")
META_PATH = os.path.join(MODEL_DIR, "rl_priced_dqn.json")

# Seconds after the interval opens at which training prices were sampled. The Kalshi
# book is empty for the first seconds of each market, so prices from the first
# minute are not usable; the live gate refuses to trade earlier than this.
ENTRY_OFFSET_SECONDS = 60

ACTIONS = ("PASS", "YES", "NO")

LAG_FEATS = ["bb_percent_b", "rsi", "volume_15m_ratio", "roc_15m", "cvd_divergence"]


def kalshi_fee(price: float) -> float:
    """Kalshi taker fee per contract (approx.): 0.07 * P * (1 - P)."""
    price = min(max(float(price), 0.0), 1.0)
    return 0.07 * price * (1.0 - price)


# ---------------------------------------------------------------------
# Features (single implementation for training and live)
# ---------------------------------------------------------------------
def _f(x, default=0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def market_features(df_ind: pd.DataFrame, i: int) -> Dict[str, float]:
    """Features for the interval that starts at candle i, using ONLY candles < i
    (plus candle i's open, which is known at the start). df_ind must come from
    indicators.add_all_indicators()."""
    p = df_ind.iloc[i - 1]
    c = df_ind.iloc[i]
    target = _f(c.get("open"), _f(p["close"]))
    base = _f(p.get("ema_50"), target) or target
    p_open, p_close = _f(p.get("open"), target), _f(p["close"], target)
    p_high = _f(p.get("high"), max(p_open, p_close))
    p_low = _f(p.get("low"), min(p_open, p_close))
    rng = max(1e-5, p_high - p_low)
    atr = _f(p.get("atr"), 100.0) or 100.0

    lo = max(0, i - 96)
    high_24h = float(df_ind["high"].iloc[lo:i].max())
    low_24h = float(df_ind["low"].iloc[lo:i].min())
    vol3d = float(df_ind["volume"].iloc[max(0, i - 288):i].mean() or 1.0)
    atr_slice = df_ind["atr"].iloc[lo:i]
    bb_u, bb_l = _f(p.get("bb_upper"), target), _f(p.get("bb_lower"), target)

    ts = int(_f(p.get("time"), 0))
    lt = time.gmtime(ts - 4 * 3600)  # approx. US Eastern; only used as a coarse seasonality signal
    hour = lt.tm_hour + lt.tm_min / 60.0

    feats = {
        "rsi": (_f(p.get("rsi"), 50.0) - 50.0) / 50.0,
        "bb_pos": ((p_close - bb_l) / (bb_u - bb_l) - 0.5) if bb_u > bb_l else 0.0,
        "bb_width": (bb_u - bb_l) / base * 100.0,
        "ema9_rel": (_f(p.get("ema_9"), base) / base - 1.0) * 100.0,
        "ema21_rel": (_f(p.get("ema_21"), base) / base - 1.0) * 100.0,
        "close_vs_ema50": (p_close / base - 1.0) * 100.0,
        "atr_pct": atr / base * 100.0,
        "vwap_rel": (target - _f(p.get("vwap"), target)) / base * 100.0,
        "delta_to_target": (p_close - target) / max(target, 1e-9) * 100.0,
        "upper_wick": (p_high - max(p_open, p_close)) / rng,
        "lower_wick": (min(p_open, p_close) - p_low) / rng,
        "body": (p_close - p_open) / rng,
        "range_24h_pos": min(1.0, max(0.0, (p_close - low_24h) / max(1.0, high_24h - low_24h))),
        "range_24h_pct": (high_24h - low_24h) / base * 100.0,
        "vol_ratio": math.log1p(max(0.0, _f(p.get("volume")) / max(vol3d, 1e-9))),
        "vol_regime": float((atr_slice <= atr).mean()) if len(atr_slice) else 0.5,
        "roc_15m": _f(p.get("roc_15m")),
        "roc_1h": _f(p.get("roc_1h")),
        "roc_4h": _f(p.get("roc_4h")),
        "hour_sin": math.sin(2 * math.pi * hour / 24.0),
        "hour_cos": math.cos(2 * math.pi * hour / 24.0),
        "weekend": 1.0 if lt.tm_wday >= 5 else 0.0,
    }
    for step in range(1, 5):  # candles i-2 .. i-5 (i-1 is covered above)
        j = i - 1 - step
        r = df_ind.iloc[j] if j >= 0 else p
        r_close = _f(r.get("close"), p_close)
        r_open = _f(r.get("open"), r_close)
        feats[f"ret_lag{step}"] = (r_close / max(r_open, 1e-9) - 1.0) * 100.0
        feats[f"rsi_lag{step}"] = (_f(r.get("rsi"), 50.0) - 50.0) / 50.0
    return feats


def price_features(yes_ask: float, yes_bid: float) -> Dict[str, float]:
    mid = (yes_ask + yes_bid) / 2.0
    m = min(max(mid, 0.01), 0.99)
    return {
        "yes_ask": yes_ask,
        "yes_bid": yes_bid,
        "mid": mid,
        "spread": yes_ask - yes_bid,
        "mid_logit": math.log(m / (1.0 - m)),
        "mid_dist": abs(mid - 0.5),
    }


def valid_quote(yes_ask, yes_bid) -> bool:
    return (yes_ask is not None and yes_bid is not None and 0.01 <= yes_bid < yes_ask <= 0.99
            and (yes_ask - yes_bid) <= 0.10)


def action_rewards(yes_ask: float, yes_bid: float, result_yes: bool) -> np.ndarray:
    """Exact net profit per contract of [PASS, BUY YES, BUY NO] at these prices, after fees."""
    no_ask = 1.0 - yes_bid
    r_yes = (1.0 if result_yes else 0.0) - yes_ask - kalshi_fee(yes_ask)
    r_no = (0.0 if result_yes else 1.0) - no_ask - kalshi_fee(no_ask)
    return np.array([0.0, r_yes, r_no])


# ---------------------------------------------------------------------
# Network: dueling Q-network, numpy, trained on full-information rewards
# ---------------------------------------------------------------------
def _silu(x):
    return x / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _silu_grad(x):
    s = 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))
    return s * (1.0 + x * (1.0 - s))


class DuelingQNet:
    def __init__(self, n_in: int, h1: int = 64, h2: int = 32, seed: int = 0):
        rng = np.random.default_rng(seed)
        he = lambda a, b: rng.normal(0, math.sqrt(2.0 / a), (a, b))
        self.p = {
            "W1": he(n_in, h1), "b1": np.zeros(h1),
            "W2": he(h1, h2), "b2": np.zeros(h2),
            "Wv": he(h2, 1) * 0.1, "bv": np.zeros(1),
            "Wa": he(h2, 3) * 0.1, "ba": np.zeros(3),
        }

    def forward(self, X, cache=False):
        p = self.p
        z1 = X @ p["W1"] + p["b1"]; h1 = _silu(z1)
        z2 = h1 @ p["W2"] + p["b2"]; h2 = _silu(z2)
        v = h2 @ p["Wv"] + p["bv"]
        a = h2 @ p["Wa"] + p["ba"]
        q = v + a - a.mean(axis=1, keepdims=True)
        if cache:
            return q, (X, z1, h1, z2, h2)
        return q

    def grads(self, X, R, huber_delta=1.0, l2=1e-4):
        q, (X, z1, h1, z2, h2) = self.forward(X, cache=True)
        err = q - R
        dq = np.where(np.abs(err) <= huber_delta, err, huber_delta * np.sign(err)) / (len(X) * 3)
        p = self.p
        dv = dq.sum(axis=1, keepdims=True)
        da = dq - dq.mean(axis=1, keepdims=True)
        g = {
            "Wv": h2.T @ dv, "bv": dv.sum(0),
            "Wa": h2.T @ da, "ba": da.sum(0),
        }
        dh2 = dv @ p["Wv"].T + da @ p["Wa"].T
        dz2 = dh2 * _silu_grad(z2)
        g["W2"] = h1.T @ dz2; g["b2"] = dz2.sum(0)
        dh1 = dz2 @ p["W2"].T
        dz1 = dh1 * _silu_grad(z1)
        g["W1"] = X.T @ dz1; g["b1"] = dz1.sum(0)
        for k in ("W1", "W2", "Wv", "Wa"):
            g[k] = g[k] + l2 * p[k]
        loss = float(np.mean(np.where(np.abs(err) <= huber_delta, 0.5 * err ** 2,
                                      huber_delta * (np.abs(err) - 0.5 * huber_delta))))
        return loss, g


def train_qnet(X, R, Xv, Rv, seed=0, h1=64, h2=32, lr=1e-3, l2=1e-4, epochs=80, batch=512, patience=8):
    """Adam + early stopping on validation loss. Returns (net, history)."""
    net = DuelingQNet(X.shape[1], h1, h2, seed)
    m = {k: np.zeros_like(v) for k, v in net.p.items()}
    s = {k: np.zeros_like(v) for k, v in net.p.items()}
    rng = np.random.default_rng(seed + 1000)
    best, best_p, bad, step, hist = float("inf"), None, 0, 0, []
    for ep in range(epochs):
        idx = rng.permutation(len(X))
        for b in range(0, len(X), batch):
            j = idx[b:b + batch]
            _, g = net.grads(X[j], R[j], l2=l2)
            step += 1
            for k in net.p:
                m[k] = 0.9 * m[k] + 0.1 * g[k]
                s[k] = 0.999 * s[k] + 0.001 * g[k] ** 2
                net.p[k] -= lr * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(s[k] / (1 - 0.999 ** step)) + 1e-8)
        err = net.forward(Xv) - Rv
        vl = float(np.mean(err ** 2))
        hist.append(vl)
        if vl < best - 1e-6:
            best, best_p, bad = vl, {k: v.copy() for k, v in net.p.items()}, 0
        else:
            bad += 1
            if bad >= patience:
                break
    net.p = best_p
    return net, hist


# ---------------------------------------------------------------------
# Model bundle: feature order + scaler + ensemble + decision threshold
# ---------------------------------------------------------------------
class PricedDQN:
    def __init__(self, feature_names: List[str], mean, std, nets: List[DuelingQNet], meta: dict):
        self.feature_names = list(feature_names)
        self.mean = np.asarray(mean, dtype=np.float64)
        self.std = np.asarray(std, dtype=np.float64)
        self.nets = nets
        self.meta = meta

    @property
    def threshold(self) -> float:
        return float(self.meta.get("threshold", float("inf")))

    def vectorize(self, feats: Dict[str, float]) -> np.ndarray:
        x = np.array([_f(feats.get(k), 0.0) for k in self.feature_names], dtype=np.float64)
        return np.clip((x - self.mean) / self.std, -6, 6)

    def q_values(self, Xs: np.ndarray) -> np.ndarray:
        Xs = np.atleast_2d(Xs)
        return np.mean([n.forward(Xs) for n in self.nets], axis=0)

    def decide_q(self, q: np.ndarray, threshold: float = None) -> Tuple[int, float]:
        """0 PASS / 1 YES / 2 NO, and the expected net profit of the chosen side."""
        thr = self.threshold if threshold is None else threshold
        side = 1 if q[1] >= q[2] else 2
        best = float(q[side])
        return (side if best > thr else 0), best

    def save(self, model_path=None, meta_path=None):
        model_path = model_path or MODEL_PATH
        meta_path = meta_path or META_PATH
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        arrays = {"mean": self.mean, "std": self.std}
        for n_i, n in enumerate(self.nets):
            for k, v in n.p.items():
                arrays[f"net{n_i}_{k}"] = v
        tmp = model_path + ".tmp.npz"
        np.savez(tmp, **arrays)
        os.replace(tmp, model_path)
        meta = dict(self.meta, feature_names=self.feature_names, n_nets=len(self.nets))
        with open(meta_path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        os.replace(meta_path + ".tmp", meta_path)

    @classmethod
    def load(cls, model_path=None, meta_path=None) -> "PricedDQN":
        model_path = model_path or MODEL_PATH
        meta_path = meta_path or META_PATH
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        z = np.load(model_path)
        nets = []
        for n_i in range(int(meta["n_nets"])):
            net = DuelingQNet(len(meta["feature_names"]))
            net.p = {k: z[f"net{n_i}_{k}"] for k in ("W1", "b1", "W2", "b2", "Wv", "bv", "Wa", "ba")}
            nets.append(net)
        return cls(meta["feature_names"], z["mean"], z["std"], nets, meta)


_model_cache = {"mtime": None, "model": None}
_model_lock = threading.Lock()


def get_priced_model() -> Optional[PricedDQN]:
    """Loaded model, reloaded when the file changes; None if missing or disabled."""
    try:
        mtime = os.path.getmtime(META_PATH)
    except OSError:
        return None
    with _model_lock:
        if _model_cache["mtime"] != mtime:
            try:
                _model_cache["model"] = PricedDQN.load()
            except Exception as e:
                logger.warning(f"[PricedDQN] Could not load model: {e}")
                _model_cache["model"] = None
            _model_cache["mtime"] = mtime
        return _model_cache["model"]


def _interval_index(df_ind: pd.DataFrame, interval_start: int) -> Tuple[pd.DataFrame, Optional[int]]:
    """Index of the candle that opens at interval_start; appends a placeholder row
    when the exchange has not published the new candle yet."""
    times = df_ind["time"].astype("int64").to_numpy()
    hit = np.where(times == interval_start)[0]
    if len(hit):
        return df_ind, int(hit[0])
    if len(times) and times[-1] == interval_start - 900:
        last = df_ind.iloc[-1]
        row = {col: np.nan for col in df_ind.columns}
        row.update(time=interval_start, open=float(last["close"]), high=float(last["close"]),
                   low=float(last["close"]), close=float(last["close"]), volume=0.0)
        df2 = pd.concat([df_ind, pd.DataFrame([row])], ignore_index=True)
        return df2, len(df2) - 1
    return df_ind, None


def evaluate_live(df_ind: pd.DataFrame, kalshi_m: dict, now_ts: float = None) -> dict:
    """Live decision for the currently open 15m market. Never raises."""
    out = {"action": 0, "q": None, "expected_profit": None, "reason": ""}
    try:
        model = get_priced_model()
        if model is None:
            out["reason"] = "no trained priced model (run backend/scripts/train_rl_priced.py)"
            return out
        if not model.meta.get("enabled", False):
            out["reason"] = "priced model is disabled (it did not show a profit on the untouched test period)"
            return out
        if not kalshi_m or kalshi_m.get("is_synthetic") or str(kalshi_m.get("ticker", "")).endswith("_SYNTH"):
            out["reason"] = "no real Kalshi market"
            return out
        yes_ask, yes_bid = _f(kalshi_m.get("yes_ask"), None), _f(kalshi_m.get("yes_bid"), None)
        if not valid_quote(yes_ask, yes_bid):
            out["reason"] = f"unusable quote (bid {yes_bid}, ask {yes_ask})"
            return out
        now_ts = time.time() if now_ts is None else now_ts
        interval_start = int(now_ts // 900 * 900)
        elapsed = now_ts - interval_start
        max_elapsed = float(model.meta.get("max_entry_seconds", 180))
        if elapsed < ENTRY_OFFSET_SECONDS or elapsed > max_elapsed:
            out["reason"] = f"outside trained entry window ({elapsed:.0f}s into interval; trained {ENTRY_OFFSET_SECONDS}-{max_elapsed:.0f}s)"
            return out
        df2, i = _interval_index(df_ind, interval_start)
        if i is None or i < 300:
            out["reason"] = "candles do not line up with the current interval"
            return out
        feats = market_features(df2, i)
        feats.update(price_features(yes_ask, yes_bid))
        feats["elapsed_min"] = elapsed / 60.0
        q = model.q_values(model.vectorize(feats))[0]
        action, best = model.decide_q(q)
        out.update(action=action, q=[round(float(v), 4) for v in q], expected_profit=round(best, 4),
                   yes_ask=yes_ask, yes_bid=yes_bid, threshold=model.threshold)
        out["reason"] = (f"expected net profit {best:+.3f}/contract "
                         f"{'clears' if action else 'below'} threshold {model.threshold:.3f}")
        return out
    except Exception as e:
        out["reason"] = f"error: {e}"
        return out

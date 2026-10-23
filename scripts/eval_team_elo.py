import math, sys
from backend.engine.quant_lab.history_builder import load_history_snapshots


def score(rows, key):
    b = ll = 0.0
    for s in rows:
        y = 1.0 if s["actual_outcome"] == "YES" else 0.0
        p = min(0.99, max(0.01, key(s)))
        b += (p - y) ** 2
        ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    n = len(rows)
    return round(b / n, 4), round(ll / n, 4)


for sp in sys.argv[1:]:
    d = load_history_snapshots(sp, limit=1000)
    w = [s for s in d if "ai_win_prob" in s["raw_features"]]
    print(f"== {sp}: markets {len(d)}; with Elo prob {len(w)}")
    if len(w) < 20:
        continue
    f = lambda s: s["raw_features"]
    print("  market mid:", score(w, lambda s: f(s)["market_mid"]))
    print("  Elo       :", score(w, lambda s: f(s)["ai_win_prob"] / 100))
    print("  50/50 mix :", score(w, lambda s: 0.5 * f(s)["ai_win_prob"] / 100 + 0.5 * f(s)["market_mid"]))
    for lo, hi in ((-99, -8), (-8, -3), (-3, 3), (3, 8), (8, 99)):
        rows = [s for s in w if lo <= f(s)["ai_edge"] < hi]
        if rows:
            wr = sum(1 for s in rows if s["actual_outcome"] == "YES") / len(rows)
            mid = sum(f(s)["market_mid"] for s in rows) / len(rows)
            print(f"  edge {lo:>4}..{hi:<3}: n={len(rows):3d} YES {wr:.2f} vs market {mid:.2f}")

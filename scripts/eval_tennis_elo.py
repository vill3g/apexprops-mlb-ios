import math
from backend.engine.quant_lab.history_builder import load_history_snapshots
from backend.engine.quant_lab.strategy_coder import StrategyCoder
from backend.engine.quant_lab.validator import StrategyValidator
from backend.engine.quant_lab.alpha_ideator import AlphaIdeator

d = load_history_snapshots("TEN", limit=1000)
w = [s for s in d if "ai_win_prob" in s["raw_features"]]
print(f"TEN markets {len(d)}; with Elo prob {len(w)}")

def score(rows, key):
    b = ll = 0.0
    for s in rows:
        y = 1.0 if s["actual_outcome"] == "YES" else 0.0
        p = min(0.99, max(0.01, key(s)))
        b += (p - y) ** 2
        ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    n = len(rows)
    return round(b / n, 4), round(ll / n, 4)

if w:
    print("Brier/logloss  market mid:", score(w, lambda s: s["raw_features"]["market_mid"]))
    print("Brier/logloss  Elo       :", score(w, lambda s: s["raw_features"]["ai_win_prob"] / 100))
    print("Brier/logloss  50/50 mix :", score(w, lambda s: 0.5 * s["raw_features"]["ai_win_prob"] / 100 + 0.5 * s["raw_features"]["market_mid"]))
    # edge buckets
    for lo, hi in ((-99, -8), (-8, -3), (-3, 3), (3, 8), (8, 99)):
        rows = [s for s in w if lo <= s["raw_features"]["ai_edge"] < hi]
        if rows:
            wr = sum(1 for s in rows if s["actual_outcome"] == "YES") / len(rows)
            mid = sum(s["raw_features"]["market_mid"] for s in rows) / len(rows)
            print(f"  ai_edge {lo:>4}..{hi:<3}: n={len(rows):3d} YES win {wr:.2f} vs market {mid:.2f}")

ide = AlphaIdeator()
seen = set()
for _ in range(14):
    h = ide._generate_rule_based("TEN", "GAME", list(seen))
    if h["name"] in seen:
        continue
    seen.add(h["name"])
    if not any(c["indicator"] in ("ai_edge", "ai_win_prob") for c in h["entry_conditions"]):
        continue
    code, _h = StrategyCoder.generate_code(h)
    v = StrategyValidator.validate(StrategyCoder.compile_strategy(code), asset="TEN")
    m = v.get("metrics") or {}
    print(f"{h['name'][:42]:42s} passed={v.get('passed')} {str(v.get('failure_reason'))[:90]} oos={ {k: m.get(k) for k in ('trades','win_rate','total_pnl')} }")

from backend.engine.quant_lab.history_builder import load_history_snapshots
from backend.engine.quant_lab.strategy_coder import StrategyCoder
from backend.engine.quant_lab.validator import StrategyValidator
from backend.engine.quant_lab.alpha_ideator import AlphaIdeator

for sp in ("NFL", "TEN"):
    d = load_history_snapshots(sp)
    print(f"== {sp}: {len(d)} markets")
    buckets = [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]
    for lo, hi in buckets:
        rows = [s for s in d if lo <= s["raw_features"]["market_mid"] < hi]
        if rows:
            wr = sum(1 for s in rows if s["actual_outcome"] == "YES") / len(rows)
            print(f"  mid {lo:.1f}-{min(hi,1):.1f}: n={len(rows):3d}  YES win rate {wr:.2f}  (implied {sum(s['raw_features']['market_mid'] for s in rows)/len(rows):.2f})")
    drifts = [s["raw_features"].get("price_drift") for s in d]
    nz = sum(1 for x in drifts if x not in (None, 0.0))
    print(f"  drift present {sum(1 for x in drifts if x is not None)}, nonzero {nz}")
    # run every sports rule-based archetype through the validator
    ide = AlphaIdeator()
    seen = set()
    for _ in range(12):
        h = ide._generate_rule_based(sp, "GAME", [n for n in seen])
        if h["name"] in seen:
            continue
        seen.add(h["name"])
        code, _h = StrategyCoder.generate_code(h)
        fn = StrategyCoder.compile_strategy(code)
        v = StrategyValidator.validate(fn, asset=sp)
        m = v.get("metrics") or {}
        print(f"  {h['name'][:45]:45s} passed={v.get('passed')} {v.get('failure_reason')} oos={ {k: m.get(k) for k in ('trades','win_rate','total_pnl')} }")

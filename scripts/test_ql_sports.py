from backend.engine.quant_lab.incubator import PaperIncubator
p = PaperIncubator()
for a in ["NFL", "NHL", "TEN", "SPORTS"]:
    act = p.get_active_incubating(asset=a)
    snap = {"raw_features": {"ai_win_prob": 70, "ai_edge": 8, "confidence_score": 75}, "price": 50}
    try:
        s = p.evaluate_snapshot(a, snap)
        print(a, "active", len(act), "signals", len(s))
    except Exception as e:
        print(a, "ERR", repr(e))

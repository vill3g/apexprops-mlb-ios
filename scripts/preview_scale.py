from backend.engine.quant_lab.feedback import refresh, size_scale
refresh()
for t in ("KXBTC15M-X", "KXETH15M-X", "KXSOL15M-X", "KXDOGE15M-X", "KXGOLD-X", "KXGBPUSD-X", "KXUSDJPY-X", "KXEURUSD-X", "KXAUDUSD-X"):
    print(t.split("-")[0], size_scale(t))

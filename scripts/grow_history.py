import logging, sys
logging.basicConfig(level=logging.INFO)
from backend.engine.quant_lab.history_builder import build_history, backfill_names
for sp in sys.argv[1:]:
    for _ in range(5):
        try:
            n = build_history(sp, 120)
        except Exception as e:
            print(sp, "err", e); break
        print(sp, "added", n, flush=True)
        if n == 0: break
    try:
        print(sp, "names", backfill_names(sp), flush=True)
    except Exception as e:
        print(sp, "names err", e)

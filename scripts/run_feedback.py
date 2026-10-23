from backend.engine.quant_lab.feedback import refresh
r = refresh()
for k, v in sorted(r.items(), key=lambda kv: -kv[1]["n"])[:25]:
    print(k, v)

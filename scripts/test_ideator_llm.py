from dotenv import load_dotenv
load_dotenv()
from backend.engine.quant_lab.alpha_ideator import AlphaIdeator
a = AlphaIdeator()
for asset in ("ETH", "TEN"):
    try:
        h = a._generate_with_llm(asset, "15m", [], None)
        print(asset, "LLM OK:", (h or {}).get("name"))
    except Exception as e:
        print(asset, "LLM ERR:", repr(e))
from backend.engine.quant_lab.orchestrator import QuantLabOrchestrator
o = QuantLabOrchestrator()
for asset, iv in (("ETH", "15m"), ("TEN", "GAME")):
    r = o.run_research_cycle(asset=asset, target_interval=iv)
    print(asset, {k: r.get(k) for k in ("result", "status", "strategy_id", "name")})

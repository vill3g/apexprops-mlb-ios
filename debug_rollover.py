import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.btc.auto_executor import get_auto_executor
ex = get_auto_executor("BTC")
print("Last action:", ex.get_status().get("last_trade", "None"))

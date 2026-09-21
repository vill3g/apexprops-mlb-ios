import sys
sys.path.append('.')
from backend.btc.paper_balance import atomic_json_write, BALANCE_PATH
import os

atomic_json_write(BALANCE_PATH, {"balance": 4000.0})
print(f"Updated {BALANCE_PATH} to $4000.0")

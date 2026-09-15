from backend.btc.auto_executor import auto_executor
import json

s = auto_executor.get_status()
recent = s.get('recent_trades', [])
open_t = s.get('open_trades', [])

print(f"=== get_status() ===")
print(f"recent_trades count: {len(recent)}")
print(f"open_trades count:   {len(open_t)}")
print(f"win_rate value:      {repr(s.get('win_rate'))}")
print(f"total_pnl value:     {repr(s.get('total_pnl'))}")
print(f"today_realized_pnl:  {repr(s.get('today_realized_pnl'))}")
print(f"open_pnl_dollars:    {repr(s.get('open_pnl_dollars'))}")
print()

print("=== recent_trades statuses ===")
for t in recent:
    print(f"  id={t.get('id')[:12]} mode={t.get('mode')} status={t.get('status')} result={t.get('result')} pnl={t.get('pnl')}")

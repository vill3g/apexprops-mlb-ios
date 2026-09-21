import json
import sys
import os

sys.path.insert(0, os.path.abspath('.'))
from backend.btc.loss_analyzer import LossAnalyzer

def main():
    analyzer = LossAnalyzer()
    
    with open('backend/data/trades_history.json') as f:
        trades = json.load(f)
        
    live_losses = [
        t for t in trades 
        if t.get('mode', '').upper() == 'LIVE' 
        and t.get('status') == 'SETTLED'
        and 'LOSS' in str(t.get('result'))
        and t.get('timestamp', '') >= '2026-09-13'
    ]
    
    if not live_losses:
        print('No live losses found since God Mode upgrade (Sept 13).')
        return
        
    print(f'Analyzing {len(live_losses)} LIVE losses since God Mode upgrade...')
    print('-' * 80)
    
    for i, t in enumerate(live_losses, 1):
        diagnosis = analyzer.diagnose_loss(t)
        print(f"Loss #{i}: {t.get('ticker')} (PnL: {t.get('pnl', 0)})")
        print(f"  Category: {diagnosis.get('category')}")
        print(f"  Summary:  {diagnosis.get('summary')}")
        print(f"  Severity: {diagnosis.get('severity')}")
        print(f"  Metrics:  RSI={diagnosis.get('rsi_at_entry')}, ATR={diagnosis.get('atr_at_entry')}, CVD={diagnosis.get('cvd_at_entry')}")
        print('-' * 80)
        
    regime = analyzer.calculate_regime_penalties(trades)
    print("\nRegime Penalties based on recent trades:")
    print(json.dumps(regime, indent=2))

if __name__ == '__main__':
    main()

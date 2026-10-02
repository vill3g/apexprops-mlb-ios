import json
from collections import defaultdict
from datetime import datetime

def main():
    with open(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\live_trades_dump.json', 'r') as f:
        trades = json.load(f)
    
    sessions = []
    current_session = [trades[0]]
    for i in range(1, len(trades)):
        prev_time = trades[i-1]['created_at']
        curr_time = trades[i]['created_at']
        gap = prev_time - curr_time
        if gap > 4 * 3600:
            sessions.append(current_session)
            current_session = [trades[i]]
        else:
            current_session.append(trades[i])
    sessions.append(current_session)
    
    target_session = None
    for sess in sessions:
        if len(sess) >= 5:
            target_session = sess
            break
            
    print(f"Target session length: {len(target_session)}")
    session_trades = target_session
    
    start_time = datetime.fromtimestamp(session_trades[-1]['created_at']).isoformat()
    end_time = datetime.fromtimestamp(session_trades[0]['created_at']).isoformat()
    print(f"Session Start: {start_time}")
    print(f"Session End:   {end_time}")
    
    total_pnl = 0.0
    wins = 0
    losses = 0
    
    exit_reasons = defaultdict(int)
    strategy_pnl = defaultdict(float)
    strategy_counts = defaultdict(int)
    strategy_wins = defaultdict(int)
    
    for t in session_trades:
        pnl = t.get('realized_pnl') or t.get('pnl') or 0.0
        total_pnl += pnl
        
        is_win = (pnl > 0)
        if is_win:
            wins += 1
        else:
            losses += 1
            
        reason = t.get('exit_reason') or 'UNKNOWN'
        if not reason:
            reason = 'UNKNOWN'
        exit_reasons[reason] += 1
        
        strat = 'UNKNOWN'
        try:
            raw = json.loads(t.get('raw_json', '{}'))
            strat = raw.get('trade_source') or raw.get('trading_style') or 'UNKNOWN'
        except:
            pass
            
        strategy_pnl[strat] += pnl
        strategy_counts[strat] += 1
        if is_win:
            strategy_wins[strat] += 1
            
    win_rate = (wins / len(session_trades)) * 100 if session_trades else 0
    
    print(f"\n--- SESSION METRICS ---")
    print(f"Total Trades: {len(session_trades)}")
    print(f"Overall PnL: ${total_pnl:.2f}")
    print(f"Win Rate:    {win_rate:.2f}% ({wins}W / {losses}L)")
    
    print("\n--- EXIT REASONS ---")
    for r, c in exit_reasons.items():
        print(f"{r}: {c}")
        
    print("\n--- STRATEGIES ---")
    for s, count in strategy_counts.items():
        swins = strategy_wins[s]
        spnl = strategy_pnl[s]
        swr = (swins / count) * 100
        print(f"Strategy: {s} | Trades: {count} | Win Rate: {swr:.2f}% | PnL: ${spnl:.2f}")

if __name__ == "__main__":
    main()

import json

try:
    with open('backend/data/trades_history.json', 'r') as f:
        trades = json.load(f)
    
    valid_trades = []
    for t in trades:
        res = t.get('result', '')
        if 'PENDING' in res or 'OPEN' in res:
            continue
        ml_prob = t.get('ml_prob')
        if ml_prob is None or ml_prob == 0.5:
            continue
        valid_trades.append(t)
    
    total = len(valid_trades)
    correct = 0
    for t in valid_trades:
        ml_dir = "ABOVE" if t['ml_prob'] > 0.5 else "BELOW"
        actual_dir = t.get('direction')
        if 'LOSS' in t.get('result', ''):
            actual_dir = "BELOW" if actual_dir == "ABOVE" else "ABOVE"
        if ml_dir == actual_dir:
            correct += 1
            
    print(f"Overall Accuracy: {correct}/{total} ({correct/total*100:.1f}%)")
    
    # Split into chunks of 20
    chunks = [valid_trades[i:i+20] for i in range(0, len(valid_trades), 20)]
    for i, chunk in enumerate(chunks):
        c_correct = 0
        for t in chunk:
            ml_dir = "ABOVE" if t['ml_prob'] > 0.5 else "BELOW"
            actual_dir = t.get('direction')
            if 'LOSS' in t.get('result', ''):
                actual_dir = "BELOW" if actual_dir == "ABOVE" else "ABOVE"
            if ml_dir == actual_dir:
                c_correct += 1
        acc = c_correct / len(chunk) * 100
        print(f"Window {i+1} (Trades {i*20 + 1}-{i*20 + len(chunk)}): {c_correct}/{len(chunk)} ({acc:.1f}%)")
        
except Exception as e:
    print(e)

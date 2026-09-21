import json

try:
    with open('backend/data/trades_history.json', 'r') as f:
        trades = json.load(f)
    
    total = 0
    correct = 0
    
    for t in trades:
        res = t.get('result', '')
        if 'PENDING' in res or 'OPEN' in res:
            continue
        
        ml_prob = t.get('ml_prob')
        if ml_prob is None:
            continue
        
        # ML Prediction direction
        ml_dir = "ABOVE" if ml_prob > 0.5 else "BELOW"
        if ml_prob == 0.5:
            continue # Pass
        
        # What actually happened?
        # If the trade was a WIN, then t['direction'] was correct.
        # So actual market direction = t['direction'] if WIN else opposite
        actual_dir = t.get('direction')
        if 'LOSS' in res:
            actual_dir = "BELOW" if actual_dir == "ABOVE" else "ABOVE"
            
        if ml_dir == actual_dir:
            correct += 1
            
        total += 1
        
    print(f"ML Prediction Accuracy: {correct} / {total} ({(correct/total*100) if total > 0 else 0:.2f}%)")
except Exception as e:
    print(e)

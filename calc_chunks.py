import json

try:
    with open('backend/data/trades_history.json', 'r') as f:
        trades = json.load(f)
    
    chunks = [trades[i:i+30] for i in range(0, len(trades), 30)]
    for i, chunk in enumerate(chunks):
        total = 0
        correct = 0
        for t in chunk:
            res = t.get('result', '')
            if 'PENDING' in res or 'OPEN' in res:
                continue
            
            ml_prob = t.get('ml_prob')
            if ml_prob is None:
                continue
                
            ml_dir = "ABOVE" if ml_prob > 0.5 else "BELOW"
            if ml_prob == 0.5:
                continue
                
            actual_dir = t.get('direction')
            if 'LOSS' in res:
                actual_dir = "BELOW" if actual_dir == "ABOVE" else "ABOVE"
                
            if ml_dir == actual_dir:
                correct += 1
            total += 1
        
        acc = (correct/total*100) if total > 0 else 0
        print(f"Chunk {i+1} (Trades {i*30}-{(i+1)*30}): {correct}/{total} = {acc:.2f}%")
        
except Exception as e:
    print(e)

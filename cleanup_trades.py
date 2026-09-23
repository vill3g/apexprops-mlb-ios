import os, json

data_dir = os.path.join('backend', 'data', 'users')
if os.path.exists(data_dir):
    for uid in os.listdir(data_dir):
        hist_path = os.path.join(data_dir, uid, 'trades_history.json')
        if os.path.exists(hist_path):
            with open(hist_path, 'r') as f:
                trades = json.load(f)
            
            cleaned = []
            for t in trades:
                # remove bad synthetic
                if "SYNTH" in t.get("ticker", "").upper():
                    continue
                if "TEST" in t.get("ticker", "").upper():
                    continue
                if "ETH" in t.get("ticker", "").upper() or "GOLD" in t.get("ticker", "").upper():
                    continue
                
                # fix pnl None
                if t.get("pnl") is None:
                    t["pnl"] = 0.0
                    
                cleaned.append(t)
                
            with open(hist_path, 'w') as f:
                json.dump(cleaned, f, indent=4)
print("Cleaned up trades.")

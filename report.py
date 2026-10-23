import requests, time, sys

for i in range(15):
    try:
        d = requests.get("http://127.0.0.1:8058/api/engine/sports/events?public=1", timeout=30).json()
        events = d.get("events", [])
        
        yes_ask_gt_0 = sum(1 for e in events if e.get("yes_ask", 0) > 0)
        print(f"Number of events with yes_ask > 0: {yes_ask_gt_0} / {len(events)}")
        
        picks = {}
        for e in events:
            if e.get("predicted_team"):
                sp = e.get("sport", "Unknown")
                picks[sp] = picks.get(sp, 0) + 1
                
        print("Picks per sport:")
        for sp, count in picks.items():
            print(f"- {sp}: {count}")
            
        sys.exit(0)
    except Exception as e:
        print(f"Waiting for backend: {e}")
        time.sleep(5)
        
print("Failed to get events")

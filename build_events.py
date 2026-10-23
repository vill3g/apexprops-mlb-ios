import requests, re
from datetime import datetime

def build_dynamic_ufc_events():
    r = requests.get("https://external-api.kalshi.com/trade-api/v2/events?series_ticker=KXUFCFIGHT")
    events = r.json().get("events", [])
    
    date_codes = set()
    for e in events:
        ticker = e.get("event_ticker", "")
        # KXUFCFIGHT-26OCT10KARGAT
        m = re.search(r'KXUFCFIGHT-(\d{2})([A-Z]{3})(\d{2})', ticker)
        if m:
            yy = "20" + m.group(1)
            mo_str = m.group(2)
            dd = m.group(3)
            mo = str(datetime.strptime(mo_str, "%b").month).zfill(2)
            date_codes.add(f"{yy}{mo}{dd}")
            
    official = []
    for dc in sorted(date_codes):
        # Fetch from ESPN
        er = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates={dc}")
        evts = er.json().get("events", [])
        for evt in evts:
            dt = datetime.fromisoformat(evt["date"].replace("Z", "+00:00"))
            
            # format as ufc-fn-allen or ufc-332
            name = evt.get("name", "")
            if "UFC " in name and ":" in name:
                num = name.split("UFC ")[1].split(":")[0]
                if num.isdigit():
                    eid = f"ufc-{num}"
                    ctype = "Championship PPV"
                else:
                    # Fight Night: Allen vs. Duncan
                    p1 = name.split(" vs. ")[0].split()[-1].lower()
                    eid = f"ufc-fn-{p1}"
                    ctype = "Fight Night"
            else:
                eid = f"ufc-{dc}"
                ctype = "Fight Night"
                
            venue = "UFC Apex, Las Vegas"
            try:
                venue = evt["competitions"][0]["venue"]["fullName"]
                if evt["competitions"][0]["venue"]["address"].get("city"):
                    venue += ", " + evt["competitions"][0]["venue"]["address"]["city"]
            except:
                pass
                
            official.append({
                "id": eid,
                "name": name,
                "date_code": dc,
                "date_label": dt.strftime("%A, %b %-d, %Y"),
                "venue": venue,
                "card_type": ctype,
                "is_default": False
            })
            
    if official:
        official[0]["is_default"] = True
        
    return official

print(build_dynamic_ufc_events())

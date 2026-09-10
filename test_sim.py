from backend.engine.top5_selector import Top5Selector
import time

s = Top5Selector()
t0 = time.time()
print("Starting simulation and ESPN ingestion...")
res = s.generate_daily_picks()
t1 = time.time()

print(f"Elapsed: {t1 - t0:.2f}s")
print(f"Slate games analyzed: {res['slate_count']}")
print(f"Total props generated: {res['total_props']}")
print("\n--- TOP 5 DAILY HIGHEST PROBABILITY PICKS ---")
for p in res["top_5"]:
    print(f"#{p['rank']}: {p['name']} ({p['team']} vs {p['opponent']})")
    print(f"   Line: {p['type']} {p['line']} H+R+RBI | Win Prob: {p['win_prob']}% | Edge: +{p['edge']}% | Proj: {p['proj_total']}")
    print(f"   Expected: {p['exp_hits']} Hits, {p['exp_runs']} Runs, {p['exp_rbis']} RBIs")
    print(f"   Key Catalyst: {p['catalysts'][0]}")

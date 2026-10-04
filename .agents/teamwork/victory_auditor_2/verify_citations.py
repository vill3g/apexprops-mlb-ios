import os

repo = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

citations = [
    ("backend/btc/auto_executor/executor.py", 1042, 1052, "use_kelly"),
    ("backend/btc/auto_executor/executor.py", 1346, 1356, "kelly"),
    ("backend/btc/auto_executor/saas_broadcaster.py", 946, 955, "kelly"),
    ("backend/btc/auto_executor/stop_manager.py", 345, 356, "take_profit"),
    ("backend/btc/auto_executor/stop_manager.py", 360, 374, "trail_threshold"),
    ("backend/btc/auto_executor/stop_manager.py", 381, 395, "stop_loss"),
    ("backend/btc/auto_executor/stop_manager.py", 764, 770, "is_side_flipped"),
    ("backend/btc/auto_executor/saas_broadcaster.py", 877, 881, "dca_target_max"),
    ("backend/saas_settler.py", 960, 965, "allow_reentry"),
    ("backend/btc/auto_executor/saas_broadcaster.py", 760, 768, "int(time.time()) % 2 == 0"),
    ("backend/btc/fees.py", 25, 31, "entry_edge_cents"),
    ("backend/btc/analyzer/contract_eval.py", 638, 650, "kalshi_override_yes"),
    ("backend/btc/analyzer/config.py", 25, 27, "kalshi_override_yes"),
    ("backend/btc/auto_executor/saas_broadcaster.py", 361, 363, "sec_left < 15"),
    ("backend/btc/auto_executor/stop_manager.py", 648, 650, "minutes_remaining < 0.25")
]

results = []
all_passed = True
for rel_path, start_line, end_line, keyword in citations:
    p = os.path.join(repo, rel_path.replace("/", os.sep))
    if not os.path.exists(p):
        print(f"FAIL: File missing {rel_path}")
        all_passed = False
        continue
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    chunk = "".join(lines[max(0, start_line-5):min(len(lines), end_line+5)])
    if keyword.lower() in chunk.lower():
        print(f"PASS: {rel_path}:{start_line}-{end_line} matched keyword '{keyword}'")
    else:
        print(f"WARNING: {rel_path}:{start_line}-{end_line} keyword '{keyword}' not found in window")
        # Let's search entire file to see where it is
        for idx, l in enumerate(lines, 1):
            if keyword.lower() in l.lower():
                print(f"       Found '{keyword}' at line {idx}")
        all_passed = False

if all_passed:
    print("\nALL CITATIONS VERIFIED 100% AUTHENTIC!")

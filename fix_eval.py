import re

path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer\contract_eval.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

old_blend = '''    elif iso_setting == "BLEND":
        w_heur, w_ml = 0.6, 0.4
        if not pred:
            w_heur, w_ml = 0.0, 1.0  # Let ML decide entirely if no heuristic edge
            heur_dir = 1 if ml_prob >= 0.50 else -1
            prob_heur = 50.0
        else:'''

new_blend = '''    elif iso_setting == "BLEND":
        w_heur, w_ml = 0.6, 0.4
        if not pred:
            # TEAMWORK AUDIT FIX 3: Fake Edge Suppression
            # Prevent squashed ML probabilities (~51%) from blindly buying deep OTM options
            # by forcing PASS if the ML conviction is weak when there's no chart setup.
            if 0.45 <= ml_prob <= 0.55:
                w_heur, w_ml = 1.0, 0.0
                heur_dir = 1
                prob_heur = 50.0
                pred = "PASS"
                grade = "PASS / LOW ML CONVICTION"
            else:
                w_heur, w_ml = 0.0, 1.0  # Let ML decide entirely if no heuristic edge
                heur_dir = 1 if ml_prob >= 0.50 else -1
                prob_heur = 50.0
        else:'''

text = text.replace(old_blend, new_blend)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

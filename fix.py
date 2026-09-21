import sys

try:
    with open('backend/btc/analyzer.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    start_idx = -1
    end_idx = -1

    for i, line in enumerate(lines):
        if 'if ml_prob_for_pred_dir < 50.0 and disagreement >=' in line:
            start_idx = i
            break

    if start_idx != -1:
        for i in range(start_idx + 1, len(lines)):
            if '        else:' in lines[i] and 'ML Confirmation:' in lines[i+2]:
                end_idx = i
                break

    if end_idx == -1 and start_idx != -1:
        for i in range(start_idx + 1, len(lines)):
            if '        else:' in lines[i] and 'ML Confirmation' in lines[i+2]:
                end_idx = i
                break

    if start_idx != -1 and end_idx != -1:
        new_block = [
            '        if ml_prob_for_pred_dir < 50.0 and disagreement >= THRESHOLDS["model_conflict_threshold"]:\n',
            '            catalysts.append(f"⚠️ Model Conflict: Chart setup favors {pred} ({prob}%) but ML model disagrees ({ml_prob_for_pred_dir:.1f}% for this side) - confidence capped")\n',
            '            blended_prob = min(blended_prob, THRESHOLDS["model_conflict_cap"])\n',
            '            if "GRADE A+" in grade:\n',
            '                grade = "GRADE A SETUP"\n'
        ]
        new_lines = lines[:start_idx] + new_block + lines[end_idx:]
        with open('backend/btc/analyzer.py', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print("Fixed!")
    else:
        print(f"Failed to find indices: {start_idx}, {end_idx}")

except Exception as e:
    print(f"Error: {e}")

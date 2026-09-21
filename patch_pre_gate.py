import re

with open('backend/btc/analyzer.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_block2 = """    # Capture candidate direction and probability prior to any safety filter overrides
    pre_gate_direction = "ABOVE" if ("YES" in str(pred) or "ABOVE" in str(direction)) else "BELOW"
    pre_gate_prob = float(prob)
    pre_gate_grade = grade"""

new_block2 = """    # Capture candidate direction and probability prior to any safety filter overrides
    if "PASS" in str(pred) or "PASS" in str(direction):
        pre_gate_direction = "PASS"
    else:
        pre_gate_direction = "ABOVE" if ("YES" in str(pred) or "ABOVE" in str(direction)) else "BELOW"
    pre_gate_prob = float(prob)
    pre_gate_grade = grade"""

code = code.replace(old_block2, new_block2)

with open('backend/btc/analyzer.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched pre_gate_direction!")

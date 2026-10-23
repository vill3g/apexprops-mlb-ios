with open('backend/sports_bridge/executor.py', 'r') as f:
    code = f.read()

code = code.replace("or 'GAME,SPREAD,TOTAL,PROP,INNING'", "or 'GAME,SPREAD,TOTAL,PROP'")
code = code.replace("# Market type check (GAME, SPREAD, TOTAL, PROP, INNING)", "# Market type check (GAME, SPREAD, TOTAL, PROP)")
inning_block = '''            elif any(w in upper_tk or w in upper_mt for w in ("INNING", "PERIOD", "HALF", "QUARTER", "Q1", "Q2", "Q3", "Q4", "1ST", "2ND", "3RD", "4TH", "5TH", "6TH", "7TH", "8TH", "9TH")):
                m_type = "INNING"
'''
code = code.replace(inning_block, "")

with open('backend/sports_bridge/executor.py', 'w') as f:
    f.write(code)


with open("backend/btc/auto_executor/executor.py", "r", encoding="utf-8") as f:
    content = f.read()

target_reversal = """if "positionReversal" not in self.ai_settings:
                                self.ai_settings["positionReversal"] = False"""
new_reversal = """if "positionReversal" not in self.ai_settings:
                                self.ai_settings["positionReversal"] = True"""

content = content.replace(target_reversal, new_reversal)

with open("backend/btc/auto_executor/executor.py", "w", encoding="utf-8") as f:
    f.write(content)


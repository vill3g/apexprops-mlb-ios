filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer\contract_eval.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

bad_block = '''            iso_setting = "BLEND"

    else:
        try:
            iso_setting = get_auto_executor(asset).ai_settings.get("signalIsolation", "BLEND")
        except (ValueError, TypeError) as e:
            logger.warning(f"Auto executor get error: {e}")
            iso_setting = "BLEND"'''

content = content.replace(bad_block, '            iso_setting = "BLEND"')

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed syntax error")

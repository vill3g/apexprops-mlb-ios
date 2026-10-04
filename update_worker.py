import re

with open('backend/worker.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add import
if 'SportsBridgeExecutor' not in code:
    code = code.replace('from backend.forex.auto_executor import start_forex_executor', 'from backend.forex.auto_executor import start_forex_executor\nfrom backend.sports_bridge.executor import SportsBridgeExecutor')

# Instantiate before loop
if 'sports_bridge = SportsBridgeExecutor()' not in code:
    code = code.replace('settle_tick = 0\n    while True:', 'sports_bridge = SportsBridgeExecutor()\n    settle_tick = 0\n    while True:')

# Call in loop
if 'sports_bridge.run_cycle()' not in code:
    call_code = '''        except Exception as e:
            logger.error(f"[Worker] Global loop error: {e}")
            
        try:
            sports_bridge.run_cycle()
        except Exception as e:
            logger.error(f"[Worker] Sports Bridge error: {e}")

        time.sleep(2.0)'''
    code = re.sub(r'        except Exception as e:\s*logger\.error\(f"\[Worker\] Global loop error: \{e\}"\)\s*time\.sleep\(2\.0\)', call_code, code)

with open('backend/worker.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Updated worker.py')

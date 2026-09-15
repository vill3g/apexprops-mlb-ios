from backend.btc.auto_executor import auto_executor
print(auto_executor.ai_settings.get('minConf'))
print(auto_executor.ai_settings.get('trainWindow'))
print(auto_executor.ai_settings.get('edgeWeightFactor'))

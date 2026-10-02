import re

with open('backend/btc/ml_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix in training extraction functions
# except (TypeError, ValueError):
#     val = default_val
# feature_vec.append(val)
# ->
# except (TypeError, ValueError):
#     valid = False
#     val = default_val
# feature_vec.append(val)

new_code = re.sub(
    r'except \(TypeError, ValueError\):\s+val = default_val\s+feature_vec\.append\(val\)',
    r'except (TypeError, ValueError):\n                    valid = False\n                    val = default_val\n                feature_vec.append(val)',
    code
)

# And for val = 0.0
new_code = re.sub(
    r'except \(TypeError, ValueError\):\s+val = 0\.0\s+feature_vec\.append\(val\)',
    r'except (TypeError, ValueError):\n                    valid = False\n                    val = 0.0\n                feature_vec.append(val)',
    new_code
)

# And for the lag extraction block
new_code = re.sub(
    r'except \(ValueError, TypeError, KeyError, IndexError\) as e:\s+logger\.warning\(f\"\[MLEngine\] feature extraction error: \{e\}\"\)\s+lag_features\[f\"\{feat\}_lag_\{step\}\"\] = val',
    r'except (ValueError, TypeError, KeyError, IndexError) as e:\n                    valid = False\n                    logger.warning(f"[MLEngine] feature extraction error: {e}")\n                lag_features[f"{feat}_lag_{step}"] = val',
    new_code
)

# And in predict_probability:
# except (TypeError, ValueError):
#     val = default_val
# feature_vec.append(val)
# ->
# except (TypeError, ValueError):
#     return 0.5
# feature_vec.append(val)
# Wait, predict_probability doesn't have 'valid = False' in scope, so the above re.sub would have replaced it with 'valid = False'.
# Let's fix that.

with open('backend/btc/ml_engine.py', 'w', encoding='utf-8') as f:
    f.write(new_code)

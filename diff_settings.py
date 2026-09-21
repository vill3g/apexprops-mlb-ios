with open('main_index.html', 'r', encoding='utf-8') as f:
    main_text = f.read()

with open('temp_index.html', 'r', encoding='utf-8') as f:
    temp_text = f.read()

import re
def get_settings(text):
    return set(re.findall(r'id="(setting.*?)"', text))

main_settings = get_settings(main_text)
temp_settings = get_settings(temp_text)

missing_in_temp = main_settings - temp_settings
print("Settings in main but missing in temp (kalshi-ai-trader branch):", missing_in_temp)

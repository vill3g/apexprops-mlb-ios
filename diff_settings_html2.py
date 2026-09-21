with open('main_index.html', 'r', encoding='utf-8') as f:
    main_text = f.read()

with open('temp_index.html', 'r', encoding='utf-8') as f:
    temp_text = f.read()

start_main = main_text.find('id="kalshiSettingsModal"')
end_main = main_text.find('id="kalshiTradeLogModal"')

start_temp = temp_text.find('id="kalshiSettingsModal"')
end_temp = temp_text.find('id="kalshiTradeLogModal"')

print("Main settings length:", end_main - start_main)
print("Temp settings length:", end_temp - start_temp)

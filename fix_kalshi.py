with open('backend/btc/kalshi_client.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('\"ticker\": \"KXBTC15M_SYNTH\",', '\"ticker\": f\"{series_ticker}_SYNTH\",')
with open('backend/btc/kalshi_client.py', 'w', encoding='utf-8') as f:
    f.write(c)

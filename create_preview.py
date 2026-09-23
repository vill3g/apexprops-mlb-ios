import os

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Strip out the script tags at the bottom to prevent network errors in the preview
html = html.split('<!-- App JavaScript -->')[0] + '</body></html>'

# Inject dummy data for preview
html = html.replace('$--.--', '$4,520.50', 1)
html = html.replace('$--.--', '+$240.50', 1)
html = html.replace('--%', '68.5%', 1)
html = html.replace('--', '$98,500', 1) # kalshi-target
html = html.replace('--:--', '12:45')
html = html.replace('$--.--', '$98,421.50') # live-btc-price
html = html.replace('--%', '52%', 1) # yes prob
html = html.replace('--%', '48%', 1) # no prob
html = html.replace('STANDBY', 'BULLISH') # ml-status-bubble
html = html.replace('--', 'BULLISH', 1) # bias
html = html.replace('--%', '76%', 1) # conf
html = html.replace('--%', '82.1%', 1) # prob
html = html.replace('Awaiting AI signal computation...', 'Model predicts BULLISH with 82.1% probability based on strong MACD crossover and breaking 15m volume resistance.')

# Write artifact
artifact_path = r'C:\Users\Vill3\.gemini\antigravity\brain\f9732238-5384-4f24-8075-ded12557e9eb\mobile_preview.html'
with open(artifact_path, 'w', encoding='utf-8') as f:
    f.write(html)

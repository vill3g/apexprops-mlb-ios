with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('function selectDashboardAsset(asset)', 'async function selectDashboardAsset(asset)')

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)

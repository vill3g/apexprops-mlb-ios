import re
with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

payload_old = '''                    use_kelly_criterion: document.getElementById('kelly-criterion-toggle') ? document.getElementById('kelly-criterion-toggle').checked : false,
                    atr_risk_enabled: document.getElementById('atr-risk-toggle') ? document.getElementById('atr-risk-toggle').checked : false
                };'''
payload_new = '''                    use_kelly_criterion: document.getElementById('kelly-criterion-toggle') ? document.getElementById('kelly-criterion-toggle').checked : false,
                    atr_risk_enabled: document.getElementById('atr-risk-toggle') ? document.getElementById('atr-risk-toggle').checked : false,
                    trading_universe: document.getElementById('universe-select') ? document.getElementById('universe-select').value : 'FINANCIAL',
                    min_sports_confidence: document.getElementById('sports-conf-slider') ? parseFloat(document.getElementById('sports-conf-slider').value) : 70.0
                };'''
html = html.replace(payload_old, payload_new)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed Config Payload')

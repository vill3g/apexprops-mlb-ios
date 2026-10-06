import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update saveUserConfig
old_save = '''                    min_sports_confidence: document.getElementById('sports-conf-slider') ? parseFloat(document.getElementById('sports-conf-slider').value) : 70.0'''
new_save = '''                    min_sports_confidence: document.getElementById('sports-conf-slider') ? parseFloat(document.getElementById('sports-conf-slider').value) : 70.0,
                    min_sports_edge: document.getElementById('sports-edge-slider') ? parseFloat(document.getElementById('sports-edge-slider').value) : 3.0,
                    sports_max_wager: document.getElementById('sports-wager-dollars') ? parseFloat(document.getElementById('sports-wager-dollars').value) : 10.0,
                    sports_include_live: document.getElementById('sports-include-live-toggle') ? document.getElementById('sports-include-live-toggle').checked : false'''

if old_save in content:
    content = content.replace(old_save, new_save)
    print("Updated saveUserConfig")
else:
    print("Could not find save pattern")

# 2. Update populateUserSettings
old_pop = '''            if (s.min_sports_confidence !== undefined && document.getElementById('sports-conf-slider')) {
                document.getElementById('sports-conf-slider').value = s.min_sports_confidence;
                if (document.getElementById('sports-conf-val')) {
                    document.getElementById('sports-conf-val').innerText = s.min_sports_confidence + '.0%';
                }
            }'''
new_pop = '''            if (s.min_sports_confidence !== undefined && document.getElementById('sports-conf-slider')) {
                document.getElementById('sports-conf-slider').value = s.min_sports_confidence;
                if (document.getElementById('sports-conf-val')) {
                    document.getElementById('sports-conf-val').innerText = s.min_sports_confidence + '.0%';
                }
            }
            if (s.min_sports_edge !== undefined && document.getElementById('sports-edge-slider')) {
                document.getElementById('sports-edge-slider').value = s.min_sports_edge;
                if (document.getElementById('sports-edge-val')) {
                    document.getElementById('sports-edge-val').innerText = '+' + s.min_sports_edge + '.0%';
                }
            }
            if (s.sports_max_wager !== undefined && document.getElementById('sports-wager-dollars')) {
                document.getElementById('sports-wager-dollars').value = s.sports_max_wager;
            }
            if (s.sports_include_live !== undefined && document.getElementById('sports-include-live-toggle')) {
                document.getElementById('sports-include-live-toggle').checked = !!s.sports_include_live;
            }'''

if old_pop in content:
    content = content.replace(old_pop, new_pop)
    print("Updated populateUserSettings")
else:
    print("Could not find populate pattern")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)

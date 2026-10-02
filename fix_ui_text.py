import re

def update_ui_text(fpath):
    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    # In admin_users.js
    text = text.replace('BLEND (RL + Chart Confluence)', 'BLEND (AI Model + Chart Confluence)')
    text = text.replace('Deep Q-Network (100% AI)', 'Primary AI Engine (100% AI)')
    text = text.replace('God-Tier ML Ensemble (Legacy AI)', 'Secondary ML Engine (100% AI)')
    
    # Let's also look at how index.html might phrase it.
    text = text.replace('Standard (Blend)', 'Standard (AI + Chart Blend)')
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(text)

update_ui_text('static/js/admin_users.js')
update_ui_text('static/index.html')

print("UI dropdown text updated to clarify AI + Chart blending.")

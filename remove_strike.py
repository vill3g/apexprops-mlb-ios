import sys

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

bad_logic = '''
                let isRedundantStrike = false;
                if (hasAiPick && strikeDetails && strikeDetails.toLowerCase().includes(aiPickTeam.toLowerCase()) && (propType === 'Moneyline' || propType === 'Spread')) {
                    isRedundantStrike = true;
                }
                if (strikeDetails && strikeDetails.toLowerCase() !== cleanMatchup.toLowerCase() && !isRedundantStrike) {
                    strikeDetailsRow = <div class="text-[10px] text-gray-300 font-mono flex items-center gap-1.5 mt-0.5 truncate" title=""><span class="text-cyan-400 shrink-0">??</span> <span class="truncate"></span></div>;
                }
'''

content = content.replace(bad_logic.strip(), "")
content = content.replace("", "")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)

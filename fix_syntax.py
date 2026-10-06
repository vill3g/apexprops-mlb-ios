import re
import os

html_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

# I will find the window.selectUniverse function block and completely replace it.
# It starts at: window.selectUniverse = function(universe) {
# And ends before: window.filterSportsEvents = function(sport) {
start_str = "window.selectUniverse = function(universe) {"
end_str = "window.filterSportsEvents = function(sport) {"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

correct_function = """window.selectUniverse = function(universe) {
            window.currentUniverse = universe;
            const label = document.getElementById('market-universe-label');
            if (label) label.innerText = universe === 'SPORTS' ? 'SPORTS' : 'MARKETS';
            
            const dd = document.getElementById('universe-dropdown');
            if (dd) {
                dd.classList.add('opacity-0', 'scale-95');
                setTimeout(() => {
                    dd.classList.add('hidden');
                }, 200);
            }
            
            const finAssets = document.querySelectorAll('#btn-asset-btc, #btn-asset-eth, #btn-asset-gold');
            const moreAssetsWrapper = document.getElementById('btn-asset-more') ? document.getElementById('btn-asset-more').parentElement : null;
            const sportsAssets = document.querySelectorAll('.asset-btn-sports');
            
            const fAs = document.getElementById('finance-asset-settings');
            const fRs = document.getElementById('finance-risk-settings');
            const sRs = document.getElementById('sports-risk-settings');

            if(universe === 'SPORTS') {
                finAssets.forEach(el => { el.style.display = 'none'; });
                if (moreAssetsWrapper) moreAssetsWrapper.style.display = 'none';
                sportsAssets.forEach(el => { el.style.display = 'inline-block'; el.classList.remove('hidden'); });
                
                if(fAs) fAs.classList.add('hidden');
                if(fRs) fRs.classList.add('hidden');
                if(sRs) sRs.classList.remove('hidden');

                document.getElementById('lw-chart-container').style.display = 'none';
                document.getElementById('stats-bar-target').style.display = 'none';
                document.getElementById('sports-event-list').style.display = 'block';
                document.getElementById('sports-event-list').classList.remove('hidden');
                
                if (window.activeSportsEventMarket) {
                    const found = Array.from(sportsAssets).find(b => b.innerText.includes(window.activeSportsEventMarket));
                    if(found) found.click();
                    else filterSportsEvents('NFL');
                } else {
                    filterSportsEvents('NFL');
                }
            } else {
                finAssets.forEach(el => { el.style.display = ''; el.classList.remove('hidden'); });
                if (moreAssetsWrapper) moreAssetsWrapper.style.display = '';
                sportsAssets.forEach(el => { el.style.display = 'none'; el.classList.add('hidden'); });
                
                if(fAs) fAs.classList.remove('hidden');
                if(fRs) fRs.classList.remove('hidden');
                if(sRs) sRs.classList.add('hidden');

                document.getElementById('lw-chart-container').style.display = 'block';
                document.getElementById('stats-bar-target').style.display = 'flex';
                document.getElementById('sports-event-list').style.display = 'none';
                document.getElementById('sports-event-list').classList.add('hidden');

                const found = Array.from(finAssets).find(b => b.innerText.includes(window.activeAsset));
                if(found) found.click();
                else if (typeof selectDashboardAsset === 'function') selectDashboardAsset('BTC');
            }
        };

        """

new_content = content[:start_idx] + correct_function + content[end_idx:]

with open(html_path, "w", encoding="utf-8") as f:
    f.write(new_content)

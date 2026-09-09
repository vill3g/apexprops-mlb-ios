
import json, os
from backend.engine.top5_selector import Top5Selector
from backend.engine.pitcher_k_model import PitcherKModel
from backend.data.espn_client import ESPNClient
from backend.data.draftkings_client import DraftKingsClient
from backend.data.injuries_client import InjuriesClient

espn = ESPNClient()
dk = DraftKingsClient()
injuries = InjuriesClient()
injuries.refresh_injuries()
selector = Top5Selector(espn_client=espn)
pitcher_model = PitcherKModel()
os.makedirs('static/data', exist_ok=True)

picks_data = selector.generate_daily_picks(force_refresh=True)
with open('static/data/top5.json', 'w', encoding='utf-8') as f:
    json.dump({'timestamp': picks_data['timestamp'], 'slate_count': picks_data['slate_count'], 'total_props': picks_data['total_props'], 'top_5': picks_data['top_5']}, f, indent=2, ensure_ascii=False)

with open('static/data/props.json', 'w', encoding='utf-8') as f:
    json.dump({'count': len(picks_data['all_props']), 'props': picks_data['all_props']}, f, indent=2, ensure_ascii=False)

slate = espn.get_todays_slate(force_refresh=True)
k_data = pitcher_model.get_pitcher_k_data(slate)
with open('static/data/pitchers.json', 'w', encoding='utf-8') as f:
    json.dump(k_data, f, indent=2, ensure_ascii=False)

odds_list = []
for g in slate:
    ev_id = g.get('game_id')
    away_abbr = g.get('away_team', {}).get('abbreviation', 'AWAY')
    home_abbr = g.get('home_team', {}).get('abbreviation', 'HOME')
    if ev_id:
        dk_data = dk.get_game_dk_odds(ev_id, away_abbr)
        odds_list.append({
            'game_id': ev_id,
            'matchup': away_abbr + ' @ ' + home_abbr,
            'home_team': g.get('home_team', {}).get('name'),
            'away_team': g.get('away_team', {}).get('name'),
            'venue': g.get('venue'),
            'draftkings': dk_data
        })
with open('static/data/draftkings.json', 'w', encoding='utf-8') as f:
    json.dump({'count': len(odds_list), 'provider': 'DraftKings', 'logo': dk.dk_logo, 'games': odds_list}, f, indent=2)

from backend.engine.international_model import InternationalBaseballModel
intl = InternationalBaseballModel()

npb_games = intl.get_npb_slate()
npb_props = intl.get_npb_props()
with open('static/data/npb.json', 'w', encoding='utf-8') as f:
    json.dump({'league': 'Japan NPB', 'count': len(npb_games), 'games': npb_games, 'props': npb_props}, f, indent=2)

kbo_games = intl.get_kbo_slate()
kbo_props = intl.get_kbo_props()
with open('static/data/kbo.json', 'w', encoding='utf-8') as f:
    json.dump({'league': 'Korea KBO', 'count': len(kbo_games), 'games': kbo_games, 'props': kbo_props}, f, indent=2)

print('SUCCESS: Static data synced!')
print('Top 5 picks:', len(picks_data['top_5']))
for p in picks_data['top_5']:
    print(' ', p['top_rank'], p['name'], p['team'], p['game_datetime'], p['dk_odds'])
print('NPB Props:', len(npb_props))
print('KBO Props:', len(kbo_props))


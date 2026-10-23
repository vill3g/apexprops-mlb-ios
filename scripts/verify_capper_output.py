import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from backend.sports_engine.master_capper import MasterSportsCapper

sample_events = [
    ('KXNHLGAME-26OCT12FLABUF', 'Florida Panthers vs Buffalo Sabres', 'Buffalo Sabres', 'NHL', 'MONEYLINE', 53.4, 0.50),
    ('KXNFLSPREAD-26OCT12DALPHI', 'Dallas Cowboys @ Philadelphia Eagles', 'Philadelphia Eagles', 'NFL', 'SPREAD', 57.0, 0.52),
    ('KXEPLGAME-26OCT12ARSLEE', 'Arsenal vs Leeds United', 'Arsenal', 'SOC', '3_WAY', 72.5, 0.68),
    ('KXUFCFIGHT-26OCT12ALLDUN', 'Allen vs Duncan', 'Allen', 'UFC', 'FIGHT_WINNER', 62.0, 0.58)
]

for tk, matchup, pick, sport, mtype, prob, price in sample_events:
    analysis = MasterSportsCapper.evaluate_capper_edge(
        sport=sport,
        matchup=matchup,
        pick_name=pick,
        market_type=mtype,
        model_win_prob=prob,
        kalshi_price_dollars=price,
        bankroll=1000.0
    )
    print(f"=== [{sport}] {matchup} ===")
    print(f"Pick: {analysis['pick']} | Market: {analysis['market_type']}")
    print(f"Grade: {analysis['grade']} {analysis['stars']} ({analysis['tier_label']})")
    print(f"Win Prob: {analysis['model_win_pct']}% vs Kalshi {analysis['kalshi_implied_pct']}% (Raw Edge: {analysis['raw_edge_pct']}%)")
    print(f"Net EV: {analysis['net_ev_pct']}% | Fee: ${analysis['fee_per_contract']:.4f}/contract")
    print(f"Sizing: {analysis['kelly_bankroll_pct']}% Kelly -> ${analysis['recommended_wager']:.2f}")
    print(f"Thesis: {analysis['capper_thesis']}")
    print()

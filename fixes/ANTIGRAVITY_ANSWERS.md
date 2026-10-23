# Answers for Section 0

1. **Which sports and endpoints `bot_bridge_router.py` merges into `/api/bot-bridge/predictions`.**
The router merges MLB (via local import `get_top5_picks`) and NFL (via local import `get_nfl_picks`). It also fetches via HTTP from endpoints for NHL, SOCCER, TENNIS, UFC, NBA, NCAAF, and NPB (`/api/{sport}/top_picks`).

2. **Whether `/api/nfl/top_picks` props reach the bridge.**
Yes. They are fetched natively by `_fetch_nfl()` (which calls `api_top_picks_feed`). The normalize function sets `market_type` to `"Player Prop"`, `metadata.type` to `"Player Prop"`, `metadata.stat_name` to the specific stat (e.g. "Receiving Yds"), and `metadata.line` to the pick side/value (e.g. "OVER 24.5 Receiving Yds").

3. **Whether ApexProps predicts any MLB player props (hits+runs+RBIs, home runs, strikeouts, total bases).**
Yes, ApexProps predicts MLB player props (like H+R+RBI and Pitcher Ks). However, the dictionaries emitted by `get_top5_picks` do not include a `"type"` or `"stat_name"` field. As a result, the bridge's `_normalize` function mistakenly defaults their `market_type` to `"MONEYLINE"`.

4. **What `confidence_pct` means for each market type.**
- Moneyline: win probability of `predicted_team`.
- Puck line / spread: the probability that the pick's `metadata.line` covers.
- Total: the probability of the over/under side named in `metadata.line`.
- Prop: the probability of `metadata.line`.

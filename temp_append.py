text = '''
### 17. NBA Explain Endpoint (Verified)

**GET /api/nba/explain/KXNBAGAME-26OCT20OKCSAS**
`json
{
  "market": "moneyline",
  "pick": "San Antonio",
  "side": "",
  "line": "",
  "probability": 57.6,
  "projected": 2.5,
  "projected_unit": "points margin",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (San Antonio)",
      "detail": "115.0 ORtg vs 115.0 League Avg",
      "impact": 0.0,
      "unit": "%"
    },
    {
      "label": "Away Offense (Oklahoma City)",
      "detail": "115.0 ORtg vs 115.0 League Avg",
      "impact": 0.0,
      "unit": "%"
    },
    {
      "label": "Game Pace",
      "detail": "Expected pace vs 99.0 League Avg",
      "impact": 0.0,
      "unit": "%"
    },
    {
      "label": "Home Court Advantage",
      "detail": "+2.5 pts to home team",
      "impact": 7.6,
      "unit": "%"
    }
  ],
  "not_used": [
    "Referee assignments",
    "Live sportsbook odds"
  ]
}
`

**GET /api/nba/explain/KXNBAGAME-26OCT20OKCSAS?market=total&line=220.5&side=over**
`json
{
  "market": "total",
  "pick": "OVER",
  "side": "over",
  "line": "220.5",
  "probability": 74.1,
  "projected": 230.2,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (San Antonio)",
      "detail": "115.0 ORtg vs 115.0 League Avg",
      "impact": 0.0,
      "unit": "points"
    },
    {
      "label": "Away Offense (Oklahoma City)",
      "detail": "115.0 ORtg vs 115.0 League Avg",
      "impact": 0.0,
      "unit": "points"
    },
    {
      "label": "Game Pace",
      "detail": "Expected pace vs 99.0 League Avg",
      "impact": 0.0,
      "unit": "points"
    },
    {
      "label": "Home Court Advantage",
      "detail": "+2.5 pts to home team",
      "impact": 2.5,
      "unit": "points"
    }
  ],
  "not_used": [
    "Referee assignments",
    "Live sportsbook odds"
  ]
}
`

**GET /api/nba/explain/KXNBAGAME-26OCT20OKCSAS?market=total&line=220.5&side=under**
`json
{
  "market": "total",
  "pick": "UNDER",
  "side": "under",
  "line": "220.5",
  "probability": 25.9,
  "projected": 230.2,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (San Antonio)",
      "detail": "115.0 ORtg vs 115.0 League Avg",
      "impact": -0.0,
      "unit": "points"
    },
    {
      "label": "Away Offense (Oklahoma City)",
      "detail": "115.0 ORtg vs 115.0 League Avg",
      "impact": -0.0,
      "unit": "points"
    },
    {
      "label": "Game Pace",
      "detail": "Expected pace vs 99.0 League Avg",
      "impact": -0.0,
      "unit": "points"
    },
    {
      "label": "Home Court Advantage",
      "detail": "+2.5 pts to home team",
      "impact": -2.5,
      "unit": "points"
    }
  ],
  "not_used": [
    "Referee assignments",
    "Live sportsbook odds"
  ]
}
`

**GET /api/nba/explain/does-not-exist**
{"detail":"NBA game stats not yet loaded"}

**GET /api/nba/explain/KXNBAGAME-26OCT20OKCSAS/narrative**
`json
{"enabled":true,"narrative":"**Official Pick:** San Antonio (57.6% win probability)\\n\\n**Key Factors:**\\n* **Home-Court Advantage:** San Antonio benefits from a +2.5 point home-court boost, which contributes 7.6 impact points to their win probability.\\n* **Evenly Matched Offenses:** Both Oklahoma City and San Antonio possess identical 115.0 offensive ratings, making the home-court edge the deciding factor in this matchup."}
`
'''
with open(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\fixes\SPORTS_PICKS_FOR_ANTIGRAVITY.md', 'a') as f:
    f.write(text)

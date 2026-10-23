import json

text = '''
### 20. NBA Tweaks Verified

**GET /api/nba/explain/KXNBAGAME-26OCT20BOSDET**
`json
{
  "market": "moneyline",
  "pick": "Boston",
  "side": "",
  "line": "",
  "probability": 77.2,
  "projected": 226.8,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (Detroit)",
      "detail": "109.0 ORtg vs 115.0 League Avg",
      "impact": 8.9,
      "unit": "%"
    },
    {
      "label": "Away Offense (Boston)",
      "detail": "122.2 ORtg vs 115.0 League Avg",
      "impact": 11.2,
      "unit": "%"
    },
    {
      "label": "Game Pace",
      "detail": "98.6 expected vs 99.0 League Avg",
      "impact": -0.1,
      "unit": "%"
    },
    {
      "label": "Home Court Advantage",
      "detail": "+2.5 pts to home team",
      "impact": -5.3,
      "unit": "%"
    }
  ],
  "not_used": [
    "Referee assignments",
    "Live sportsbook odds"
  ]
}
`

**GET /api/nba/explain/KXNBAGAME-26OCT20PHINYK?market=total&line=220.5&side=over**
`json
{
  "market": "total",
  "pick": "UNDER",
  "side": "over",
  "line": "220.5",
  "probability": 57.4,
  "projected": 217.7,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (New York)",
      "detail": "117.3 ORtg vs 115.0 League Avg",
      "impact": 1.3,
      "unit": "points"
    },
    {
      "label": "Away Offense (Philadelphia)",
      "detail": "116.2 ORtg vs 115.0 League Avg",
      "impact": 0.7,
      "unit": "points"
    },
    {
      "label": "Game Pace",
      "detail": "94.7 expected vs 99.0 League Avg",
      "impact": -9.8,
      "unit": "points"
    },
    {
      "label": "Home Court Advantage",
      "detail": "+2.5 pts to home team",
      "impact": 0.0,
      "unit": "points"
    }
  ],
  "not_used": [
    "Referee assignments",
    "Live sportsbook odds"
  ],
  "requested_side_probability": 42.6
}
`

**GET /api/nba/explain/KXNBAGAME-26OCT20PHINYK?market=total&line=220.5&side=under**
`json
{
  "market": "total",
  "pick": "UNDER",
  "side": "under",
  "line": "220.5",
  "probability": 57.4,
  "projected": 217.7,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (New York)",
      "detail": "117.3 ORtg vs 115.0 League Avg",
      "impact": 1.3,
      "unit": "points"
    },
    {
      "label": "Away Offense (Philadelphia)",
      "detail": "116.2 ORtg vs 115.0 League Avg",
      "impact": 0.7,
      "unit": "points"
    },
    {
      "label": "Game Pace",
      "detail": "94.7 expected vs 99.0 League Avg",
      "impact": -9.8,
      "unit": "points"
    },
    {
      "label": "Home Court Advantage",
      "detail": "+2.5 pts to home team",
      "impact": 0.0,
      "unit": "points"
    }
  ],
  "not_used": [
    "Referee assignments",
    "Live sportsbook odds"
  ],
  "requested_side_probability": 57.4
}
`
'''
with open(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\fixes\SPORTS_PICKS_FOR_ANTIGRAVITY.md', 'a') as f:
    f.write(text)

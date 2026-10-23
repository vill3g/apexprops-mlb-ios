import json

text = '''
### 18. NBA Fixes Verified (Restarted)

**GET /api/nba/explain/KXNBAGAME-26OCT20OKCSAS**
`json
{
  "market": "moneyline",
  "pick": "Oklahoma City",
  "side": "",
  "line": "",
  "probability": 80.6,
  "projected": 229.9,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (San Antonio)",
      "detail": "109.3 ORtg vs 115.0 League Avg",
      "impact": 12.0,
      "unit": "%"
    },
    {
      "label": "Away Offense (Oklahoma City)",
      "detail": "118.3 ORtg vs 115.0 League Avg",
      "impact": 7.9,
      "unit": "%"
    },
    {
      "label": "Game Pace",
      "detail": "Expected pace vs 99.0 League Avg",
      "impact": 0.9,
      "unit": "%"
    },
    {
      "label": "Home Court Advantage",
      "detail": "+2.5 pts to home team",
      "impact": -4.9,
      "unit": "%"
    }
  ],
  "not_used": [
    "Referee assignments",
    "Live sportsbook odds"
  ]
}
`

**GET /api/nba/explain/KXNBAGAME-26OCT20BOSDET**
`json
{
  "market": "moneyline",
  "pick": "Boston",
  "side": "",
  "line": "",
  "probability": 91.4,
  "projected": 227.0,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (Detroit)",
      "detail": "109.0 ORtg vs 115.0 League Avg",
      "impact": 9.0,
      "unit": "%"
    },
    {
      "label": "Away Offense (Boston)",
      "detail": "122.2 ORtg vs 115.0 League Avg",
      "impact": 12.0,
      "unit": "%"
    },
    {
      "label": "Game Pace",
      "detail": "Expected pace vs 99.0 League Avg",
      "impact": -0.1,
      "unit": "%"
    },
    {
      "label": "Home Court Advantage",
      "detail": "+2.5 pts to home team",
      "impact": -2.7,
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
  "pick": "OVER",
  "side": "over",
  "line": "220.5",
  "probability": 42.3,
  "projected": 217.6,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (New York)",
      "detail": "117.3 ORtg vs 115.0 League Avg",
      "impact": 2.2,
      "unit": "points"
    },
    {
      "label": "Away Offense (Philadelphia)",
      "detail": "116.2 ORtg vs 115.0 League Avg",
      "impact": 1.2,
      "unit": "points"
    },
    {
      "label": "Game Pace",
      "detail": "Expected pace vs 99.0 League Avg",
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
  ]
}
`

**GET /api/nba/explain/KXNBAGAME-26OCT20PHINYK?market=total&line=220.5&side=under**
`json
{
  "market": "total",
  "pick": "UNDER",
  "side": "under",
  "line": "220.5",
  "probability": 57.7,
  "projected": 217.6,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form Normal Distribution Model with pace & injury adjustments.",
  "factors": [
    {
      "label": "Home Offense (New York)",
      "detail": "117.3 ORtg vs 115.0 League Avg",
      "impact": 2.2,
      "unit": "points"
    },
    {
      "label": "Away Offense (Philadelphia)",
      "detail": "116.2 ORtg vs 115.0 League Avg",
      "impact": 1.2,
      "unit": "points"
    },
    {
      "label": "Game Pace",
      "detail": "Expected pace vs 99.0 League Avg",
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
  ]
}
`
'''
with open(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\fixes\SPORTS_PICKS_FOR_ANTIGRAVITY.md', 'a') as f:
    f.write(text)

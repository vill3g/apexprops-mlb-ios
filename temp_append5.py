import json

text = '''
### 21. NCAAF Explainer Added

**GET /api/ncaaf/explain/KXNCAAFGAME-26OCT10UGAALA**
`json
{
  "market": "moneyline",
  "pick": "Georgia",
  "side": "",
  "line": "",
  "probability": 52.6,
  "projected": 53.9,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form SP+ Model with pace adjustments.",
  "factors": [
    {
      "label": "Home Offense (Alabama)",
      "detail": "40.5 SP+ vs 25.0 League Avg",
      "impact": -12.0,
      "unit": "%"
    },
    {
      "label": "Away Offense (Georgia)",
      "detail": "42.5 SP+ vs 25.0 League Avg",
      "impact": 12.0,
      "unit": "%"
    },
    {
      "label": "Home Defense (Alabama)",
      "detail": "14.0 SP+ vs 25.0 League Avg",
      "impact": -12.0,
      "unit": "%"
    },
    {
      "label": "Away Defense (Georgia)",
      "detail": "10.2 SP+ vs 25.0 League Avg",
      "impact": 12.0,
      "unit": "%"
    },
    {
      "label": "Game Pace",
      "detail": "67.5 expected vs 68.0 League Avg",
      "impact": -0.1,
      "unit": "%"
    },
    {
      "label": "Home Field Advantage",
      "detail": "+2.5 pts to home team",
      "impact": -6.8,
      "unit": "%"
    }
  ],
  "not_used": [
    "Weather conditions",
    "Live sportsbook odds"
  ]
}
`

**GET /api/ncaaf/explain/KXNCAAFGAME-26OCT10UGAALA?market=spread&line=-1.5**
`json
{
  "market": "spread",
  "pick": "Georgia -1.5",
  "side": "",
  "line": "-1.5",
  "probability": 51.7,
  "projected": 53.9,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form SP+ Model with pace adjustments.",
  "factors": [
    {
      "label": "Home Offense (Alabama)",
      "detail": "40.5 SP+ vs 25.0 League Avg",
      "impact": -12.0,
      "unit": "%"
    },
    {
      "label": "Away Offense (Georgia)",
      "detail": "42.5 SP+ vs 25.0 League Avg",
      "impact": 12.0,
      "unit": "%"
    },
    {
      "label": "Home Defense (Alabama)",
      "detail": "14.0 SP+ vs 25.0 League Avg",
      "impact": -12.0,
      "unit": "%"
    },
    {
      "label": "Away Defense (Georgia)",
      "detail": "10.2 SP+ vs 25.0 League Avg",
      "impact": 12.0,
      "unit": "%"
    },
    {
      "label": "Game Pace",
      "detail": "67.5 expected vs 68.0 League Avg",
      "impact": -0.1,
      "unit": "%"
    },
    {
      "label": "Home Field Advantage",
      "detail": "+2.5 pts to home team",
      "impact": -6.8,
      "unit": "%"
    }
  ],
  "not_used": [
    "Weather conditions",
    "Live sportsbook odds"
  ]
}
`

**GET /api/ncaaf/explain/KXNCAAFGAME-26OCT10TXAMMIZZ?market=total&line=54.5&side=over**
`json
{
  "market": "total",
  "pick": "UNDER",
  "side": "over",
  "line": "54.5",
  "probability": 59.8,
  "projected": 50.9,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form SP+ Model with pace adjustments.",
  "factors": [
    {
      "label": "Home Offense (Missouri)",
      "detail": "37.0 SP+ vs 25.0 League Avg",
      "impact": 7.0,
      "unit": "points"
    },
    {
      "label": "Away Offense (Texas A&M)",
      "detail": "32.0 SP+ vs 25.0 League Avg",
      "impact": 4.1,
      "unit": "points"
    },
    {
      "label": "Home Defense (Missouri)",
      "detail": "19.5 SP+ vs 25.0 League Avg",
      "impact": -3.2,
      "unit": "points"
    },
    {
      "label": "Away Defense (Texas A&M)",
      "detail": "15.5 SP+ vs 25.0 League Avg",
      "impact": -5.5,
      "unit": "points"
    },
    {
      "label": "Game Pace",
      "detail": "66.0 expected vs 68.0 League Avg",
      "impact": -1.5,
      "unit": "points"
    },
    {
      "label": "Home Field Advantage",
      "detail": "+2.5 pts to home team",
      "impact": 0.0,
      "unit": "points"
    }
  ],
  "not_used": [
    "Weather conditions",
    "Live sportsbook odds"
  ],
  "requested_side_probability": 40.2
}
`

**GET /api/ncaaf/explain/KXNCAAFGAME-26OCT10TXAMMIZZ?market=total&line=54.5&side=under**
`json
{
  "market": "total",
  "pick": "UNDER",
  "side": "under",
  "line": "54.5",
  "probability": 59.8,
  "projected": 50.9,
  "projected_unit": "points",
  "iterations": 1000,
  "method": "Closed-form SP+ Model with pace adjustments.",
  "factors": [
    {
      "label": "Home Offense (Missouri)",
      "detail": "37.0 SP+ vs 25.0 League Avg",
      "impact": 7.0,
      "unit": "points"
    },
    {
      "label": "Away Offense (Texas A&M)",
      "detail": "32.0 SP+ vs 25.0 League Avg",
      "impact": 4.1,
      "unit": "points"
    },
    {
      "label": "Home Defense (Missouri)",
      "detail": "19.5 SP+ vs 25.0 League Avg",
      "impact": -3.2,
      "unit": "points"
    },
    {
      "label": "Away Defense (Texas A&M)",
      "detail": "15.5 SP+ vs 25.0 League Avg",
      "impact": -5.5,
      "unit": "points"
    },
    {
      "label": "Game Pace",
      "detail": "66.0 expected vs 68.0 League Avg",
      "impact": -1.5,
      "unit": "points"
    },
    {
      "label": "Home Field Advantage",
      "detail": "+2.5 pts to home team",
      "impact": 0.0,
      "unit": "points"
    }
  ],
  "not_used": [
    "Weather conditions",
    "Live sportsbook odds"
  ],
  "requested_side_probability": 59.8
}
`

**GET /api/ncaaf/explain/does-not-exist**
`json
{
  "detail": "Game does not have active real SP+ ratings loaded yet"
}
`
HTTP Status: 404
'''
with open(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\fixes\SPORTS_PICKS_FOR_ANTIGRAVITY.md', 'a') as f:
    f.write(text)

with open("backend/routes/engine.py", "r", encoding="utf-8") as f:
    c = f.read()

team_map_code = """
_TEAM_NAME_MAP = {
    # MLB
    "ARI": "Arizona Diamondbacks", "ARIZONA": "Arizona Diamondbacks",
    "ATL": "Atlanta Braves", "ATLANTA": "Atlanta Braves",
    "BAL": "Baltimore Orioles", "BALTIMORE": "Baltimore Orioles",
    "BOS": "Boston Red Sox", "BOSTON": "Boston Red Sox",
    "CHC": "Chicago Cubs", "CWS": "Chicago White Sox", "CHICAGO WS": "Chicago White Sox", "CHW": "Chicago White Sox",
    "CIN": "Cincinnati Reds", "CINCINNATI": "Cincinnati Reds",
    "CLE": "Cleveland Guardians", "CLEVELAND": "Cleveland Guardians",
    "COL": "Colorado Rockies", "COLORADO": "Colorado Rockies",
    "DET": "Detroit Tigers", "DETROIT": "Detroit Tigers",
    "HOU": "Houston Astros", "HOUSTON": "Houston Astros",
    "KC": "Kansas City Royals", "KANSAS CITY": "Kansas City Royals",
    "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers", "LOS ANGELES D": "Los Angeles Dodgers",
    "MIA": "Miami Marlins", "MIAMI": "Miami Marlins",
    "MIL": "Milwaukee Brewers", "MILWAUKEE": "Milwaukee Brewers",
    "MIN": "Minnesota Twins", "MINNESOTA": "Minnesota Twins",
    "NYM": "New York Mets", "NYY": "New York Yankees", "NEW YORK M": "New York Mets", "NEW YORK Y": "New York Yankees",
    "OAK": "Oakland Athletics", "OAKLAND": "Oakland Athletics",
    "PHI": "Philadelphia Phillies", "PHILADELPHIA": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates", "PITTSBURGH": "Pittsburgh Pirates",
    "SD": "San Diego Padres", "SAN DIEGO": "San Diego Padres", "SDP": "San Diego Padres",
    "SF": "San Francisco Giants", "SAN FRANCISCO": "San Francisco Giants", "SFG": "San Francisco Giants",
    "SEA": "Seattle Mariners", "SEATTLE": "Seattle Mariners",
    "STL": "St. Louis Cardinals", "ST. LOUIS": "St. Louis Cardinals", "ST LOUIS": "St. Louis Cardinals",
    "TB": "Tampa Bay Rays", "TAMPA BAY": "Tampa Bay Rays", "TBR": "Tampa Bay Rays",
    "TEX": "Texas Rangers", "TEXAS": "Texas Rangers",
    "TOR": "Toronto Blue Jays", "TORONTO": "Toronto Blue Jays",
    "WSH": "Washington Nationals", "WASHINGTON": "Washington Nationals", "WAS": "Washington Nationals",
    
    # NFL
    "BUF": "Buffalo Bills", "BUFFALO": "Buffalo Bills",
    "MIA": "Miami Dolphins", "MIAMI": "Miami Dolphins",
    "NE": "New England Patriots", "NEW ENGLAND": "New England Patriots",
    "NYJ": "New York Jets", "NEW YORK J": "New York Jets",
    "BAL": "Baltimore Ravens", "BALTIMORE": "Baltimore Ravens",
    "CIN": "Cincinnati Bengals", "CINCINNATI": "Cincinnati Bengals",
    "CLE": "Cleveland Browns", "CLEVELAND": "Cleveland Browns",
    "PIT": "Pittsburgh Steelers", "PITTSBURGH": "Pittsburgh Steelers",
    "HOU": "Houston Texans", "HOUSTON": "Houston Texans",
    "IND": "Indianapolis Colts", "INDIANAPOLIS": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars", "JACKSONVILLE": "Jacksonville Jaguars",
    "TEN": "Tennessee Titans", "TENNESSEE": "Tennessee Titans",
    "DEN": "Denver Broncos", "DENVER": "Denver Broncos",
    "KC": "Kansas City Chiefs", "KANSAS CITY": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders", "LAS VEGAS": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers", "LOS ANGELES C": "Los Angeles Chargers",
    "DAL": "Dallas Cowboys", "DALLAS": "Dallas Cowboys",
    "NYG": "New York Giants", "NEW YORK G": "New York Giants",
    "PHI": "Philadelphia Eagles", "PHILADELPHIA": "Philadelphia Eagles",
    "WAS": "Washington Commanders", "WASHINGTON": "Washington Commanders",
    "CHI": "Chicago Bears", "CHICAGO": "Chicago Bears",
    "DET": "Detroit Lions", "DETROIT": "Detroit Lions",
    "GB": "Green Bay Packers", "GREEN BAY": "Green Bay Packers",
    "MIN": "Minnesota Vikings", "MINNESOTA": "Minnesota Vikings",
    "ATL": "Atlanta Falcons", "ATLANTA": "Atlanta Falcons",
    "CAR": "Carolina Panthers", "CAROLINA": "Carolina Panthers",
    "NO": "New Orleans Saints", "NEW ORLEANS": "New Orleans Saints",
    "TB": "Tampa Bay Buccaneers", "TAMPA BAY": "Tampa Bay Buccaneers",
    "ARI": "Arizona Cardinals", "ARIZONA": "Arizona Cardinals",
    "LAR": "Los Angeles Rams", "LOS ANGELES R": "Los Angeles Rams",
    "SF": "San Francisco 49ers", "SAN FRANCISCO": "San Francisco 49ers",
    "SEA": "Seattle Seahawks", "SEATTLE": "Seattle Seahawks",

    # NHL
    "BOS": "Boston Bruins", "BOSTON": "Boston Bruins",
    "BUF": "Buffalo Sabres", "BUFFALO": "Buffalo Sabres",
    "DET": "Detroit Red Wings", "DETROIT": "Detroit Red Wings",
    "FLA": "Florida Panthers", "FLORIDA": "Florida Panthers",
    "MTL": "Montreal Canadiens", "MONTREAL": "Montreal Canadiens",
    "OTT": "Ottawa Senators", "OTTAWA": "Ottawa Senators",
    "TB": "Tampa Bay Lightning", "TAMPA BAY": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs", "TORONTO": "Toronto Maple Leafs",
    "CAR": "Carolina Hurricanes", "CAROLINA": "Carolina Hurricanes",
    "CBJ": "Columbus Blue Jackets", "COLUMBUS": "Columbus Blue Jackets",
    "NJ": "New Jersey Devils", "NEW JERSEY": "New Jersey Devils",
    "NYI": "New York Islanders", "NEW YORK I": "New York Islanders",
    "NYR": "New York Rangers", "NEW YORK R": "New York Rangers",
    "PHI": "Philadelphia Flyers", "PHILADELPHIA": "Philadelphia Flyers",
    "PIT": "Pittsburgh Penguins", "PITTSBURGH": "Pittsburgh Penguins",
    "WSH": "Washington Capitals", "WASHINGTON": "Washington Capitals", "WAS": "Washington Capitals",
    "CHI": "Chicago Blackhawks", "CHICAGO": "Chicago Blackhawks",
    "COL": "Colorado Avalanche", "COLORADO": "Colorado Avalanche",
    "DAL": "Dallas Stars", "DALLAS": "Dallas Stars",
    "MIN": "Minnesota Wild", "MINNESOTA": "Minnesota Wild",
    "NSH": "Nashville Predators", "NASHVILLE": "Nashville Predators",
    "STL": "St. Louis Blues", "ST. LOUIS": "St. Louis Blues",
    "WPG": "Winnipeg Jets", "WINNIPEG": "Winnipeg Jets",
    "ANA": "Anaheim Ducks", "ANAHEIM": "Anaheim Ducks",
    "CGY": "Calgary Flames", "CALGARY": "Calgary Flames",
    "EDM": "Edmonton Oilers", "EDMONTON": "Edmonton Oilers",
    "LA": "Los Angeles Kings", "LOS ANGELES K": "Los Angeles Kings", "LAK": "Los Angeles Kings",
    "SJS": "San Jose Sharks", "SAN JOSE": "San Jose Sharks", "SJ": "San Jose Sharks",
    "SEA": "Seattle Kraken", "SEATTLE": "Seattle Kraken",
    "VAN": "Vancouver Canucks", "VANCOUVER": "Vancouver Canucks",
    "VGK": "Vegas Golden Knights", "VEGAS": "Vegas Golden Knights",
    "UTA": "Utah Hockey Club", "UTAH": "Utah Hockey Club",
}

def _normalize_team_name(name: str) -> str:
    n = (name or "").upper().strip()
    if not n: return ""
    return _TEAM_NAME_MAP.get(n, n)

"""

if "_TEAM_NAME_MAP = {" not in c:
    c = c.replace("def _normalize_sport(s: str) -> str:", team_map_code + "def _normalize_sport(s: str) -> str:")
    with open("backend/routes/engine.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("Added _TEAM_NAME_MAP")
else:
    print("Already added")

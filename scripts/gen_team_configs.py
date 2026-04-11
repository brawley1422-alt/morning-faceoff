#!/usr/bin/env python3
"""Generate teams/{slug}.json for all 32 NHL teams.

Pulls team list from /standings/now (has abbrev, division, conference,
common name). Applies hand-maintained color/venue tables. Run once at
scaffold time; re-run if NHL adds/moves a team.
"""
import json, urllib.request, re
from pathlib import Path

STANDINGS = "https://api-web.nhle.com/v1/standings/now"

# Hand-maintained brand table. Colors from NHL style guides / Wikipedia.
# Source of truth for everything we can't pull from the API.
BRAND = {
    "ANA": ("ducks", "Anaheim Ducks", "#F47A38", "#B9975B", "Honda Center"),
    "BOS": ("bruins", "Boston Bruins", "#FFB81C", "#000000", "TD Garden"),
    "BUF": ("sabres", "Buffalo Sabres", "#002654", "#FCB514", "KeyBank Center"),
    "CGY": ("flames", "Calgary Flames", "#C8102E", "#F1BE48", "Scotiabank Saddledome"),
    "CAR": ("hurricanes", "Carolina Hurricanes", "#CC0000", "#A2AAAD", "Lenovo Center"),
    "CHI": ("blackhawks", "Chicago Blackhawks", "#CF0A2C", "#FF671F", "United Center"),
    "COL": ("avalanche", "Colorado Avalanche", "#6F263D", "#236192", "Ball Arena"),
    "CBJ": ("blue-jackets", "Columbus Blue Jackets", "#002654", "#CE1126", "Nationwide Arena"),
    "DAL": ("stars", "Dallas Stars", "#006847", "#8F8F8C", "American Airlines Center"),
    "DET": ("red-wings", "Detroit Red Wings", "#CE1126", "#FFFFFF", "Little Caesars Arena"),
    "EDM": ("oilers", "Edmonton Oilers", "#041E42", "#FF4C00", "Rogers Place"),
    "FLA": ("panthers", "Florida Panthers", "#041E42", "#C8102E", "Amerant Bank Arena"),
    "LAK": ("kings", "Los Angeles Kings", "#111111", "#A2AAAD", "Crypto.com Arena"),
    "MIN": ("wild", "Minnesota Wild", "#154734", "#DDCBA4", "Grand Casino Arena"),
    "MTL": ("canadiens", "Montreal Canadiens", "#AF1E2D", "#192168", "Bell Centre"),
    "NSH": ("predators", "Nashville Predators", "#FFB81C", "#041E42", "Bridgestone Arena"),
    "NJD": ("devils", "New Jersey Devils", "#CE1126", "#000000", "Prudential Center"),
    "NYI": ("islanders", "New York Islanders", "#00539B", "#F47D30", "UBS Arena"),
    "NYR": ("rangers", "New York Rangers", "#0038A8", "#CE1126", "Madison Square Garden"),
    "OTT": ("senators", "Ottawa Senators", "#C52032", "#C2912C", "Canadian Tire Centre"),
    "PHI": ("flyers", "Philadelphia Flyers", "#F74902", "#000000", "Wells Fargo Center"),
    "PIT": ("penguins", "Pittsburgh Penguins", "#000000", "#FCB514", "PPG Paints Arena"),
    "SJS": ("sharks", "San Jose Sharks", "#006D75", "#EA7200", "SAP Center"),
    "SEA": ("kraken", "Seattle Kraken", "#001628", "#99D9D9", "Climate Pledge Arena"),
    "STL": ("blues", "St. Louis Blues", "#002F87", "#FCB514", "Enterprise Center"),
    "TBL": ("lightning", "Tampa Bay Lightning", "#002868", "#FFFFFF", "Benchmark International Arena"),
    "TOR": ("maple-leafs", "Toronto Maple Leafs", "#00205B", "#FFFFFF", "Scotiabank Arena"),
    "UTA": ("mammoth", "Utah Mammoth", "#6CACE4", "#000000", "Delta Center"),
    "VAN": ("canucks", "Vancouver Canucks", "#00205B", "#00843D", "Rogers Arena"),
    "VGK": ("golden-knights", "Vegas Golden Knights", "#B4975A", "#333F42", "T-Mobile Arena"),
    "WSH": ("capitals", "Washington Capitals", "#C8102E", "#041E42", "Capital One Arena"),
    "WPG": ("jets", "Winnipeg Jets", "#041E42", "#AC162C", "Canada Life Centre"),
}

# AHL affiliate table — hand-maintained.
AHL = {
    "ANA": "San Diego Gulls", "BOS": "Providence Bruins", "BUF": "Rochester Americans",
    "CGY": "Calgary Wranglers", "CAR": "Chicago Wolves", "CHI": "Rockford IceHogs",
    "COL": "Colorado Eagles", "CBJ": "Cleveland Monsters", "DAL": "Texas Stars",
    "DET": "Grand Rapids Griffins", "EDM": "Bakersfield Condors", "FLA": "Charlotte Checkers",
    "LAK": "Ontario Reign", "MIN": "Iowa Wild", "MTL": "Laval Rocket",
    "NSH": "Milwaukee Admirals", "NJD": "Utica Comets", "NYI": "Bridgeport Islanders",
    "NYR": "Hartford Wolf Pack", "OTT": "Belleville Senators", "PHI": "Lehigh Valley Phantoms",
    "PIT": "Wilkes-Barre/Scranton Penguins", "SJS": "San Jose Barracuda",
    "SEA": "Coachella Valley Firebirds", "STL": "Springfield Thunderbirds",
    "TBL": "Syracuse Crunch", "TOR": "Toronto Marlies", "UTA": "Tucson Roadrunners",
    "VAN": "Abbotsford Canucks", "VGK": "Henderson Silver Knights",
    "WSH": "Hershey Bears", "WPG": "Manitoba Moose",
}


def _hi(hex_color):
    """Lighten a hex color ~15% for the '_hi' hover variant."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = min(255, int(r + (255 - r) * 0.25))
    g = min(255, int(g + (255 - g) * 0.25))
    b = min(255, int(b + (255 - b) * 0.25))
    return f"#{r:02X}{g:02X}{b:02X}"


def main():
    req = urllib.request.Request(STANDINGS, headers={"User-Agent": "Mozilla/5.0 morning-faceoff"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())

    teams_dir = Path(__file__).parent.parent / "teams"
    teams_dir.mkdir(exist_ok=True)

    # Build a rivals lookup: all teams in the same division.
    by_div = {}
    for t in data["standings"]:
        abbr = t["teamAbbrev"]["default"]
        by_div.setdefault(t["divisionName"], []).append(abbr)

    count = 0
    for t in data["standings"]:
        abbr = t["teamAbbrev"]["default"]
        if abbr not in BRAND:
            print(f"warning: no brand entry for {abbr}; skipping")
            continue
        slug, full_name, primary, accent, venue = BRAND[abbr]
        division = t["divisionName"]
        conference = t["conferenceName"]
        rivals = {a: BRAND[a][1].split()[-1] for a in by_div[division] if a != abbr and a in BRAND}

        cfg = {
            "slug": slug,
            "nhl_abbr": abbr,
            "name": full_name,
            "short_name": full_name.split()[-1] if abbr != "MTL" else "Canadiens",
            "division": division,
            "conference": conference,
            "colors": {
                "primary": primary,
                "primary_hi": _hi(primary),
                "accent": accent,
                "accent_hi": _hi(accent),
            },
            "venue": venue,
            "ahl_affiliate": AHL.get(abbr, ""),
            "rivals": rivals,
            "branding": {
                "tagline": f"A Daily {full_name.split()[-1]} Broadsheet",
                "footer_tag": f"A {full_name} Broadsheet",
                "lede_tone": "plainspoken hockey writer",
                "idle_msg": f"No {full_name.split()[-1]} game tonight.",
            },
        }

        # Red Wings override: richer editorial identity (JB's home team).
        if abbr == "DET":
            cfg["branding"] = {
                "tagline": "Hockeytown's Morning Read",
                "footer_tag": "A Hockeytown Broadsheet",
                "lede_tone": "gritty Detroit beat writer who remembers the '97 team",
                "idle_msg": "Wings are off tonight.",
            }
            cfg["short_name"] = "Red Wings"

        out = teams_dir / f"{slug}.json"
        out.write_text(json.dumps(cfg, indent=2) + "\n")
        count += 1

    print(f"wrote {count} team configs → {teams_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Morning Faceoff — daily NHL briefing generator.

Usage:
  python3 build.py --team red-wings          # build one team's page
  python3 build.py                            # build all 32 teams
  python3 build.py --landing                  # build landing page only

Data source: NHL Web API (api-web.nhle.com/v1), no auth required.
Stdlib only. Output goes to {slug}/index.html.
"""
from __future__ import annotations
import argparse, json, sys, urllib.request, urllib.error
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/Detroit")  # NHL runs on Eastern
except (ImportError, KeyError):
    ET = timezone(timedelta(hours=-4))

ROOT = Path(__file__).parent
TEAMS_DIR = ROOT / "teams"
DATA_DIR = ROOT / "data"
API = "https://api-web.nhle.com/v1"
UA = {"User-Agent": "Mozilla/5.0 morning-faceoff/0.1"}


# ─── helpers ────────────────────────────────────────────────────────────────
def fetch(path: str) -> dict:
    """GET a JSON endpoint from the NHL Web API. Returns {} on 404."""
    url = f"{API}{path}"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise


def load_team_config(slug: str) -> dict:
    p = TEAMS_DIR / f"{slug}.json"
    if not p.exists():
        sys.exit(f"error: no team config at {p}")
    return json.loads(p.read_text())


def all_team_slugs() -> list[str]:
    return sorted(p.stem for p in TEAMS_DIR.glob("*.json"))


def fmt_date(d: date) -> str:
    return d.strftime("%A, %B ") + str(d.day) + d.strftime(", %Y")


# ─── data load ──────────────────────────────────────────────────────────────
def load_all(abbr: str, today: date) -> dict:
    """Pull every NHL endpoint we need for one team's briefing.

    Returns a dict the section renderers read from. Caches the whole
    payload to data/{today}-{abbr}.json for debugging and the evening
    rebuild.
    """
    yesterday = today - timedelta(days=1)

    standings = fetch("/standings/now")
    scoreboard = fetch("/scoreboard/now")
    club_week = fetch(f"/club-schedule/{abbr}/week/now")
    club_prev_week = fetch(f"/club-schedule/{abbr}/week/{(today - timedelta(days=7)).isoformat()}")
    roster = fetch(f"/roster/{abbr}/current")

    # League-wide slate for yesterday + today. The /schedule/{date} endpoint
    # returns a forward-looking week, so to get yesterday's games we query
    # yesterday, but the returned window starts at yesterday only sometimes —
    # some dates come back empty. Safer: query both explicitly.
    week_y = fetch(f"/schedule/{yesterday.isoformat()}")
    week_t = fetch(f"/schedule/{today.isoformat()}")

    games_yesterday = []
    games_today = []
    for day in week_y.get("gameWeek", []):
        if day.get("date") == yesterday.isoformat():
            games_yesterday = day.get("games", [])
            break
    for day in week_t.get("gameWeek", []):
        if day.get("date") == today.isoformat():
            games_today = day.get("games", [])
            break

    # Today's game for this team
    def _find_team_game(games: list) -> dict | None:
        for g in games:
            if g.get("awayTeam", {}).get("abbrev") == abbr or g.get("homeTeam", {}).get("abbrev") == abbr:
                return g
        return None

    team_t = _find_team_game(games_today)

    # Most recent completed game (not strictly yesterday — could be a few
    # days back if the team was off). Search both weeks' club_schedule in
    # reverse chronological order for the newest OFF-state game.
    all_team_games = (club_prev_week.get("games", []) or []) + (club_week.get("games", []) or [])
    completed = [g for g in all_team_games if g.get("gameState") == "OFF"]
    completed.sort(key=lambda g: g.get("gameDate", ""), reverse=True)
    team_y = completed[0] if completed else None

    # Deep recap for yesterday's game (three stars, goals, etc.)
    recap = {}
    if team_y and team_y.get("id"):
        recap = fetch(f"/gamecenter/{team_y['id']}/landing")

    # Deep pregame for tonight's game (matchup stats)
    matchup = {}
    if team_t and team_t.get("id"):
        matchup = fetch(f"/gamecenter/{team_t['id']}/landing")

    payload = {
        "abbr": abbr,
        "today": today.isoformat(),
        "yesterday": yesterday.isoformat(),
        "standings": standings,
        "scoreboard": scoreboard,
        "club_week": club_week,
        "roster": roster,
        "games_yesterday": games_yesterday,
        "games_today": games_today,
        "team_y": team_y,
        "team_t": team_t,
        "recap": recap,
        "matchup": matchup,
    }

    # Persist a snapshot (one file per team per day)
    DATA_DIR.mkdir(exist_ok=True)
    snap = DATA_DIR / f"{today.isoformat()}-{abbr}.json"
    snap.write_text(json.dumps(payload, indent=2, default=str))

    return payload


# ─── briefing dataclass ─────────────────────────────────────────────────────
@dataclass
class TeamBriefing:
    slug: str
    config: dict
    data: dict
    today: date
    abbr: str
    team_name: str      # e.g. "Red Wings"
    full_name: str      # e.g. "Detroit Red Wings"
    division: str
    conference: str


def build_briefing(slug: str, today: date) -> TeamBriefing:
    cfg = load_team_config(slug)
    abbr = cfg["nhl_abbr"]
    data = load_all(abbr, today)
    return TeamBriefing(
        slug=slug,
        config=cfg,
        data=data,
        today=today,
        abbr=abbr,
        team_name=cfg["short_name"],
        full_name=cfg["name"],
        division=cfg["division"],
        conference=cfg["conference"],
    )


# ─── page envelope ──────────────────────────────────────────────────────────
import sections.headline
import sections.pregame
import sections.pulse
import sections.slate
import sections.division


def _team_record_str(briefing: TeamBriefing) -> str:
    for t in briefing.data.get("standings", {}).get("standings", []):
        if t.get("teamAbbrev", {}).get("default") == briefing.abbr:
            w, l, otl = t.get("wins", 0), t.get("losses", 0), t.get("otLosses", 0)
            pts = t.get("points", 0)
            return f'{w}&ndash;{l}&ndash;{otl} &middot; {pts} pts'
    return ""


def page(briefing: TeamBriefing) -> str:
    cfg = briefing.config
    t = briefing.today
    colors = cfg["colors"]
    css = (ROOT / "style.css").read_text()

    # Inject team colors as CSS variable overrides.
    color_override = f"""
:root {{
  --team-primary: {colors['primary']};
  --team-primary-hi: {colors['primary_hi']};
  --team-accent: {colors['accent']};
  --team-accent-hi: {colors['accent_hi']};
}}
"""
    css = color_override + css

    headline_html, headline_tag = sections.headline.render(briefing)
    pregame_html, pregame_tag = sections.pregame.render(briefing)
    pulse_html = sections.pulse.render(briefing)
    slate_html = sections.slate.render(briefing)
    division_html = sections.division.render(briefing)

    # Numbering skips empty sections (pregame on off-days).
    _visible = [
        ("team", headline_html),
        ("pregame", pregame_html),
        ("pulse", pulse_html),
        ("slate", slate_html),
        ("div", division_html),
    ]
    _num = {}
    _n = 1
    for sid, html in _visible:
        if html:
            _num[sid] = f"{_n:02d}"
            _n += 1

    vol_no = (t - date(t.year, 1, 1)).days + 1
    filed = datetime.now(tz=ET).strftime("%m/%d/%y %H:%M ET")
    rec_str = _team_record_str(briefing)
    logo_url = f"https://assets.nhle.com/logos/nhl/svg/{briefing.abbr}_light.svg"
    idle_msg = cfg["branding"].get("idle_msg", "")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0d0f14">
<title>The Morning Faceoff &mdash; {fmt_date(t)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,800;0,900;1,700&family=Oswald:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body data-team="{briefing.slug}">

<header class="masthead">
  <div class="nav-btns">
    <a href="../" class="teams-btn" aria-label="All Teams" title="All Teams">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z"/></svg>
      <span>All Teams</span>
    </a>
  </div>
  <div class="kicker">
    <span>Vol. {t.year - 2025} &middot; <span class="vol">No. {vol_no:03d}</span></span>
    <span>{escape(cfg['branding']['tagline'])}</span>
    <span>Est. 2026</span>
  </div>
  <h1>
    <img src="{logo_url}" alt="{escape(briefing.full_name)}" class="mast-logo">
    <span class="mast-text"><span class="the">The</span><span class="lineup">Morning <em style="font-style:italic">Faceoff</em></span></span>
  </h1>
  <div class="dek">
    <span class="item"><span class="label">{t.strftime("%a")}</span><span class="val">{t.strftime("%b")} {t.day}, {t.year}</span></span>
    <span class="item"><span class="label">{escape(briefing.full_name)}</span><span class="rec">{rec_str}</span></span>
    <span class="item pill">Data: NHL Web API</span>
  </div>
</header>

<div class="wrap">
  <nav class="toc" aria-label="Sections">
    <div class="title">Sections</div>
    <ol>
      <li><a href="#team">The {escape(briefing.team_name)}</a></li>
      {'<li><a href="#pregame">Pre-Game</a></li>' if pregame_html else ''}
      <li><a href="#pulse">The Pulse</a></li>
      <li><a href="#slate">Tonight&rsquo;s Slate</a></li>
      <li><a href="#div">{escape(briefing.division)}</a></li>
    </ol>
  </nav>

  <main>
  <div id="live-game"></div>

  <section id="team" open>
    <summary>
      <span class="num">{_num.get("team", "")}</span>
      <span class="h">The {escape(briefing.team_name)}</span>
      <span class="tag">{escape(headline_tag)}</span>
      <span class="chev">&#9656;</span>
    </summary>
    {headline_html}
  </section>

  {f'''<section id="pregame" open>
    <summary>
      <span class="num">{_num.get("pregame", "")}</span>
      <span class="h">Pre-Game</span>
      <span class="tag">{escape(pregame_tag)}</span>
      <span class="chev">&#9656;</span>
    </summary>
    {pregame_html}
  </section>''' if pregame_html else ''}

  <section id="pulse" open>
    <summary>
      <span class="num">{_num.get("pulse", "")}</span>
      <span class="h">The Pulse</span>
      <span class="tag">Season Pulse</span>
      <span class="chev">&#9656;</span>
    </summary>
    {pulse_html}
  </section>

  <section id="slate" open>
    <summary>
      <span class="num">{_num.get("slate", "")}</span>
      <span class="h">Tonight&rsquo;s Slate</span>
      <span class="tag">{t.strftime("%a %b ")}{t.day}</span>
      <span class="chev">&#9656;</span>
    </summary>
    {slate_html}
  </section>

  <section id="div" open>
    <summary>
      <span class="num">{_num.get("div", "")}</span>
      <span class="h">{escape(briefing.division)}</span>
      <span class="tag">Standings &middot; Rivals</span>
      <span class="chev">&#9656;</span>
    </summary>
    {division_html}
  </section>

  </main>
</div>

<footer class="foot">
  <span>The Morning Faceoff &middot; <span class="flag">{escape(cfg['branding']['footer_tag'])}</span></span>
  <span>Data: NHL Web API (api-web.nhle.com)</span>
  <span>Filed {filed}</span>
</footer>

<script>
(function(){{
  var links = document.querySelectorAll('.toc a[href^="#"]');
  var sections = Array.from(links).map(function(a){{return {{link:a, el:document.querySelector(a.getAttribute('href'))}}}});
  function onScroll(){{
    var y = window.scrollY + 120;
    var current = sections[0];
    for (var i=0;i<sections.length;i++){{ if (sections[i].el && sections[i].el.offsetTop <= y) current = sections[i]; }}
    links.forEach(function(l){{l.classList.remove('active')}});
    if (current) current.link.classList.add('active');
  }}
  window.addEventListener('scroll', onScroll, {{passive:true}});
  onScroll();
}})();
</script>
<script>var TEAM_ABBR="{briefing.abbr}";var TEAM_IDLE_MSG="{escape(idle_msg)}";</script>
</body>
</html>"""


# ─── landing page ───────────────────────────────────────────────────────────
def build_landing(today: date) -> str:
    css = (ROOT / "style.css").read_text()
    cards = []
    for slug in all_team_slugs():
        cfg = load_team_config(slug)
        abbr = cfg["nhl_abbr"]
        logo = f"https://assets.nhle.com/logos/nhl/svg/{abbr}_light.svg"
        primary = cfg["colors"]["primary"]
        cards.append(f"""<a class="team-card" href="{slug}/" style="border-color:{primary}">
  <img src="{logo}" alt="{escape(cfg['name'])}">
  <span class="name">{escape(cfg['short_name'])}</span>
  <span class="city">{escape(cfg['name'].replace(cfg['short_name'], '').strip())}</span>
</a>""")

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Morning Faceoff &mdash; {fmt_date(today)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,800;0,900;1,700&family=Oswald:wght@400;600;700&family=Lora:wght@400;500&display=swap" rel="stylesheet">
<style>{css}
body {{ background: var(--ink); color: var(--paper); min-height:100vh; }}
.landing-mast {{ text-align:center; padding:60px 20px 40px; border-bottom:2px solid var(--gold); }}
.landing-mast h1 {{ font-family:'Playfair Display',serif; font-size:clamp(48px,8vw,96px); font-style:italic; font-weight:900; margin:0; color:var(--paper); }}
.landing-mast p {{ font-family:'Oswald',sans-serif; text-transform:uppercase; letter-spacing:0.2em; color:var(--gold); margin-top:12px; }}
.team-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:16px; max-width:1200px; margin:40px auto; padding:0 20px; }}
.team-card {{ display:flex; flex-direction:column; align-items:center; padding:20px 12px; background:var(--ink-2); border:2px solid var(--gold-dim); border-radius:8px; text-decoration:none; color:var(--paper); transition:transform .15s ease, border-color .15s ease; }}
.team-card:hover {{ transform:translateY(-4px); border-width:3px; }}
.team-card img {{ width:64px; height:64px; margin-bottom:12px; }}
.team-card .name {{ font-family:'Playfair Display',serif; font-weight:800; font-size:18px; }}
.team-card .city {{ font-family:'Oswald',sans-serif; text-transform:uppercase; font-size:11px; color:var(--paper-dim); letter-spacing:0.1em; margin-top:2px; }}
</style>
</head><body>
<header class="landing-mast">
  <h1>The Morning <em>Faceoff</em></h1>
  <p>A Daily NHL Broadsheet &middot; {fmt_date(today)}</p>
</header>
<div class="team-grid">
  {''.join(cards)}
</div>
</body></html>"""


# ─── main ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", help="slug to build (omit for all 32)")
    ap.add_argument("--landing", action="store_true", help="build landing page only")
    ap.add_argument("--date", help="override today (YYYY-MM-DD) for testing")
    args = ap.parse_args()

    today = date.fromisoformat(args.date) if args.date else datetime.now(tz=ET).date()

    if args.landing:
        html = build_landing(today)
        (ROOT / "index.html").write_text(html)
        print(f"landing → index.html ({len(html):,} bytes)")
        return

    slugs = [args.team] if args.team else all_team_slugs()
    for slug in slugs:
        briefing = build_briefing(slug, today)
        html = page(briefing)
        out_dir = ROOT / slug
        out_dir.mkdir(exist_ok=True)
        out_file = out_dir / "index.html"
        out_file.write_text(html)
        print(f"built → {slug}/index.html ({len(html):,} bytes)")


if __name__ == "__main__":
    main()

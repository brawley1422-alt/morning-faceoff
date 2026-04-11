"""{Division} — standings table + rival results from yesterday."""
from html import escape


def _render_standings(standings, division_name, my_abbr):
    div_teams = [t for t in standings if t.get("divisionName") == division_name]
    # Sort by divisionSequence if present, fallback to points
    div_teams.sort(key=lambda t: t.get("divisionSequence") or 99)

    rows = []
    for t in div_teams:
        ab = t.get("teamAbbrev", {}).get("default", "???")
        cls = ' class="my-team"' if ab == my_abbr else ""
        name = t.get("teamName", {}).get("default", ab)
        gp = t.get("gamesPlayed", 0)
        w = t.get("wins", 0)
        l = t.get("losses", 0)
        otl = t.get("otLosses", 0)
        pts = t.get("points", 0)
        pct = t.get("pointPctg", 0)
        l10 = f'{t.get("l10Wins",0)}-{t.get("l10Losses",0)}-{t.get("l10OtLosses",0)}'
        streak = f'{t.get("streakCode","")}{t.get("streakCount","")}' if t.get("streakCode") else "—"
        rows.append(
            f'<tr{cls}><td class="team">{escape(name)}</td>'
            f'<td class="num">{gp}</td><td class="num">{w}</td><td class="num">{l}</td>'
            f'<td class="num">{otl}</td><td class="num pct"><b>{pts}</b></td>'
            f'<td class="num">{pct:.3f}</td><td class="num">{l10}</td>'
            f'<td class="num">{streak}</td></tr>'
        )
    return f"""<div class="tblwrap"><table class="data standings">
<thead><tr><th>Team</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>PTS</th><th>P%</th><th>L10</th><th>Strk</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""


def _render_rivals(games_y, rivals_cfg, my_abbr):
    cards = []
    seen = set()
    for g in games_y:
        a_ab = g.get("awayTeam", {}).get("abbrev", "")
        h_ab = g.get("homeTeam", {}).get("abbrev", "")
        opp = None
        if a_ab in rivals_cfg and a_ab != my_abbr:
            opp = a_ab
        elif h_ab in rivals_cfg and h_ab != my_abbr:
            opp = h_ab
        if not opp or opp in seen:
            continue
        seen.add(opp)

        is_away = opp == a_ab
        opp_score = g.get("awayTeam" if is_away else "homeTeam", {}).get("score", 0)
        other_score = g.get("homeTeam" if is_away else "awayTeam", {}).get("score", 0)
        other_ab = h_ab if is_away else a_ab
        won = opp_score > other_score
        word = "W" if won else "L"
        loc = "at" if is_away else "vs"
        pd = (g.get("periodDescriptor") or {}).get("periodType", "")
        ot_tag = f" ({pd})" if pd in ("OT", "SO") else ""
        cards.append(f"""<div class="rival">
  <h4>{escape(rivals_cfg[opp])}</h4>
  <p class="score">{word} {opp_score}-{other_score} {loc} {escape(other_ab)}{ot_tag}</p>
</div>""")

    if not cards:
        cards.append('<div class="rival"><h4>Division Rivals</h4><p>All off yesterday.</p></div>')
    return f'<div class="rivals">{"".join(cards)}</div>'


def render(briefing):
    data = briefing.data
    standings = data.get("standings", {}).get("standings", [])
    games_y = data.get("games_yesterday", []) or []
    rivals = briefing.config.get("rivals", {})

    standings_html = _render_standings(standings, briefing.division, briefing.abbr)
    rivals_html = _render_rivals(games_y, rivals, briefing.abbr)

    return f"""<h3>{escape(briefing.division)} Standings</h3>
{standings_html}
<h3>Rivals &middot; Yesterday</h3>
{rivals_html}"""

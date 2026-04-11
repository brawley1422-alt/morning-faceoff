"""The {Team} — yesterday's result, line score, three stars, next games."""
from html import escape


def _period_line(t_side: dict, period_by_period: list) -> str:
    """Comma-joined period goals for a side (e.g., '1, 2, 0')."""
    # NHL landing endpoint puts period scores in linescore.byPeriod; fallback to total.
    return ""


def _result_word(us_score: int, them_score: int) -> str:
    if us_score > them_score:
        return "WIN"
    if us_score < them_score:
        return "LOSS"
    return "—"


def _fmt_next_game(g: dict, my_abbr: str) -> str:
    away = g.get("awayTeam", {}).get("abbrev", "???")
    home = g.get("homeTeam", {}).get("abbrev", "???")
    d = g.get("gameDate", "")
    try:
        from datetime import datetime
        ds = datetime.fromisoformat(d).strftime("%a %b ") + str(datetime.fromisoformat(d).day)
    except Exception:
        ds = d
    opp = away if home == my_abbr else home
    loc = "vs" if home == my_abbr else "at"
    return f'<span class="next-game"><span class="date">{ds}</span> <span class="loc">{loc}</span> <span class="opp">{opp}</span></span>'


def render(briefing):
    data = briefing.data
    abbr = briefing.abbr
    team_y = data.get("team_y")
    recap = data.get("recap") or {}

    # --- Masthead: yesterday's result ---
    result_block = ""
    summary_tag = "No game yesterday"

    if team_y and recap:
        away = recap.get("awayTeam", {})
        home = recap.get("homeTeam", {})
        a_ab = away.get("abbrev", "???")
        h_ab = home.get("abbrev", "???")
        a_score = away.get("score") or 0
        h_score = home.get("score") or 0
        is_home = h_ab == abbr
        us_score = h_score if is_home else a_score
        them_score = a_score if is_home else h_score
        opp_ab = a_ab if is_home else h_ab
        word = _result_word(us_score, them_score)
        state = recap.get("gameState", "")
        ot_note = ""
        pd = recap.get("periodDescriptor", {}) or {}
        if pd.get("periodType") == "OT":
            ot_note = " (OT)"
        elif pd.get("periodType") == "SO":
            ot_note = " (SO)"

        summary_tag = f"{word} {us_score}-{them_score} {'vs' if is_home else 'at'} {opp_ab}{ot_note}"

        # Three stars
        stars = (recap.get("summary") or {}).get("threeStars") or []
        star_html = ""
        if stars:
            cells = []
            for s in stars:
                name = f"{s.get('name',{}).get('default','')}"
                team = s.get("teamAbbrev", "")
                pos = s.get("position", "")
                # Stat line varies by position
                if pos == "G":
                    saves = s.get("saves")
                    shots = s.get("shotsAgainst")
                    sv = s.get("savePctg")
                    if saves is not None and shots is not None:
                        stat = f"{saves}/{shots} saves"
                    elif sv is not None:
                        stat = f"{float(sv):.3f} SV%"
                    else:
                        stat = "—"
                else:
                    g_ = s.get("goals", 0)
                    a_ = s.get("assists", 0)
                    p_ = s.get("points", g_ + a_)
                    stat = f"{g_}G {a_}A"
                star_num = s.get("star", "")
                cells.append(f"""<div class="star">
  <div class="rank">★ {star_num}</div>
  <div class="name">{escape(name)}</div>
  <div class="meta">{escape(team)} &middot; {escape(pos)}</div>
  <div class="stat">{escape(stat)}</div>
</div>""")
            star_html = f'<div class="three-stars">{"".join(cells)}</div>'

        # Scoring summary
        scoring = (recap.get("summary") or {}).get("scoring") or []
        goal_rows = []
        for period in scoring:
            pd_num = (period.get("periodDescriptor") or {}).get("number", "")
            for goal in period.get("goals", []):
                scorer = f"{goal.get('firstName',{}).get('default','')} {goal.get('lastName',{}).get('default','')}".strip()
                team = goal.get("teamAbbrev", {}).get("default", "")
                time = goal.get("timeInPeriod", "")
                strength = goal.get("strength", "EV")
                strength_tag = f' <span class="strength">{escape(strength)}</span>' if strength and strength != "ev" else ""
                goal_rows.append(
                    f'<tr><td class="per">P{pd_num}</td><td class="time">{escape(time)}</td>'
                    f'<td class="team">{escape(team)}</td><td class="scorer">{escape(scorer)}{strength_tag}</td></tr>'
                )
        goals_table = ""
        if goal_rows:
            goals_table = f"""<h4>Scoring</h4>
<div class="tblwrap"><table class="data scoring">
<thead><tr><th>Prd</th><th>Time</th><th>Team</th><th>Goal</th></tr></thead>
<tbody>{''.join(goal_rows)}</tbody></table></div>"""

        # Final score banner
        result_block = f"""<div class="hero-grid">
  <div class="final-banner">
    <div class="label">{'Home' if is_home else 'Road'} · Final{escape(ot_note)}</div>
    <div class="score">
      <span class="side {'win' if us_score>them_score else 'loss'}">{escape(briefing.team_name)} <b>{us_score}</b></span>
      <span class="sep">—</span>
      <span class="side">{escape(opp_ab)} <b>{them_score}</b></span>
    </div>
  </div>
  {star_html}
</div>
{goals_table}"""

    else:
        result_block = f'<p class="idle">{escape(briefing.team_name)} were off yesterday.</p>'

    # --- Next 3 games ---
    upcoming = data.get("club_week", {}).get("games", []) or []
    next_games = [g for g in upcoming if g.get("gameState") in ("FUT", "PRE")][:3]
    next_html = ""
    if next_games:
        cells = [_fmt_next_game(g, abbr) for g in next_games]
        next_html = f'<h4>Next Up</h4><div class="next-games">{"".join(cells)}</div>'

    inner = result_block + next_html
    return inner, summary_tag

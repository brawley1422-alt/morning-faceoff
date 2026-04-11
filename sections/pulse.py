"""The Pulse — season snapshot (record, PP%, PK%, GF/GA, streak)."""
from html import escape


def _stat_card(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="sub">{escape(sub)}</div>' if sub else ""
    return f"""<div class="stat-card">
  <div class="label">{escape(label)}</div>
  <div class="value">{value}</div>
  {sub_html}
</div>"""


def render(briefing):
    data = briefing.data
    abbr = briefing.abbr
    standings = data.get("standings", {}).get("standings", [])
    me = None
    div_teams = []
    for t in standings:
        if t.get("teamAbbrev", {}).get("default") == abbr:
            me = t
        if t.get("divisionName") == briefing.division:
            div_teams.append(t)
    if not me:
        return "<p>No season data available.</p>"

    w = me.get("wins", 0)
    l = me.get("losses", 0)
    otl = me.get("otLosses", 0)
    pts = me.get("points", 0)
    gp = me.get("gamesPlayed", 0)
    pct = me.get("pointPctg", 0)
    gf = me.get("goalFor", 0)
    ga = me.get("goalAgainst", 0)
    diff = gf - ga
    streak_code = me.get("streakCode", "")
    streak_count = me.get("streakCount", 0)
    div_seq = me.get("divisionSequence", 0)
    conf_seq = me.get("conferenceSequence", 0)
    l10_w = me.get("l10Wins", 0)
    l10_l = me.get("l10Losses", 0)
    l10_otl = me.get("l10OtLosses", 0)

    def _ord(n):
        if 10 <= n % 100 <= 20:
            suf = "th"
        else:
            suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suf}"

    cards = [
        _stat_card("Record", f"{w}–{l}–{otl}", f"{pts} points · {pct:.3f} pts%"),
        _stat_card("Standing", f"{_ord(div_seq)} {briefing.division}", f"{_ord(conf_seq)} {briefing.conference}"),
        _stat_card("Goal Diff", f"{'+' if diff >= 0 else ''}{diff}", f"{gf} GF · {ga} GA"),
        _stat_card("Last 10", f"{l10_w}–{l10_l}–{l10_otl}", f"Streak: {streak_code}{streak_count}" if streak_code else ""),
        _stat_card("Games Played", f"{gp}", f"{82 - gp} remaining"),
    ]

    return f'<div class="stat-grid">{"".join(cards)}</div>'

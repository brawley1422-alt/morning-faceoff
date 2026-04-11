"""The Race — NHL playoff chase.

Renders:
  1) A verdict card for this team (clinched / in / chasing / eliminated)
  2) Magic & tragic numbers
  3) The wild-card race mini-table for the relevant conference

NHL playoff format: top 3 in each division auto-qualify (6 teams), plus
2 wild cards per conference (4 teams) = 16 playoff teams. The wild card
race is sorted by conference points, excluding the division top-3s.
"""
from html import escape

REG_SEASON_GAMES = 82
CLINCH_STATUS = {"x": "Clinched playoff berth",
                 "y": "Clinched division",
                 "z": "Clinched conference",
                 "p": "Presidents' Trophy"}


def _max_possible(team: dict) -> int:
    """Highest points a team can still finish with."""
    gp = team.get("gamesPlayed", 0) or 0
    pts = team.get("points", 0) or 0
    remaining = REG_SEASON_GAMES - gp
    return pts + 2 * max(0, remaining)


def _games_left(team: dict) -> int:
    return REG_SEASON_GAMES - (team.get("gamesPlayed", 0) or 0)


def _verdict(me: dict, conf_sorted: list) -> tuple[str, str, str]:
    """Return (headline, kind, sub) where kind is one of
    clinched/in/chasing/eliminated.
    """
    ci = me.get("clinchIndicator", "")
    conf_seq = me.get("conferenceSequence", 99)

    if ci == "e":
        return ("Eliminated", "eliminated", "Will watch the postseason from home.")
    if ci in CLINCH_STATUS:
        return (CLINCH_STATUS[ci], "clinched", "Locked in.")

    # Not clinched, not eliminated — live race
    # First team out of playoffs = conference seq 9
    first_out = conf_sorted[8] if len(conf_sorted) > 8 else None
    last_in = conf_sorted[7] if len(conf_sorted) > 7 else None
    my_pts = me.get("points", 0) or 0

    if conf_seq <= 8:
        cushion = my_pts - (first_out.get("points", 0) if first_out else 0)
        return (
            "Inside the Field",
            "in",
            f"{cushion:+d} pt cushion on {first_out.get('teamAbbrev',{}).get('default','')}"
            if first_out else "Held a playoff seat.",
        )
    else:
        deficit = (last_in.get("points", 0) if last_in else 0) - my_pts
        last_in_ab = last_in.get("teamAbbrev", {}).get("default", "") if last_in else ""
        return (
            "Chasing",
            "chasing",
            f"{deficit} pts back of {last_in_ab} for the final wild card",
        )


def _numbers(me: dict, conf_sorted: list) -> tuple[str, str, str, str]:
    """Return (first_label, first_value, tragic_label, tragic_value).

    For in-field teams (conf_seq <= 8) the first number is the classic
    Magic Number. For chasing teams the first number is Points Back —
    the raw deficit to the last wild-card slot.
    """
    my_pts = me.get("points", 0) or 0
    my_max = _max_possible(me)
    conf_seq = me.get("conferenceSequence", 99)
    ci = me.get("clinchIndicator", "")

    # The team whose position we reference is different depending on whether
    # we are in or out of the field.
    #   in-field   →  "first out" is conf_sorted[8] (9th team)
    #   chasing    →  "last in"  is conf_sorted[7] (8th team) — who we chase
    first_out = conf_sorted[8] if len(conf_sorted) > 8 else None
    last_in = conf_sorted[7] if len(conf_sorted) > 7 else None

    if conf_seq <= 8 and first_out:
        # Magic number: out_max + 1 - my_pts (clipped to 0)
        out_max = _max_possible(first_out)
        magic = max(0, out_max + 1 - my_pts)
        if ci in CLINCH_STATUS:
            first_label, first_value = "Magic Number", "0 — clinched"
        elif magic == 0:
            first_label, first_value = "Magic Number", "0 — in"
        else:
            first_label, first_value = "Magic Number", f"{magic} pt{'s' if magic != 1 else ''}"
    elif last_in:
        back = (last_in.get("points", 0) or 0) - my_pts
        last_in_ab = last_in.get("teamAbbrev", {}).get("default", "")
        first_label = "Points Back"
        first_value = f"{back} pt{'s' if back != 1 else ''}"
    else:
        first_label, first_value = "—", "—"

    # Tragic number: how many points the 8th team needs for me to be
    # mathematically unable to catch their CURRENT total. For in-field
    # teams we measure against the 9th-place team's max instead, so the
    # number is always framed as "points needed to push me out."
    if conf_seq <= 8 and first_out:
        # In-field: tragic = how many MORE points first_out needs so that
        # their max exceeds my max. Usually moot when comfortably in.
        out_max = _max_possible(first_out)
        tragic = max(0, my_max + 1 - out_max)
        tragic_label = "Tragic Number"
    elif last_in:
        tragic = max(0, my_max + 1 - (last_in.get("points", 0) or 0))
        tragic_label = "Tragic Number"
    else:
        tragic = 0
        tragic_label = "—"

    if ci == "e":
        tragic_value = "0 — eliminated"
    elif tragic == 0 and conf_seq > 8:
        tragic_value = "0 — gone"
    else:
        tragic_value = f"{tragic} pt{'s' if tragic != 1 else ''}"

    return first_label, first_value, tragic_label, tragic_value


def _race_table(conf_sorted: list, my_abbr: str) -> str:
    """Render rows for conf seqs 6–11: last auto slot through first 3 out.

    Highlights the current team, visually separates the playoff cutoff line
    (between seqs 8 and 9), and calls out wild-card slots.
    """
    rows = []
    for i, t in enumerate(conf_sorted[:11]):
        if i < 5:
            continue  # show seqs 6..11 (indices 5..10)
        ab = t.get("teamAbbrev", {}).get("default", "???")
        name = t.get("teamName", {}).get("default", ab)
        pts = t.get("points", 0)
        gp = t.get("gamesPlayed", 0)
        gl = REG_SEASON_GAMES - gp
        div_seq = t.get("divisionSequence", 0)
        ci = t.get("clinchIndicator", "")
        if div_seq <= 3:
            slot = f"{t.get('divisionName','')[:3].upper()} #{div_seq}"
        else:
            wc = t.get("wildcardSequence", 0)
            if wc == 1: slot = "WC1"
            elif wc == 2: slot = "WC2"
            else: slot = f"Out +{wc-2}"
        badge = ""
        if ci in ("x", "y", "z", "p"): badge = ' <span class="badge clinch">✓</span>'
        elif ci == "e": badge = ' <span class="badge out">✕</span>'
        cls = []
        if ab == my_abbr: cls.append("my-team")
        if i == 8: cls.append("cutline")  # first row out of playoffs
        cls_attr = f' class="{" ".join(cls)}"' if cls else ""
        rows.append(
            f'<tr{cls_attr}>'
            f'<td class="slot">{slot}</td>'
            f'<td class="team">{escape(name)}{badge}</td>'
            f'<td class="num"><b>{pts}</b></td>'
            f'<td class="num">{gp}</td>'
            f'<td class="num">{gl}</td>'
            f'</tr>'
        )
    return f"""<div class="tblwrap"><table class="data race">
<thead><tr><th>Slot</th><th>Team</th><th>PTS</th><th>GP</th><th>GL</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""


def render(briefing):
    data = briefing.data
    standings = data.get("standings", {}).get("standings", [])
    if not standings:
        return "", ""

    # Separate the team's conference and sort by conferenceSequence
    my_conf = briefing.conference
    conf_sorted = sorted(
        [t for t in standings if t.get("conferenceName") == my_conf],
        key=lambda t: t.get("conferenceSequence", 99),
    )
    me = next((t for t in conf_sorted if t.get("teamAbbrev", {}).get("default") == briefing.abbr), None)
    if not me:
        return "", ""

    headline, kind, sub = _verdict(me, conf_sorted)
    first_label, first_value, tragic_label, tragic_value = _numbers(me, conf_sorted)
    games_left = _games_left(me)

    verdict_html = f"""<div class="race-verdict race-{kind}">
  <div class="verdict-label">The Race</div>
  <div class="verdict-headline">{escape(headline)}</div>
  <div class="verdict-sub">{escape(sub)}</div>
</div>"""

    first_sub = "to clinch" if first_label == "Magic Number" else "behind last wild-card"
    numbers_html = f"""<div class="race-numbers">
  <div class="num-card">
    <div class="label">{escape(first_label)}</div>
    <div class="value">{escape(first_value)}</div>
    <div class="sub">{escape(first_sub)}</div>
  </div>
  <div class="num-card">
    <div class="label">{escape(tragic_label)}</div>
    <div class="value">{escape(tragic_value)}</div>
    <div class="sub">to be eliminated</div>
  </div>
  <div class="num-card">
    <div class="label">Games Left</div>
    <div class="value">{games_left}</div>
    <div class="sub">max {_max_possible(me)} pts</div>
  </div>
</div>"""

    race_html = _race_table(conf_sorted, briefing.abbr)

    inner = f"""{verdict_html}
{numbers_html}
<h4>{escape(my_conf)} Wild-Card Race</h4>
{race_html}
<p class="race-note">Top 3 in each division auto-qualify. The next two teams per conference fill the wild cards. The red line is the playoff cutoff.</p>"""

    tag = headline
    return inner, tag

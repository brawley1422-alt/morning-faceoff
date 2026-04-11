"""Pre-Game — tonight's matchup head-to-head. Renders only on game nights."""
from html import escape
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/Detroit")
except (ImportError, KeyError):
    from datetime import timedelta
    _ET = timezone(timedelta(hours=-4))


def _fmt_time_et(iso_z: str) -> str:
    try:
        gd = datetime.strptime(iso_z, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        et = gd.astimezone(_ET)
        return et.strftime("%-I:%M %p ET")
    except Exception:
        return ""


def _find_team(standings: list, abbr: str) -> dict:
    for t in standings:
        if t.get("teamAbbrev", {}).get("default") == abbr:
            return t
    return {}


def _stat_row(label: str, my_val, opp_val, higher_better: bool = True) -> str:
    def _fmt(v):
        if v is None:
            return "—"
        if isinstance(v, float):
            return f"{v:.3f}" if abs(v) < 1 else f"{v:.2f}"
        return str(v)
    my_cls, opp_cls = "", ""
    try:
        mv, ov = float(my_val), float(opp_val)
        if (mv > ov) == higher_better:
            my_cls = ' class="lead"'
        elif (mv < ov) == higher_better:
            opp_cls = ' class="lead"'
    except (TypeError, ValueError):
        pass
    return (
        f'<tr><td{my_cls}>{_fmt(my_val)}</td>'
        f'<td class="stat-label">{escape(label)}</td>'
        f'<td{opp_cls}>{_fmt(opp_val)}</td></tr>'
    )


def render(briefing):
    data = briefing.data
    team_t = data.get("team_t")
    matchup = data.get("matchup") or {}
    if not team_t:
        return "", ""

    abbr = briefing.abbr
    away = matchup.get("awayTeam") or team_t.get("awayTeam", {})
    home = matchup.get("homeTeam") or team_t.get("homeTeam", {})
    is_home = home.get("abbrev") == abbr
    opp = away if is_home else home
    opp_ab = opp.get("abbrev", "???")
    place = (opp.get("placeName") or {}).get("default", "")
    common = (opp.get("commonName") or {}).get("default", "")
    opp_name = f"{place} {common}".strip() or opp_ab

    venue = matchup.get("venue", {}).get("default", "") if isinstance(matchup.get("venue"), dict) else ""
    time_str = _fmt_time_et(matchup.get("startTimeUTC") or team_t.get("startTimeUTC", ""))
    bc = matchup.get("tvBroadcasts") or team_t.get("tvBroadcasts") or []
    bc_str = " · ".join(b.get("network", "") for b in bc if b.get("network"))
    summary_tag = f"{'vs' if is_home else 'at'} {opp_ab} · {time_str}"

    # Head-to-head from standings
    standings = data.get("standings", {}).get("standings", [])
    me = _find_team(standings, abbr)
    opp = _find_team(standings, opp_ab)

    rows_html = ""
    if me and opp:
        def _rec(t):
            return f'{t.get("wins",0)}-{t.get("losses",0)}-{t.get("otLosses",0)}'
        def _gdiff(t):
            return (t.get("goalFor", 0) or 0) - (t.get("goalAgainst", 0) or 0)
        def _gfg(t):
            gp = t.get("gamesPlayed") or 1
            return (t.get("goalFor", 0) or 0) / gp
        def _gag(t):
            gp = t.get("gamesPlayed") or 1
            return (t.get("goalAgainst", 0) or 0) / gp

        rows = [
            ("Record", _rec(me), _rec(opp), False),
            ("Points", me.get("points", 0), opp.get("points", 0), True),
            ("Points %", me.get("pointPctg", 0), opp.get("pointPctg", 0), True),
            ("GF / GP", _gfg(me), _gfg(opp), True),
            ("GA / GP", _gag(me), _gag(opp), False),
            ("Goal Differential", f"{'+' if _gdiff(me)>=0 else ''}{_gdiff(me)}",
                                  f"{'+' if _gdiff(opp)>=0 else ''}{_gdiff(opp)}", True),
            ("Home Record", f'{me.get("homeWins",0)}-{me.get("homeLosses",0)}-{me.get("homeOtLosses",0)}',
                            f'{opp.get("homeWins",0)}-{opp.get("homeLosses",0)}-{opp.get("homeOtLosses",0)}', False),
            ("Road Record", f'{me.get("roadWins",0)}-{me.get("roadLosses",0)}-{me.get("roadOtLosses",0)}',
                            f'{opp.get("roadWins",0)}-{opp.get("roadLosses",0)}-{opp.get("roadOtLosses",0)}', False),
            ("Last 10", f'{me.get("l10Wins",0)}-{me.get("l10Losses",0)}-{me.get("l10OtLosses",0)}',
                        f'{opp.get("l10Wins",0)}-{opp.get("l10Losses",0)}-{opp.get("l10OtLosses",0)}', False),
        ]
        body = "".join(_stat_row(lbl, mv, ov, hb) for lbl, mv, ov, hb in rows)
        rows_html = f"""<div class="tblwrap"><table class="data matchup">
<thead><tr><th>{escape(briefing.team_name)}</th><th>Stat</th><th>{escape(opp_ab)}</th></tr></thead>
<tbody>{body}</tbody></table></div>"""

    header = f"""<div class="pregame-head">
  <div class="matchup-top">{escape(briefing.team_name)} {('vs' if is_home else 'at')} {escape(opp_name)}</div>
  <div class="matchup-meta">{escape(time_str)}{(' &middot; ' + escape(venue)) if venue else ''}{(' &middot; ' + escape(bc_str)) if bc_str else ''}</div>
</div>"""

    return header + rows_html, summary_tag

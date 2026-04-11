"""Tonight's Slate — every NHL game on today's schedule."""
from html import escape
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/Detroit")
except (ImportError, KeyError):
    from datetime import timedelta
    _ET = timezone(timedelta(hours=-4))


def _fmt_time(iso_z: str) -> str:
    try:
        gd = datetime.strptime(iso_z, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return gd.astimezone(_ET).strftime("%-I:%M").lstrip("0") + " ET"
    except Exception:
        return ""


def render(briefing):
    games = briefing.data.get("games_today") or []
    if not games:
        return '<p class="idle">No games on the NHL slate tonight.</p>'

    cards = []
    for g in games:
        a = g.get("awayTeam", {})
        h = g.get("homeTeam", {})
        a_ab = a.get("abbrev", "???")
        h_ab = h.get("abbrev", "???")
        state = g.get("gameState", "")
        # Score if in progress / final, time if scheduled
        if state in ("OFF", "FINAL", "LIVE", "CRIT"):
            a_sc = a.get("score", 0)
            h_sc = h.get("score", 0)
            label = "FINAL" if state in ("OFF", "FINAL") else "LIVE"
            score_line = f'<div class="score">{escape(str(a_sc))} – {escape(str(h_sc))}</div>'
            meta = f'<div class="state">{label}</div>'
        else:
            score_line = ""
            meta = f'<div class="time">{_fmt_time(g.get("startTimeUTC", ""))}</div>'

        bc_parts = [escape(b.get("network", "")) for b in g.get("tvBroadcasts", []) if b.get("network")]
        bc_str = f'<div class="bc">{" · ".join(bc_parts[:3])}</div>' if bc_parts else ""

        highlight = ' highlight' if briefing.abbr in (a_ab, h_ab) else ''
        cards.append(f"""<div class="g{highlight}" data-gpk="{g.get('id','')}">
  <div class="matchup">{escape(a_ab)} @ {escape(h_ab)}</div>
  {score_line}
  {meta}
  {bc_str}
</div>""")

    return f'<div class="slate">{"".join(cards)}</div>'

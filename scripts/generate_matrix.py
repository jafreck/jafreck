#!/usr/bin/env python3
"""Generate a Matrix-rain SVG with live GitHub stats baked in."""

import json, os, random, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ───────────────────────────────────────────────────
USERNAME = "jafreck"
OUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "matrix-stats.svg"

W = 850
NUM_COLS = 45
COL_W = W / NUM_COLS
FS = 14
CH = FS + 2
PANEL_W = 620
PX = (W - PANEL_W) / 2
PANEL_RX = 12
CHARS = list(
    "アイウエオカキクケコサシスセソタチツテト"
    "ナニヌネノハヒフヘホマミムメモヤユヨ"
    "ラリルレロワヲン0123456789"
)
random.seed(42)

TOKEN = os.environ.get("GITHUB_TOKEN", "")


# ── GitHub API ──────────────────────────────────────────────────────
def gql(query, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "matrix-stats",
        },
    )
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read())
    if "errors" in resp:
        raise RuntimeError(resp["errors"])
    return resp["data"]


def fetch_streak():
    d = gql(
        """query($u:String!){user(login:$u){contributionsCollection{
        contributionCalendar{totalContributions
        weeks{contributionDays{contributionCount date}}}}}}""",
        u=USERNAME,
    )
    cal = d["user"]["contributionsCollection"]["contributionCalendar"]
    days = sorted(
        (day for w in cal["weeks"] for day in w["contributionDays"]),
        key=lambda x: x["date"],
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cur = 0
    for day in reversed(days):
        if day["date"] > today:
            continue
        if day["contributionCount"]:
            cur += 1
        else:
            break

    longest = streak = 0
    for day in days:
        if day["contributionCount"]:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0

    return dict(total=cal["totalContributions"], current=cur, longest=longest)


def fetch_langs():
    langs, colors, cursor = {}, {}, None
    while True:
        d = gql(
            """query($u:String!,$c:String){user(login:$u){
            repositories(first:100,ownerAffiliations:OWNER,after:$c,isFork:false){
            nodes{languages(first:10,orderBy:{field:SIZE,direction:DESC}){
            edges{size node{name color}}}}
            pageInfo{hasNextPage endCursor}}}}""",
            u=USERNAME,
            c=cursor,
        )
        repos = d["user"]["repositories"]
        for repo in repos["nodes"]:
            for e in repo["languages"]["edges"]:
                n = e["node"]["name"]
                langs[n] = langs.get(n, 0) + e["size"]
                if e["node"]["color"]:
                    colors[n] = e["node"]["color"]
        if repos["pageInfo"]["hasNextPage"]:
            cursor = repos["pageInfo"]["endCursor"]
        else:
            break

    top = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:8]
    total = sum(v for _, v in top)
    return [
        dict(name=n, pct=round(v / total * 100, 1), color=colors.get(n, "#858585"))
        for n, v in top
    ]


# ── SVG helpers ─────────────────────────────────────────────────────
def esc(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&apos;")
    )


CSS = """
    .bg{fill:#0D1117}
    .fs1{stop-color:#0D1117;stop-opacity:0}
    .fs2{stop-color:#0D1117;stop-opacity:1}
    .ch{fill:#00FF41;font-family:monospace;font-size:14px}
    .cd{opacity:.35} .cm{opacity:.6} .cb{opacity:.9}
    .cl{opacity:1;fill:#AFFFAF}
    .pb{fill:#0D1117;fill-opacity:.82}
    .ps{stroke:#30363D;stroke-width:1;fill:none}
    .tt{fill:#C9D1D9;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;font-weight:600}
    .ts{fill:#8B949E;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
    .tn{fill:#58A6FF;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;font-weight:600}
    .tl{fill:#C9D1D9;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
    .tp{fill:#8B949E;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;font-size:12px}
    .div{stroke:#30363D;stroke-width:1}
    .bar-bg{fill:#30363D;opacity:0.3}

    @media(prefers-color-scheme:light){
      .bg{fill:#FFF} .fs1{stop-color:#FFF;stop-opacity:0} .fs2{stop-color:#FFF;stop-opacity:1}
      .ch{fill:#0969DA} .cd{opacity:.15} .cm{opacity:.28} .cb{opacity:.45}
      .cl{opacity:.7;fill:#0550AE}
      .pb{fill:#FFF;fill-opacity:.88} .ps{stroke:#D0D7DE}
      .tt{fill:#1F2328} .ts{fill:#57606A} .tn{fill:#0969DA}
      .tl{fill:#1F2328} .tp{fill:#57606A} .div{stroke:#D0D7DE}
      .bar-bg{fill:#D0D7DE;opacity:0.4}
    }
"""


def build_svg(streak, langs):
    n_langs = len(langs)

    # Layout
    greeting_y, greeting_h = 25, 55
    streak_y = greeting_y + greeting_h + 20
    streak_h = 120
    lang_row_h = 24
    lang_h = 30 + n_langs * lang_row_h + 30
    lang_y = streak_y + streak_h + 20
    H = lang_y + lang_h + 25

    # Rain columns
    cols = []
    anim_map = {}
    for i in range(NUM_COLS):
        x = round(i * COL_W + COL_W / 2, 1)
        n = random.randint(10, 22)
        chars = [random.choice(CHARS) for _ in range(n)]
        dur = round(random.uniform(4, 10), 1)
        delay = round(random.uniform(0, 8), 1)
        total_h = n * CH
        key = (dur, total_h)
        if key not in anim_map:
            anim_map[key] = f"r{len(anim_map)}"
        cols.append(
            dict(
                x=x,
                chars=chars,
                dur=dur,
                delay=delay,
                n=n,
                total_h=total_h,
                cls=anim_map[key],
            )
        )

    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%">')
    o.append("<defs><style>")
    o.append(CSS)
    for (dur, th), name in anim_map.items():
        o.append(
            f"@keyframes {name}{{0%{{transform:translateY(-{th}px)}}"
            f"100%{{transform:translateY({H + 20}px)}}}}"
        )
    o.append("</style>")
    o.append(
        '<linearGradient id="f" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" class="fs1"/><stop offset="75%" class="fs1"/>'
        '<stop offset="100%" class="fs2"/></linearGradient>'
    )
    o.append(f'<clipPath id="c"><rect width="{W}" height="{H}" rx="6"/></clipPath>')
    o.append("</defs>")

    # Background
    o.append(f'<rect class="bg" width="{W}" height="{H}" rx="6"/>')

    # Rain
    o.append('<g clip-path="url(#c)">')
    for c in cols:
        o.append(f'<g style="animation:{c["cls"]} {c["dur"]}s linear {c["delay"]}s infinite">')
        for j, ch in enumerate(c["chars"]):
            y = round(j * CH, 1)
            bc = (
                "cl"
                if j == c["n"] - 1
                else "cb"
                if j >= c["n"] - 3
                else "cm"
                if j >= c["n"] - 6
                else "cd"
            )
            o.append(f'<text class="ch {bc}" x="{c["x"]}" y="{y}">{ch}</text>')
        o.append("</g>")
    o.append("</g>")

    # Fade
    o.append(f'<rect width="{W}" height="{H}" fill="url(#f)" rx="6"/>')

    cx = W / 2

    # ── Greeting ──
    _panel(o, greeting_y, greeting_h)
    o.append(
        f'<text class="tt" x="{cx}" y="{greeting_y + 35}" '
        f'text-anchor="middle" font-size="20">Hi there 👋</text>'
    )

    # ── Streak ──
    _panel(o, streak_y, streak_h)
    col_w = PANEL_W / 3
    centers = [PX + col_w * i + col_w / 2 for i in range(3)]
    o.append(
        f'<line class="div" x1="{PX + col_w}" y1="{streak_y + 15}" '
        f'x2="{PX + col_w}" y2="{streak_y + streak_h - 15}"/>'
    )
    o.append(
        f'<line class="div" x1="{PX + col_w * 2}" y1="{streak_y + 15}" '
        f'x2="{PX + col_w * 2}" y2="{streak_y + streak_h - 15}"/>'
    )
    for i, (val, label, emoji) in enumerate(
        [
            (streak["current"], "Current Streak", "🔥"),
            (streak["total"], "Total Contributions", "⭐"),
            (streak["longest"], "Longest Streak", "🏆"),
        ]
    ):
        x = centers[i]
        o.append(
            f'<text class="tn" x="{x}" y="{streak_y + 50}" '
            f'text-anchor="middle" font-size="28">{val}</text>'
        )
        o.append(
            f'<text class="ts" x="{x}" y="{streak_y + 72}" '
            f'text-anchor="middle" font-size="12">{label}</text>'
        )
        o.append(
            f'<text x="{x}" y="{streak_y + 95}" '
            f'text-anchor="middle" font-size="16">{emoji}</text>'
        )

    # ── Languages ──
    _panel(o, lang_y, lang_h)
    o.append(
        f'<text class="tt" x="{PX + 20}" y="{lang_y + 25}" '
        f'font-size="14">Most Used Languages</text>'
    )
    name_w, pct_w = 100, 50
    bar_x = PX + 20 + name_w
    bar_w = PANEL_W - 40 - name_w - pct_w
    for i, lang in enumerate(langs):
        ry = lang_y + 45 + i * lang_row_h
        o.append(
            f'<text class="tl" x="{PX + 20}" y="{ry + 14}" '
            f'font-size="12">{esc(lang["name"])}</text>'
        )
        o.append(
            f'<rect class="bar-bg" x="{bar_x}" y="{ry + 3}" '
            f'width="{bar_w}" height="12" rx="3"/>'
        )
        fw = round(bar_w * lang["pct"] / 100, 1)
        o.append(
            f'<rect x="{bar_x}" y="{ry + 3}" width="{fw}" '
            f'height="12" rx="3" fill="{lang["color"]}"/>'
        )
        o.append(
            f'<text class="tp" x="{bar_x + bar_w + 8}" '
            f'y="{ry + 14}">{lang["pct"]}%</text>'
        )

    o.append("</svg>")
    return "\n".join(o)


def _panel(o, y, h):
    o.append(f'<rect class="pb" x="{PX}" y="{y}" width="{PANEL_W}" height="{h}" rx="{PANEL_RX}"/>')
    o.append(f'<rect class="ps" x="{PX}" y="{y}" width="{PANEL_W}" height="{h}" rx="{PANEL_RX}"/>')


# ── Main ────────────────────────────────────────────────────────────
def main():
    try:
        streak = fetch_streak()
        print(f"Streak: current={streak['current']}, total={streak['total']}, longest={streak['longest']}")
    except Exception as e:
        print(f"⚠ Failed to fetch streak: {e}", file=sys.stderr)
        streak = dict(total=0, current=0, longest=0)

    try:
        langs = fetch_langs()
        print(f"Languages: {', '.join(l['name'] for l in langs)}")
    except Exception as e:
        print(f"⚠ Failed to fetch languages: {e}", file=sys.stderr)
        langs = [dict(name="N/A", pct=100, color="#858585")]

    svg = build_svg(streak, langs)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(svg)
    print(f"✓ Wrote {OUT_PATH} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()

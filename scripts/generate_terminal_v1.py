#!/usr/bin/env python3
"""Generate an Amber CRT Monitor themed SVG with GitHub stats.

IBM 5151–style amber phosphor on black, heavier CRT curvature, scrolling
scanline bar, boot-sequence preamble, ASCII "Hi there" header, and slower
character-by-character typing animation.  CSS keyframes only.
"""

import json, math, os, random, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ───────────────────────────────────────────────────
USERNAME = "jafreck"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

W = 850


# ── GitHub API ──────────────────────────────────────────────────────

def gql(query, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "terminal-stats",
        },
    )
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read())
    if "errors" in resp:
        raise RuntimeError(resp["errors"])
    return resp["data"]


def fetch_streak():
    d = gql(
        """query($u:String!){user(login:$u){
        createdAt
        contributionsCollection{
          contributionYears
          contributionCalendar{totalContributions
          weeks{contributionDays{contributionCount date}}}}}}""",
        u=USERNAME,
    )
    created_at = d["user"]["createdAt"][:10]
    years = d["user"]["contributionsCollection"]["contributionYears"]
    cal = d["user"]["contributionsCollection"]["contributionCalendar"]
    days = sorted(
        (day for w in cal["weeks"] for day in w["contributionDays"]),
        key=lambda x: x["date"],
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    valid = [d for d in days if d["date"] <= today]

    if len(years) > 1:
        aliases = " ".join(
            f'y{yr}:contributionsCollection(from:"{yr}-01-01T00:00:00Z",'
            f'to:"{yr}-12-31T23:59:59Z")'
            f"{{contributionCalendar{{totalContributions}}}}"
            for yr in years
        )
        d2 = gql(f"query($u:String!){{user(login:$u){{{aliases}}}}}", u=USERNAME)
        all_total = sum(
            d2["user"][f"y{yr}"]["contributionCalendar"]["totalContributions"]
            for yr in years
        )
    else:
        all_total = cal["totalContributions"]

    if valid and valid[-1]["date"] == today and not valid[-1]["contributionCount"]:
        valid = valid[:-1]

    cur = 0
    cur_start = cur_end = None
    for day in reversed(valid):
        if day["contributionCount"]:
            if cur == 0:
                cur_end = day["date"]
            cur_start = day["date"]
            cur += 1
        else:
            break

    longest = run = 0
    longest_start = longest_end = None
    run_start = None
    for day in valid:
        if day["contributionCount"]:
            if run == 0:
                run_start = day["date"]
            run += 1
            if run > longest:
                longest = run
                longest_start = run_start
                longest_end = day["date"]
        else:
            run = 0

    total_start = created_at
    total_end = today

    return dict(
        total=all_total,
        total_start=total_start,
        total_end=total_end,
        current=cur,
        current_start=cur_start,
        current_end=cur_end,
        longest=longest,
        longest_start=longest_start,
        longest_end=longest_end,
    )


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


def fmt_range(start, end):
    if not start or not end:
        return ""
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    if s.year == e.year:
        return f"{s.strftime('%b %d')} - {e.strftime('%b %d')}"
    return f"{s.strftime('%b %d, %Y')} - {e.strftime('%b %d, %Y')}"


# ── Themes ──────────────────────────────────────────────────────────
THEMES = {
    "dark": dict(
        bg="#0a0800",
        fg="#FFB000",
        fg_dim="#805800",
        fg_bright="#FFD060",
        prompt="#FFB000",
        cursor="#FFB000",
        label="#CC8C00",
        value="#FFB000",
        bar_fill="#FFB000",
        bar_empty="#3a2800",
        header="#FFB000",
        border="#664400",
        scanline_opacity="0.10",
        glow_color="rgba(255,176,0,0.12)",
        glow_strong="rgba(255,176,0,0.35)",
        bezel="#1a1200",
        bezel_highlight="#332600",
        lang_color_opacity="0.95",
        vignette_opacity="0.50",
        boot_fg="#CC8C00",
        boot_ok="#FFB000",
    ),
    "light": dict(
        bg="#f5f0e0",
        fg="#5a3a00",
        fg_dim="#8a7a5a",
        fg_bright="#3a2200",
        prompt="#5a3a00",
        cursor="#5a3a00",
        label="#7a5a1a",
        value="#5a3a00",
        bar_fill="#8a6a1a",
        bar_empty="#ddd5c0",
        header="#5a3a00",
        border="#b0a080",
        scanline_opacity="0.05",
        glow_color="rgba(90,58,0,0.05)",
        glow_strong="rgba(90,58,0,0.12)",
        bezel="#d0c8b0",
        bezel_highlight="#e0d8c0",
        lang_color_opacity="0.90",
        vignette_opacity="0.15",
        boot_fg="#8a7a5a",
        boot_ok="#5a3a00",
    ),
}

FONT = "'Courier New', 'Consolas', 'Liberation Mono', monospace"
CHAR_W = 8.4  # monospace char width at 14px (Courier New)
LINE_H = 22
MARGIN_X = 30
MARGIN_Y = 28


# ── SVG builder ─────────────────────────────────────────────────────
def _make_bar(pct, bar_len=20):
    """Return a text progress bar: filled = █, empty = ░."""
    filled = round(pct / 100 * bar_len)
    return "\u2588" * filled + "\u2591" * (bar_len - filled)


HI_THERE_TEXT = "Hi there \U0001f44b"


def build_svg(streak, langs, theme="dark"):
    t = THEMES[theme]

    # ── Build terminal lines ──
    lines = []

    # Boot sequence preamble
    lines.append(("boot", "BIOS v2.4.1 ............... OK"))
    lines.append(("boot", "Memory test: 640K ......... OK"))
    lines.append(("boot", "Loading GitHub API ........ OK"))
    lines.append(("blank", ""))

    # Greeting line (rendered larger)
    lines.append(("greeting", HI_THERE_TEXT))
    lines.append(("blank", ""))
    lines.append(("blank", ""))

    lines.append(("prompt", f"~/github/{USERNAME} $ system_info --user {USERNAME}"))
    lines.append(("blank", ""))
    box_w = 48
    lines.append(("header", "+" + "-" * box_w + "+"))
    lines.append(("header", "|" + "G I T H U B   S Y S T E M   I N F O".center(box_w) + "|"))
    lines.append(("header", "+" + "-" * box_w + "+"))
    lines.append(("blank", ""))

    cur_range = fmt_range(streak.get("current_start"), streak.get("current_end"))
    total_range = fmt_range(streak.get("total_start"), streak.get("total_end"))
    longest_range = fmt_range(streak.get("longest_start"), streak.get("longest_end"))

    lines.append(("stat", f"  CURRENT STREAK ... {streak['current']:>5} days   ({esc(cur_range)})"))
    lines.append(("stat", f"  LONGEST STREAK ... {streak['longest']:>5} days   ({esc(longest_range)})"))
    lines.append(("stat", f"  TOTAL COMMITS .... {streak['total']:>5}         ({esc(total_range)})"))
    lines.append(("blank", ""))
    lines.append(("divider", "  " + "\u2500" * 60))
    lines.append(("blank", ""))
    lines.append(("prompt", f"~/github/{USERNAME} $ lang_stats --top {len(langs)}"))
    lines.append(("blank", ""))

    max_name = max((len(l["name"]) for l in langs), default=10)
    for lang in langs:
        padded = lang["name"].ljust(max_name)
        bar = _make_bar(lang["pct"])
        lines.append(("lang", f"  {padded}  {bar}  {lang['pct']:>5.1f}%", lang.get("color", t["fg"])))

    lines.append(("blank", ""))
    lines.append(("divider", "  " + "\u2500" * 60))
    lines.append(("blank", ""))
    lines.append(("cursor_prompt", f"~/github/{USERNAME} $ "))

    # ── Layout calculations ──
    n_lines = len(lines)
    H = MARGIN_Y * 2 + n_lines * LINE_H + 20

    o = []

    # ── SVG root ──
    o.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="100%" viewBox="0 0 {W} {H}" '
        f'font-family="{FONT}">'
    )

    # ── Defs ──
    type_delay_per_line = 0.12
    char_type_speed = 0.008
    total_anim_time = n_lines * type_delay_per_line + 5

    o.append("<defs>")

    # Scanline pattern
    o.append(
        '<pattern id="scanlines" patternUnits="userSpaceOnUse" '
        'width="100%" height="4">'
    )
    o.append(
        f'<rect width="100%" height="2" fill="black" opacity="{t["scanline_opacity"]}"/>'
    )
    o.append("</pattern>")

    # CRT screen glow filter
    o.append(
        '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur stdDeviation="2.0" result="blur"/>'
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
    )

    # Phosphor text glow (warmer / slightly stronger for amber)
    o.append(
        '<filter id="textglow" x="-10%" y="-10%" width="120%" height="120%">'
        '<feGaussianBlur stdDeviation="1.0" result="blur"/>'
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
    )

    # Inner shadow for bezel depth
    o.append(
        '<filter id="innershadow" x="-5%" y="-5%" width="110%" height="110%">'
        '<feComponentTransfer in="SourceAlpha">'
        '<feFuncA type="table" tableValues="1 0"/>'
        '</feComponentTransfer>'
        '<feGaussianBlur stdDeviation="6"/>'
        '<feOffset dx="0" dy="2" result="offsetblur"/>'
        '<feFlood flood-color="#000000" flood-opacity="0.5" result="color"/>'
        '<feComposite in2="offsetblur" operator="in"/>'
        '<feComposite in2="SourceAlpha" operator="in"/>'
        '<feMerge>'
        '<feMergeNode in="SourceGraphic"/>'
        '<feMergeNode/>'
        '</feMerge>'
        '</filter>'
    )

    o.append("</defs>")

    # ── Styles ──
    o.append("<style>")
    o.append(f"""
      .bg {{ fill: {t["bg"]}; }}
      .term-text {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["fg"]};
        filter: url(#textglow);
      }}
      .term-prompt {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["prompt"]};
        font-weight: bold;
        filter: url(#textglow);
      }}
      .term-header {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["header"]};
        font-weight: bold;
        filter: url(#textglow);
      }}
      .term-stat {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["value"]};
        filter: url(#textglow);
      }}
      .term-dim {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["fg_dim"]};
        filter: url(#textglow);
      }}
      .term-boot {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["boot_fg"]};
        filter: url(#textglow);
      }}
      .term-boot-ok {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["boot_ok"]};
        font-weight: bold;
        filter: url(#textglow);
      }}
      .term-ascii {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["fg_bright"]};
        filter: url(#textglow);
      }}
      .term-greeting {{
        font-family: {FONT};
        font-size: 26px;
        fill: {t["fg_bright"]};
        font-weight: bold;
        filter: url(#textglow);
      }}

      /* Cursor blink */
      @keyframes blink {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
      .cursor {{
        fill: {t["cursor"]};
        animation: blink 1s step-end infinite;
      }}
      /* Line reveal */
      @keyframes lineReveal {{
        0% {{ opacity: 0; transform: translateX(-4px); }}
        100% {{ opacity: 1; transform: translateX(0); }}
      }}

      /* Character typing via clip-path */
      @keyframes typeClip {{
        0% {{ clip-path: inset(0 100% 0 0); }}
        100% {{ clip-path: inset(0 0% 0 0); }}
      }}

      /* More pronounced CRT flicker with occasional brightness dip */
      @keyframes crtFlicker {{
        0%   {{ opacity: 1; }}
        15%  {{ opacity: 1; }}
        16%  {{ opacity: 0.82; }}
        17%  {{ opacity: 1; }}
        42%  {{ opacity: 1; }}
        43%  {{ opacity: 0.88; }}
        44%  {{ opacity: 0.78; }}
        45%  {{ opacity: 1; }}
        70%  {{ opacity: 1; }}
        71%  {{ opacity: 0.90; }}
        72%  {{ opacity: 1; }}
        90%  {{ opacity: 1; }}
        91%  {{ opacity: 0.85; }}
        92%  {{ opacity: 0.92; }}
        93%  {{ opacity: 1; }}
        100% {{ opacity: 1; }}
      }}
      .crt-wrap {{
        animation: crtFlicker 3s infinite;
      }}

      /* Scanline pattern scroll */
      @keyframes scanScroll {{
        0%   {{ transform: translateY(0); }}
        100% {{ transform: translateY(4px); }}
      }}
      .scanline-layer {{
        animation: scanScroll 0.15s linear infinite;
      }}

      /* Scrolling bright scanline bar */
      @keyframes scanBar {{
        0%   {{ transform: translateY(-4px); }}
        100% {{ transform: translateY({H + 4}px); }}
      }}
      .scan-bar {{
        animation: scanBar 6s linear infinite;
      }}
    """)

    # Per-line animation delays
    for i in range(n_lines):
        delay = i * type_delay_per_line
        line_type = lines[i][0]
        if line_type == "blank":
            continue
        text = lines[i][1] if len(lines[i]) > 1 else ""
        char_count = len(text)
        type_dur = max(0.3, char_count * char_type_speed)

        o.append(f"""
      .line-{i} {{
        opacity: 0;
        animation: lineReveal 0.05s ease-out {delay:.2f}s forwards;
      }}
      .line-{i} .typed {{
        clip-path: inset(0 100% 0 0);
        animation: typeClip {type_dur:.2f}s steps({max(1, char_count)}) {delay:.2f}s forwards;
      }}
    """)

    o.append("</style>")

    # ── Background with thick rounded bezel ──
    o.append(f'<rect class="bg" width="{W}" height="{H}" rx="16"/>')

    # ── CRT ambient glow ──
    o.append(
        f'<rect x="16" y="10" width="{W - 32}" height="{H - 20}" rx="12" '
        f'fill="{t["glow_color"]}" filter="url(#glow)"/>'
    )

    # ── Inner shadow overlay for bezel depth ──
    o.append(
        f'<rect x="4" y="4" width="{W - 8}" height="{H - 8}" rx="14" '
        f'fill="none" stroke="{t["bezel_highlight"]}" stroke-width="1" '
        f'opacity="0.3"/>'
    )

    # ── CRT flicker wrapper ──
    o.append('<g class="crt-wrap">')

    # ── Render lines ──
    for i, line_data in enumerate(lines):
        line_type = line_data[0]
        text = line_data[1] if len(line_data) > 1 else ""
        lang_color = line_data[2] if len(line_data) > 2 else None

        y = MARGIN_Y + (i + 1) * LINE_H
        x = MARGIN_X

        if line_type == "blank":
            continue

        css_class = {
            "prompt": "term-prompt",
            "header": "term-header",
            "stat":   "term-stat",
            "divider": "term-dim",
            "lang":   "term-text",
            "boot":   "term-boot",
            "ascii":  "term-ascii",
            "greeting": "term-greeting",
        }.get(line_type, "term-text")

        o.append(f'<g class="line-{i}">')

        if line_type == "cursor_prompt":
            o.append(
                f'<text class="term-prompt" x="{x}" y="{y}">'
                f'<tspan class="typed">{esc(text)}</tspan>'
                f'<tspan class="cursor">\u2588</tspan></text>'
            )
        elif line_type == "header":
            forced_w = len(text) * CHAR_W
            o.append(
                f'<text class="{css_class}" x="{x}" y="{y}" '
                f'textLength="{forced_w}" lengthAdjust="spacing">'
                f'<tspan class="typed">{esc(text)}</tspan></text>'
            )
        elif line_type == "boot":
            # Split off the "OK" at end and color it differently
            if text.endswith("OK"):
                prefix = text[:-2]
                o.append(
                    f'<text class="term-boot" x="{x}" y="{y}">'
                    f'<tspan class="typed">{esc(prefix)}</tspan></text>'
                )
                ok_x = x + len(prefix) * CHAR_W
                o.append(
                    f'<text class="term-boot-ok" x="{ok_x}" y="{y}">'
                    f'<tspan class="typed">OK</tspan></text>'
                )
            else:
                o.append(
                    f'<text class="term-boot" x="{x}" y="{y}">'
                    f'<tspan class="typed">{esc(text)}</tspan></text>'
                )

        elif line_type == "lang" and lang_color:
            bar_start_idx = text.index("\u2588")
            bar_end_idx = text.rindex("\u2591") + 1 if "\u2591" in text else text.rindex("\u2588") + 1
            before_bar = text[:bar_start_idx]
            bar_section = text[bar_start_idx:bar_end_idx]
            after_bar = text[bar_end_idx:]

            filled_chars = bar_section.count("\u2588")
            empty_chars = bar_section.count("\u2591")
            filled_text = "\u2588" * filled_chars
            empty_text = "\u2591" * empty_chars

            # Language name
            o.append(
                f'<text class="{css_class}" x="{x}" y="{y}">'
                f'<tspan class="typed">{esc(before_bar)}</tspan></text>'
            )
            # Filled bar — actual language color from GitHub
            bar_x = x + len(before_bar) * CHAR_W
            o.append(
                f'<text x="{bar_x}" y="{y}" '
                f'font-family="{FONT}" font-size="14px" '
                f'fill="{lang_color}" opacity="{t["lang_color_opacity"]}" '
                f'filter="url(#textglow)">'
                f'<tspan class="typed">{filled_text}</tspan></text>'
            )
            # Empty bar
            if empty_chars > 0:
                empty_x = bar_x + filled_chars * CHAR_W
                o.append(
                    f'<text x="{empty_x}" y="{y}" '
                    f'font-family="{FONT}" font-size="14px" '
                    f'fill="{t["bar_empty"]}" '
                    f'filter="url(#textglow)">'
                    f'<tspan class="typed">{empty_text}</tspan></text>'
                )
            # Percentage
            after_x = bar_x + (filled_chars + empty_chars) * CHAR_W
            o.append(
                f'<text class="{css_class}" x="{after_x}" y="{y}">'
                f'<tspan class="typed">{esc(after_bar)}</tspan></text>'
            )
        else:
            o.append(
                f'<text class="{css_class}" x="{x}" y="{y}">'
                f'<tspan class="typed">{esc(text)}</tspan></text>'
            )

        o.append("</g>")

    # ── Close CRT flicker wrapper ──
    o.append("</g>")

    # ── Scanline overlay ──
    o.append(
        f'<rect class="scanline-layer" width="{W}" height="{H + 8}" '
        f'fill="url(#scanlines)" rx="16" pointer-events="none"/>'
    )

    # ── Scrolling bright scanline bar ──
    o.append(
        f'<g class="scan-bar" opacity="0.07">'
        f'<rect x="0" y="0" width="{W}" height="3" fill="{t["fg"]}" rx="1"/>'
        f'</g>'
    )

    # ── CRT vignette — heavier / warmer ──
    o.append(
        f'<radialGradient id="vig" cx="50%" cy="50%" r="65%">'
        f'<stop offset="50%" stop-color="transparent"/>'
        f'<stop offset="100%" stop-color="#0a0500" stop-opacity="{t["vignette_opacity"]}"/>'
        f'</radialGradient>'
    )
    o.append(
        f'<rect width="{W}" height="{H}" fill="url(#vig)" rx="16" pointer-events="none"/>'
    )

    # ── CRT bezel — thicker ──
    o.append(
        f'<rect width="{W}" height="{H}" rx="16" fill="none" '
        f'stroke="{t["bezel"]}" stroke-width="4" filter="url(#innershadow)"/>'
    )

    o.append("</svg>")
    return "\n".join(o)


# ── Main ────────────────────────────────────────────────────────────
def main():
    try:
        streak = fetch_streak()
        print(
            f"Streak: current={streak['current']}, "
            f"total={streak['total']}, longest={streak['longest']}"
        )
    except Exception as e:
        print(f"\u26a0 Failed to fetch streak: {e}", file=sys.stderr)
        streak = dict(
            total=2456, total_start='2019-06-15', total_end='2026-04-05',
            current=15, current_start='2026-03-22', current_end='2026-04-05',
            longest=42, longest_start='2024-11-01', longest_end='2024-12-12',
        )

    try:
        langs = fetch_langs()
        print(f"Languages: {', '.join(l['name'] for l in langs)}")
    except Exception as e:
        print(f"\u26a0 Failed to fetch languages: {e}", file=sys.stderr)
        langs = [
            dict(name='Python', pct=35.2, color='#3572A5'),
            dict(name='TypeScript', pct=22.1, color='#3178c6'),
            dict(name='Go', pct=18.4, color='#00ADD8'),
            dict(name='Rust', pct=12.8, color='#dea584'),
            dict(name='Shell', pct=11.5, color='#89e051'),
        ]

    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        svg = build_svg(streak, langs, theme=theme)
        out = ASSETS / f"terminal-v1-{theme}.svg"
        out.write_text(svg)
        print(f"\u2713 Wrote {out} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()

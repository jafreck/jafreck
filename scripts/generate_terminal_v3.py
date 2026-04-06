#!/usr/bin/env python3
"""Generate a Modern macOS Terminal SVG with GitHub stats.

Clean macOS window chrome, zsh prompt, Dracula/One Dark palette,
ASCII banner, neofetch-style stats, and subtle typing animation.
"""

import json, math, os, re, sys, urllib.request
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
        return f"{s.strftime('%b %d')} – {e.strftime('%b %d')}"
    return f"{s.strftime('%b %d, %Y')} – {e.strftime('%b %d, %Y')}"


# ── Banner ──────────────────────────────────────────────────────────
BANNER_TEXT = "Hi there! 👋"


# ── Themes ──────────────────────────────────────────────────────────
THEMES = {
    "dark": dict(
        # Window chrome
        titlebar_bg="#21252b",
        titlebar_fg="#9da5b4",
        window_border="#181a1f",
        # Terminal body — One Dark inspired
        bg="#282c34",
        fg="#abb2bf",
        fg_dim="#5c6370",
        fg_bright="#d7dae0",
        # Prompt colors
        prompt_dir="#61afef",       # blue for directory
        prompt_arrow="#56b6c2",     # cyan for ❯
        prompt_user="#c678dd",      # purple for user
        # Semantic
        cursor="#528bff",
        banner="#c678dd",           # purple banner
        stat_emoji="#e5c07b",       # gold for emoji
        stat_label="#abb2bf",
        stat_value="#e5c07b",
        stat_range="#5c6370",
        separator="#3e4452",
        table_header="#61afef",
        lang_dot_opacity="1.0",
        # Vignette
        vignette_opacity="0.2",
    ),
    "light": dict(
        titlebar_bg="#e8e8e8",
        titlebar_fg="#6a6a6a",
        window_border="#d0d0d0",
        bg="#fafafa",
        fg="#383a42",
        fg_dim="#a0a1a7",
        fg_bright="#232428",
        prompt_dir="#4078f2",
        prompt_arrow="#0184bc",
        prompt_user="#a626a4",
        cursor="#526fff",
        banner="#a626a4",
        stat_emoji="#c18401",
        stat_label="#383a42",
        stat_value="#c18401",
        stat_range="#a0a1a7",
        separator="#d3d3d8",
        table_header="#4078f2",
        lang_dot_opacity="1.0",
        vignette_opacity="0.08",
    ),
}

FONT = "'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace"
CHAR_W = 8.4
LINE_H = 22
MARGIN_X = 28
TITLE_BAR_H = 40
CONTENT_Y_START = TITLE_BAR_H + 16


# ── SVG builder ─────────────────────────────────────────────────────
def build_svg(streak, langs, theme="dark"):
    t = THEMES[theme]

    # ── Build terminal lines ──
    # Each entry: (style, text, [extra_data])
    # Styles: prompt, banner, blank, stat, divider, lang_header, lang, command
    lines = []

    # Initial prompt + command
    lines.append(("prompt", None))  # rendered specially
    lines.append(("blank", ""))

    # Banner
    lines.append(("banner", BANNER_TEXT))
    lines.append(("blank", ""))

    # Separator
    lines.append(("divider", "  " + "─" * 62))
    lines.append(("blank", ""))

    # Stats — neofetch style
    cur_range = fmt_range(streak.get("current_start"), streak.get("current_end"))
    total_range = fmt_range(streak.get("total_start"), streak.get("total_end"))
    longest_range = fmt_range(streak.get("longest_start"), streak.get("longest_end"))

    lines.append(("stat", f"  🔥 Current Streak   {streak['current']:>5} days   {esc(cur_range)}"))
    lines.append(("stat", f"  🏆 Longest Streak   {streak['longest']:>5} days   {esc(longest_range)}"))
    lines.append(("stat", f"  ⭐ Total Commits    {streak['total']:>5}         {esc(total_range)}"))
    lines.append(("blank", ""))

    # Separator
    lines.append(("divider", "  " + "─" * 62))
    lines.append(("blank", ""))

    # Language table header
    lines.append(("lang_header", "  LANGUAGE          USAGE"))
    lines.append(("blank", ""))

    # Languages — clean table with colored dots
    max_name = max((len(l["name"]) for l in langs), default=10)
    for lang in langs:
        padded = lang["name"].ljust(max_name)
        bar_len = 20
        filled = round(lang["pct"] / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        lines.append(("lang", f"  ● {padded}  {bar}  {lang['pct']:>5.1f}%", lang))

    lines.append(("blank", ""))

    # Final prompt with cursor
    lines.append(("final_prompt", None))

    # ── Layout ──
    n_lines = len(lines)
    H = CONTENT_Y_START + n_lines * LINE_H + 24

    o = []

    # ── SVG root ──
    o.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="100%" viewBox="0 0 {W} {H}" '
        f'font-family="{FONT}">'
    )

    # ── Defs ──
    type_delay = 0.25
    o.append("<defs>")

    # Subtle text smoothing filter
    o.append(
        '<filter id="soften" x="-5%" y="-5%" width="110%" height="110%">'
        '<feGaussianBlur stdDeviation="0.3" result="blur"/>'
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
    )

    o.append("</defs>")

    # ── Styles ──
    o.append("<style>")
    o.append(f"""
      /* Base text */
      .t {{ font-family: {FONT}; font-size: 14px; fill: {t["fg"]}; }}
      .t-dim {{ font-family: {FONT}; font-size: 14px; fill: {t["fg_dim"]}; }}
      .t-bright {{ font-family: {FONT}; font-size: 14px; fill: {t["fg_bright"]}; font-weight: 600; }}
      .t-banner {{ font-family: {FONT}; font-size: 14px; fill: {t["banner"]}; }}
      .t-dir {{ font-family: {FONT}; font-size: 14px; fill: {t["prompt_dir"]}; font-weight: 600; }}
      .t-arrow {{ font-family: {FONT}; font-size: 14px; fill: {t["prompt_arrow"]}; font-weight: 700; }}
      .t-cmd {{ font-family: {FONT}; font-size: 14px; fill: {t["fg_bright"]}; }}
      .t-stat {{ font-family: {FONT}; font-size: 14px; fill: {t["stat_label"]}; }}
      .t-val {{ font-family: {FONT}; font-size: 14px; fill: {t["stat_value"]}; font-weight: 600; }}
      .t-range {{ font-family: {FONT}; font-size: 14px; fill: {t["stat_range"]}; }}
      .t-header {{ font-family: {FONT}; font-size: 13px; fill: {t["table_header"]}; font-weight: 600; letter-spacing: 0.5px; }}
      .t-sep {{ font-family: {FONT}; font-size: 14px; fill: {t["separator"]}; }}
      .t-title {{ font-family: {FONT}; font-size: 13px; fill: {t["titlebar_fg"]}; }}

      /* Cursor blink — thin line */
      @keyframes blink {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
      .cursor {{
        fill: {t["cursor"]};
        animation: blink 1.2s step-end infinite;
      }}

      /* Smooth character reveal */
      @keyframes reveal {{
        from {{ clip-path: inset(0 100% 0 0); }}
        to {{ clip-path: inset(0 0% 0 0); }}
      }}
      @keyframes fadeIn {{
        from {{ opacity: 0; }}
        to {{ opacity: 1; }}
      }}

      /* Cursor-wrap fade in */
      .cursor-wrap {{
        opacity: 0;
        animation: fadeIn 0.1s ease {(n_lines - 1) * type_delay + 0.3:.2f}s forwards;
      }}
    """)

    # Per-line animation — delay based on line index so lines reveal top-to-bottom.
    # Blank lines still consume a delay slot to preserve ordering.
    for i, line_data in enumerate(lines):
        style = line_data[0]
        if style == "blank":
            continue
        if style == "prompt":
            text = f"~/source/{USERNAME} ❯ github-stats"
        elif style == "final_prompt":
            text = f"~/source/{USERNAME} ❯ "
        else:
            text = line_data[1] if len(line_data) > 1 and line_data[1] else ""
        delay = i * type_delay
        char_count = max(len(text), 1)
        type_dur = max(0.15, char_count * 0.015)

        o.append(f"""
      .line-{i} {{
        opacity: 0;
        animation: fadeIn 0.08s ease {delay:.2f}s forwards;
      }}
      .line-{i} .typed {{
        clip-path: inset(0 100% 0 0);
        animation: reveal {type_dur:.2f}s steps({char_count}) {delay:.2f}s forwards;
      }}
    """)

    o.append("</style>")

    # ── Window background ──
    o.append(f'<rect width="{W}" height="{H}" rx="10" fill="{t["bg"]}"/>')

    # ── Title bar ──
    o.append(
        f'<rect width="{W}" height="{TITLE_BAR_H}" rx="10" fill="{t["titlebar_bg"]}"/>'
    )
    # Square off bottom corners of title bar
    o.append(
        f'<rect y="{TITLE_BAR_H - 10}" width="{W}" height="10" fill="{t["titlebar_bg"]}"/>'
    )

    # Traffic lights
    dots = [("#ff5f56", "#e0443e"), ("#ffbd2e", "#dea123"), ("#27c93f", "#1aab29")]
    for idx, (fill, stroke) in enumerate(dots):
        cx = 22 + idx * 22
        cy = TITLE_BAR_H // 2
        o.append(
            f'<circle cx="{cx}" cy="{cy}" r="6.5" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="0.5"/>'
        )

    # Title text
    title_text = f"{USERNAME} — zsh — 80×24"
    o.append(
        f'<text class="t-title" x="{W // 2}" y="{TITLE_BAR_H // 2 + 4}" '
        f'text-anchor="middle">{esc(title_text)}</text>'
    )

    # Subtle line under title bar
    o.append(
        f'<line x1="0" y1="{TITLE_BAR_H}" x2="{W}" y2="{TITLE_BAR_H}" '
        f'stroke="{t["window_border"]}" stroke-width="1"/>'
    )

    # ── Render lines ──
    for i, line_data in enumerate(lines):
        style = line_data[0]
        y = CONTENT_Y_START + (i + 1) * LINE_H
        x = MARGIN_X

        if style == "blank":
            continue

        o.append(f'<g class="line-{i}">')

        if style == "prompt":
            # ~/source/jafreck ❯ github-stats
            dir_text = f"~/source/{USERNAME}"
            arrow = " ❯ "
            cmd_text = "github-stats"

            o.append(f'<text class="typed" x="{x}" y="{y}">')
            o.append(f'<tspan class="t-dir">{esc(dir_text)}</tspan>')
            o.append(f'<tspan class="t-arrow">{esc(arrow)}</tspan>')
            o.append(f'<tspan class="t-cmd">{esc(cmd_text)}</tspan>')
            o.append('</text>')

        elif style == "final_prompt":
            dir_text = f"~/source/{USERNAME}"
            arrow = " ❯ "
            final_prompt_text = dir_text + arrow
            o.append(f'<text class="typed" x="{x}" y="{y}">')
            o.append(f'<tspan class="t-dir">{esc(dir_text)}</tspan>')
            o.append(f'<tspan class="t-arrow">{esc(arrow)}</tspan>')
            o.append('</text>')

        elif style == "banner":
            text = line_data[1]
            o.append(
                f'<text x="{x + 10}" y="{y}" font-family="{FONT}" '
                f'font-size="26px" fill="{t["banner"]}" font-weight="700">'
                f'<tspan class="typed">{esc(text)}</tspan></text>'
            )

        elif style == "divider":
            text = line_data[1]
            o.append(
                f'<text class="t-sep" x="{x}" y="{y}">'
                f'<tspan class="typed">{esc(text)}</tspan></text>'
            )

        elif style == "stat":
            text = line_data[1]
            # Split into emoji+label, value, range parts
            # Format: "  🔥 Current Streak   15 days   Mar 22 – Apr 05"
            # We render the whole thing but colorize parts
            stripped = text.lstrip()
            emoji = stripped[:2]
            rest = stripped[2:]
            m = re.match(r'^(.*?)(\d[\d,]*)\s*(days|)\s*(.*)', rest)
            if m:
                label = m.group(1)
                value = m.group(2)
                unit = m.group(3)
                range_text = m.group(4)

                ex = x + 2 * CHAR_W  # indent
                o.append(f'<text x="{ex}" y="{y}">')
                o.append(f'<tspan class="t-stat">{emoji} {esc(label)}</tspan>')
                o.append(f'<tspan class="t-val">{esc(value)}</tspan>')
                if unit:
                    o.append(f'<tspan class="t-stat"> {esc(unit)}   </tspan>')
                else:
                    o.append(f'<tspan class="t-stat">         </tspan>')
                if range_text.strip():
                    o.append(f'<tspan class="t-range">{esc(range_text.strip())}</tspan>')
                o.append('</text>')
            else:
                o.append(
                    f'<text class="t-stat" x="{x}" y="{y}">'
                    f'<tspan class="typed">{esc(text)}</tspan></text>'
                )

        elif style == "lang_header":
            text = line_data[1]
            o.append(
                f'<text class="t-header" x="{x}" y="{y}">'
                f'<tspan class="typed">{esc(text)}</tspan></text>'
            )

        elif style == "lang":
            lang = line_data[2]
            lang_color = lang.get("color", t["fg"])
            text = line_data[1]

            # Render: colored dot, name, bar (colored), percentage
            dot_x = x + 2 * CHAR_W
            # ● dot
            o.append(
                f'<text x="{dot_x}" y="{y}" font-family="{FONT}" font-size="14px" '
                f'fill="{lang_color}" opacity="{t["lang_dot_opacity"]}">'
                f'<tspan class="typed">●</tspan></text>'
            )

            # Name
            name_x = dot_x + 2 * CHAR_W
            name_text = lang["name"].ljust(max((len(l["name"]) for l in langs), default=10))
            o.append(
                f'<text class="t" x="{name_x}" y="{y}">'
                f'<tspan class="typed">{esc(name_text)}</tspan></text>'
            )

            # Bar
            max_name_len = max((len(l["name"]) for l in langs), default=10)
            bar_x = name_x + (max_name_len + 2) * CHAR_W
            bar_len = 20
            filled = round(lang["pct"] / 100 * bar_len)
            filled_text = "█" * filled
            empty_text = "░" * (bar_len - filled)

            if filled > 0:
                o.append(
                    f'<text x="{bar_x}" y="{y}" font-family="{FONT}" font-size="14px" '
                    f'fill="{lang_color}" opacity="{t["lang_dot_opacity"]}">'
                    f'<tspan class="typed">{filled_text}</tspan></text>'
                )
            if bar_len - filled > 0:
                empty_x = bar_x + filled * CHAR_W
                o.append(
                    f'<text class="t-dim" x="{empty_x}" y="{y}">'
                    f'<tspan class="typed">{empty_text}</tspan></text>'
                )

            # Percentage
            pct_x = bar_x + bar_len * CHAR_W + CHAR_W
            pct_text = f"{lang['pct']:>5.1f}%"
            o.append(
                f'<text class="t-bright" x="{pct_x}" y="{y}">'
                f'<tspan class="typed">{esc(pct_text)}</tspan></text>'
            )

        o.append("</g>")

    # ── Blinking thin cursor ──
    final_idx = n_lines - 1
    prompt_text = f"~/source/{USERNAME}" + " ❯ "
    cursor_x = MARGIN_X + len(prompt_text) * CHAR_W
    # Match the exact y baseline used in the render loop: CONTENT_Y_START + (i+1)*LINE_H
    cursor_baseline_y = CONTENT_Y_START + (final_idx + 1) * LINE_H

    o.append('<g class="cursor-wrap">')
    o.append(
        f'<rect class="cursor" x="{cursor_x}" y="{cursor_baseline_y - 14}" '
        f'width="2" height="17" rx="1"/>'
    )
    o.append("</g>")

    # ── Subtle vignette ──
    o.append(
        f'<radialGradient id="vig" cx="50%" cy="50%" r="70%">'
        f'<stop offset="70%" stop-color="transparent"/>'
        f'<stop offset="100%" stop-color="black" stop-opacity="{t["vignette_opacity"]}"/>'
        f'</radialGradient>'
    )
    o.append(
        f'<rect width="{W}" height="{H}" fill="url(#vig)" rx="10" pointer-events="none"/>'
    )

    # ── Window border ──
    o.append(
        f'<rect width="{W}" height="{H}" rx="10" fill="none" '
        f'stroke="{t["window_border"]}" stroke-width="1"/>'
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
        print(f"⚠ Failed to fetch streak: {e}", file=sys.stderr)
        streak = dict(
            total=2456, total_start='2019-06-15', total_end='2026-04-05',
            current=15, current_start='2026-03-22', current_end='2026-04-05',
            longest=42, longest_start='2024-11-01', longest_end='2024-12-12',
        )

    try:
        langs = fetch_langs()
        print(f"Languages: {', '.join(l['name'] for l in langs)}")
    except Exception as e:
        print(f"⚠ Failed to fetch languages: {e}", file=sys.stderr)
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
        out = ASSETS / f"terminal-v3-{theme}.svg"
        out.write_text(svg)
        print(f"✓ Wrote {out} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()

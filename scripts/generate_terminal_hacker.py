#!/usr/bin/env python3
"""Generate a "Hacker Terminal" SVG with GitHub stats.

Linux/Unix CRT aesthetic with neofetch-style layout, Hollywood-style
character scramble animation, multiple typed commands, phosphor glow,
and retro CRT effects. CSS keyframes only — no JavaScript.
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
        bg="#0a0a0a",
        fg="#00FF41",
        fg_dim="#0a6e1e",
        fg_bright="#33FF66",
        prompt="#00FF41",
        cursor="#00FF41",
        label="#00cc33",
        value="#00FF41",
        bar_empty="#0d2a0d",
        header="#00FF41",
        border="#0d4a0d",
        scanline_opacity="0.08",
        glow_color="rgba(0,255,65,0.12)",
        glow_strong="rgba(0,255,65,0.5)",
        bezel="#111111",
        lang_color_opacity="0.95",
        accent="#00ccff",
        wave_label="#00cc33",
    ),
    "light": dict(
        bg="#f0efe8",
        fg="#1a4a1a",
        fg_dim="#6a8a6a",
        fg_bright="#0a3a0a",
        prompt="#1a5a1a",
        cursor="#1a4a1a",
        label="#3a6a3a",
        value="#1a4a1a",
        bar_empty="#d0ddd0",
        header="#1a4a1a",
        border="#8aaa8a",
        scanline_opacity="0.04",
        glow_color="rgba(26,74,26,0.06)",
        glow_strong="rgba(26,74,26,0.15)",
        bezel="#c0c0b8",
        lang_color_opacity="0.85",
        accent="#1a6a8a",
        wave_label="#3a6a3a",
    ),
}

FONT = "'Courier New', 'Consolas', 'Liberation Mono', monospace"
CHAR_W = 8.4
LINE_H = 22
MARGIN_X = 30
MARGIN_Y = 24

# Random chars for Hollywood scramble effect
GLITCH_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(){}[]|;:<>?"


# ── Progress bar helpers ────────────────────────────────────────────
def _make_bar(pct, bar_len=30):
    """Return a thin Unicode bar: ▰▰▰▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱."""
    filled = max(1, round(pct / 100 * bar_len))
    return "\u25B0" * filled + "\u25B1" * (bar_len - filled)


# ── ASCII art logo ──────────────────────────────────────────────────
# ── SVG builder ─────────────────────────────────────────────────────
def build_svg(streak, langs, theme="dark"):
    t = THEMES[theme]
    timestamp = "23:15:42"
    prompt_prefix = f"[{timestamp}] {USERNAME}@github:~/.github/{USERNAME}$"

    cur_range = fmt_range(streak.get("current_start"), streak.get("current_end"))
    total_range = fmt_range(streak.get("total_start"), streak.get("total_end"))
    longest_range = fmt_range(streak.get("longest_start"), streak.get("longest_end"))

    # ── Build all terminal lines ──
    lines = []

    # Command 1: whoami
    lines.append(("prompt", f"{prompt_prefix} whoami"))
    lines.append(("blank", ""))
    lines.append(("stat", "  Hi there! \U0001f44b"))
    lines.append(("blank", ""))
    lines.append(("stat", f"  user:       {USERNAME}"))
    lines.append(("stat", f"  host:       github.com"))
    lines.append(("stat", f"  uptime:     since {streak.get('total_start', 'N/A')}"))
    lines.append(("divider", "  " + "-" * 40))
    lines.append(("stat", f"  commits:        {streak['total']}  ({esc(total_range)})"))
    lines.append(("stat", f"  current streak: {streak['current']} days  ({esc(cur_range)})"))
    lines.append(("stat", f"  longest streak: {streak['longest']} days  ({esc(longest_range)})"))
    lines.append(("blank", ""))

    # Command 2: cat /proc/github/stats
    timestamp2 = "23:15:47"
    prompt2 = f"[{timestamp2}] {USERNAME}@github:~/.github/{USERNAME}$"
    lines.append(("prompt", f"{prompt2} cat /proc/github/stats"))
    lines.append(("blank", ""))
    box_w = 48
    lines.append(("header", "\u256D" + "\u2500" * box_w + "\u256E"))
    lines.append(("header", "\u2502" + "CONTRIBUTION STATISTICS".center(box_w) + "\u2502"))
    lines.append(("header", "\u2570" + "\u2500" * box_w + "\u256F"))
    lines.append(("blank", ""))
    lines.append(("stat", f"  🔥 Current Streak ... {streak['current']:>5} days   {esc(cur_range)}"))
    lines.append(("stat", f"  🏆 Longest Streak ... {streak['longest']:>5} days   {esc(longest_range)}"))
    lines.append(("stat", f"  📊 Total Commits .... {streak['total']:>5}         {esc(total_range)}"))
    lines.append(("blank", ""))

    # Command 3: lang-breakdown
    timestamp3 = "23:15:51"
    prompt3 = f"[{timestamp3}] {USERNAME}@github:~/.github/{USERNAME}$"
    lines.append(("prompt", f"{prompt3} lang-breakdown --top {len(langs)}"))
    lines.append(("blank", ""))

    max_name = max((len(l["name"]) for l in langs), default=10)
    for lang in langs:
        padded = lang["name"].ljust(max_name)
        bar = _make_bar(lang["pct"])
        lines.append(("lang", f"  {padded}  {bar}  {lang['pct']:>5.1f}%", lang.get("color", t["fg"])))

    lines.append(("blank", ""))

    # Final prompt with thin underscore cursor
    timestamp4 = "23:15:54"
    prompt4 = f"[{timestamp4}] {USERNAME}@github:~/.github/{USERNAME}$"
    lines.append(("prompt", f"{prompt4} "))

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
    type_delay_per_line = 0.18  # faster typing — snappier
    char_type_speed = 0.012    # faster per-char
    scramble_dur = 0.4         # how long the scramble effect lasts

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

    # Strong phosphor glow filter
    o.append(
        '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">'
        f'<feGaussianBlur stdDeviation="2.5" result="blur"/>'
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
    )

    # Text glow — stronger bloom
    o.append(
        '<filter id="textglow" x="-15%" y="-15%" width="130%" height="130%">'
        f'<feGaussianBlur stdDeviation="1.2" result="blur"/>'
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
    )

    # Extra strong glow for logo
    o.append(
        '<filter id="logoglow" x="-20%" y="-20%" width="140%" height="140%">'
        f'<feGaussianBlur stdDeviation="2.0" result="blur"/>'
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
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
      .term-logo {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["fg_bright"]};
        filter: url(#logoglow);
      }}
      .term-label {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["wave_label"]};
        font-weight: bold;
        filter: url(#textglow);
      }}
      .term-neofetch {{
        font-family: {FONT};
        font-size: 14px;
        fill: {t["fg"]};
        filter: url(#textglow);
      }}

      /* Thin underscore cursor blink */
      @keyframes cursorBlink {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
      .cursor {{
        fill: {t["cursor"]};
        animation: cursorBlink 0.8s step-end infinite;
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

      /* Hollywood scramble: random chars flash then settle */
      @keyframes scramble {{
        0% {{ opacity: 1; }}
        100% {{ opacity: 0; }}
      }}
      @keyframes unscramble {{
        0% {{ opacity: 0; }}
        100% {{ opacity: 1; }}
      }}

      /* CRT flicker */
      @keyframes crtFlicker {{
        0% {{ opacity: 1; }}
        92% {{ opacity: 1; }}
        93% {{ opacity: 0.90; }}
        94% {{ opacity: 1; }}
        96% {{ opacity: 0.94; }}
        97% {{ opacity: 1; }}
        100% {{ opacity: 1; }}
      }}
      .crt-wrap {{
        animation: crtFlicker 3s infinite;
      }}

      /* Scanline scroll */
      @keyframes scanScroll {{
        0% {{ transform: translateY(0); }}
        100% {{ transform: translateY(4px); }}
      }}
      .scanline-layer {{
        animation: scanScroll 0.15s linear infinite;
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
        type_dur = max(0.15, char_count * char_type_speed)

        # Prompt lines get scramble effect
        is_prompt = line_type == "prompt"
        scramble_delay = delay
        settle_delay = delay + scramble_dur

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

        # Scramble overlay for prompt lines
        if is_prompt:
            o.append(f"""
      .line-{i} .scramble-overlay {{
        opacity: 0;
        animation: lineReveal 0.05s ease-out {scramble_delay:.2f}s forwards,
                   scramble {scramble_dur:.2f}s ease-in {settle_delay:.2f}s forwards;
      }}
    """)

    # Cursor appears after last line
    cursor_delay = (n_lines - 1) * type_delay_per_line + 0.5
    o.append(f"""
      .cursor-wrap {{
        opacity: 0;
        animation: lineReveal 0.05s ease-out {cursor_delay:.2f}s forwards;
      }}
    """)

    o.append("</style>")

    # ── Background ──
    o.append(f'<rect class="bg" width="{W}" height="{H}" rx="8"/>')

    # ── CRT ambient glow ──
    o.append(
        f'<rect x="20" y="10" width="{W - 40}" height="{H - 20}" rx="6" '
        f'fill="{t["glow_color"]}" filter="url(#glow)"/>'
    )

    # ── CRT flicker wrapper ──
    o.append('<g class="crt-wrap">')

    # ── Render lines ──
    for i, line_data in enumerate(lines):
        line_type = line_data[0]
        text = line_data[1] if len(line_data) > 1 else ""
        extra = line_data[2] if len(line_data) > 2 else None

        y = MARGIN_Y + (i + 1) * LINE_H
        x = MARGIN_X

        if line_type == "blank":
            continue

        css_class = {
            "prompt": "term-prompt",
            "header": "term-header",
            "stat": "term-stat",
            "divider": "term-dim",
            "lang": "term-text",
            "neofetch": "term-neofetch",
        }.get(line_type, "term-text")

        o.append(f'<g class="line-{i}">')

        if line_type == "lang" and extra:
            lang_color = extra
            # Split the text to color the bar with language color
            bar_char = "\u25B0"
            empty_char = "\u25B1"

            if bar_char in text:
                bar_start_idx = text.index(bar_char)
                # Find end of bar section
                last_bar = text.rindex(bar_char) if bar_char in text else bar_start_idx
                last_empty = text.rindex(empty_char) if empty_char in text else last_bar
                bar_end_idx = max(last_bar, last_empty) + 1

                before_bar = text[:bar_start_idx]
                bar_section = text[bar_start_idx:bar_end_idx]
                after_bar = text[bar_end_idx:]

                filled_chars = bar_section.count(bar_char)
                empty_chars = bar_section.count(empty_char)

                # Name
                o.append(
                    f'<text class="{css_class}" x="{x}" y="{y}">'
                    f'<tspan class="typed">{esc(before_bar)}</tspan></text>'
                )
                # Filled bar in language color
                bar_x = x + len(before_bar) * CHAR_W
                o.append(
                    f'<text x="{bar_x}" y="{y}" '
                    f'font-family="{FONT}" font-size="14px" '
                    f'fill="{lang_color}" opacity="{t["lang_color_opacity"]}" '
                    f'filter="url(#textglow)">'
                    f'<tspan class="typed">{bar_char * filled_chars}</tspan></text>'
                )
                # Empty bar
                if empty_chars > 0:
                    empty_x = bar_x + filled_chars * CHAR_W
                    o.append(
                        f'<text x="{empty_x}" y="{y}" '
                        f'font-family="{FONT}" font-size="14px" '
                        f'fill="{t["bar_empty"]}" '
                        f'filter="url(#textglow)">'
                        f'<tspan class="typed">{empty_char * empty_chars}</tspan></text>'
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

        elif line_type == "prompt":
            # Render the actual text
            o.append(
                f'<text class="{css_class}" x="{x}" y="{y}">'
                f'<tspan class="typed">{esc(text)}</tspan></text>'
            )
            # Hollywood scramble overlay — random chars that fade out
            scramble_text = "".join(
                random.choice(GLITCH_CHARS) if c not in " []@:~/.$/\\" else c
                for c in text
            )
            o.append(
                f'<text class="{css_class} scramble-overlay" x="{x}" y="{y}">'
                f'{esc(scramble_text)}</text>'
            )
        elif line_type == "header":
            forced_w = len(text) * CHAR_W
            o.append(
                f'<text class="{css_class}" x="{x}" y="{y}" '
                f'textLength="{forced_w}" lengthAdjust="spacing">'
                f'<tspan class="typed">{esc(text)}</tspan></text>'
            )
        else:
            o.append(
                f'<text class="{css_class}" x="{x}" y="{y}">'
                f'<tspan class="typed">{esc(text)}</tspan></text>'
            )

        o.append("</g>")

    # ── Thin blinking underscore cursor ──
    last_prompt_idx = n_lines - 1
    last_text = lines[last_prompt_idx][1]
    cursor_x = MARGIN_X + len(last_text) * CHAR_W
    text_y = MARGIN_Y + (last_prompt_idx + 1) * LINE_H
    cursor_y = text_y + 1

    o.append('<g class="cursor-wrap">')
    o.append(
        f'<rect class="cursor" x="{cursor_x}" y="{cursor_y}" '
        f'width="{CHAR_W}" height="2" rx="0.5"/>'
    )
    o.append("</g>")

    # ── Close CRT flicker wrapper ──
    o.append("</g>")

    # ── Scanline overlay ──
    o.append(
        f'<rect class="scanline-layer" width="{W}" height="{H + 8}" '
        f'fill="url(#scanlines)" rx="8" pointer-events="none"/>'
    )

    # ── CRT vignette ──
    o.append(
        f'<radialGradient id="vig" cx="50%" cy="50%" r="70%">'
        f'<stop offset="60%" stop-color="transparent"/>'
        f'<stop offset="100%" stop-color="black" stop-opacity="0.35"/>'
        f'</radialGradient>'
    )
    o.append(
        f'<rect width="{W}" height="{H}" fill="url(#vig)" rx="8" pointer-events="none"/>'
    )

    # ── CRT bezel ──
    o.append(
        f'<rect width="{W}" height="{H}" rx="8" fill="none" '
        f'stroke="{t["bezel"]}" stroke-width="3"/>'
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
            total=0, total_start=None, total_end=None,
            current=0, current_start=None, current_end=None,
            longest=0, longest_start=None, longest_end=None,
        )

    try:
        langs = fetch_langs()
        print(f"Languages: {', '.join(l['name'] for l in langs)}")
    except Exception as e:
        print(f"⚠ Failed to fetch languages: {e}", file=sys.stderr)
        langs = [dict(name="N/A", pct=100, color="#858585")]

    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        svg = build_svg(streak, langs, theme=theme)
        out = ASSETS / f"terminal-hacker-{theme}.svg"
        out.write_text(svg)
        print(f"✓ Wrote {out} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate a Severance MDR (Macro Data Refinement) styled SVG with GitHub stats.

Dense fixed grid of single-digit numbers. An animated "fake cursor" glow
sweeps across the grid, causing nearby numbers to swell — mimicking the
interactive feel of Lumon's MDR terminals. Non-swelling numbers have a
subtle ambient flicker. GitHub stats are overlaid in Lumon-style panels.
"""

import json, math, os, random, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ───────────────────────────────────────────────────
USERNAME = "jafreck"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

W = 850
CELL_W = 24
CELL_H = 26
FS_NUM = 10
PANEL_W = 620
PX = (W - PANEL_W) / 2
PANEL_RX = 3
random.seed(42)

# Cursor / swell settings
CURSOR_DUR = 25
INFLUENCE_R = 50
INNER_R = 22
SWELL_PEAK_PCT = 3       # percent of cycle at peak
SWELL_WINDOW_PCT = 6     # percent of cycle for swell duration


# ── GitHub API ──────────────────────────────────────────────────────
# (duplicated from generate_matrix.py for standalone use)

def gql(query, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "mdr-stats",
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
        bg="#060A10",
        num_colors=["#2A4460", "#3A6080", "#5A90B0", "#8ABCD8"],
        swell_bright="#E0F0FF",
        cursor_glow="rgba(180,220,255,0.12)",
        panel_bg="#060A10",
        panel_opacity="0.92",
        panel_border="#2A5070",
        title="#8AB4D0",
        stat_num="#D0E4F4",
        stat_label="#5A8AAA",
        stat_range="#4A7A94",
        ring_stroke="#5A90B0",
        bin_fill="#1A4A6A",
        bin_bright="#2A6A8A",
        bin_bg="#040810",
        bin_border="#2A5070",
        bin_label="#5A8AAA",
        bin_pct="#9AC0DA",
        divider="#2A5070",
        refine_bg="#060A10",
        refine_fill="#1A4A6A",
        refine_fill_bright="#2A6A8A",
        refine_label="#5A8AAA",
        refine_pct="#9AC0DA",
        scanline_opacity="0.10",
        vignette_opacity="0.35",
    ),
    "light": dict(
        bg="#E8ECF0",
        num_colors=["#A0B0C0", "#7A8A98", "#5A6A78", "#3A4A58"],
        swell_bright="#0A1A2A",
        cursor_glow="rgba(10,26,42,0.08)",
        panel_bg="#F4F6F8",
        panel_opacity="0.94",
        panel_border="#8A9AAA",
        title="#3A5A72",
        stat_num="#1A2A3A",
        stat_label="#5A6A7A",
        stat_range="#7A8A9A",
        ring_stroke="#5A8AAA",
        bin_fill="#5A8AAA",
        bin_bright="#4A7A9A",
        bin_bg="#DEE2E8",
        bin_border="#8A9AAA",
        bin_label="#5A6A7A",
        bin_pct="#2A4A5A",
        divider="#8A9AAA",
        refine_bg="#DEE2E8",
        refine_fill="#5A8AAA",
        refine_fill_bright="#4A7A9A",
        refine_label="#5A6A7A",
        refine_pct="#2A4A5A",
        scanline_opacity="0.06",
        vignette_opacity="0.4",
    ),
}


# ── SVG builder ─────────────────────────────────────────────────────
def _panel(o, y, h):
    o.append(
        f'<rect class="pb" x="{PX}" y="{y}" width="{PANEL_W}" '
        f'height="{h}" rx="1"/>'
    )
    o.append(
        f'<rect class="ps" x="{PX}" y="{y}" width="{PANEL_W}" '
        f'height="{h}" rx="1"/>'
    )


def _sample_cursor_path(waypoints):
    """Sample cursor path into (x, y, time) tuples."""
    segs = []
    for i in range(len(waypoints) - 1):
        x0, y0 = waypoints[i]
        x1, y1 = waypoints[i + 1]
        segs.append((x0, y0, x1, y1, math.hypot(x1 - x0, y1 - y0)))
    total_len = sum(s[4] for s in segs)

    samples = []
    for si, (x0, y0, x1, y1, seg_len) in enumerate(segs):
        n_samp = max(2, round(150 * seg_len / total_len))
        seg_start = sum(s[4] for s in segs[:si]) / total_len
        for j in range(n_samp):
            f = j / n_samp
            px = x0 + (x1 - x0) * f
            py = y0 + (y1 - y0) * f
            t_sec = (seg_start + (seg_len / total_len) * f) * CURSOR_DUR
            samples.append((px, py, t_sec))
    return samples, segs


def build_svg(streak, langs, theme="dark"):
    t = THEMES[theme]
    n_langs = len(langs)

    # ── Layout ──
    title_y, title_h = 22, 42
    stats_y = title_y + title_h + 14
    stats_h = 155
    num_bins = min(n_langs, 5)
    langs_y = stats_y + stats_h + 80
    tier_h = 22
    langs_h = tier_h * 2 + 8
    H = langs_y + langs_h + 20

    cx = W / 2
    grid_cols = W // CELL_W
    grid_rows = H // CELL_H + 1
    divider_y = langs_y - 10
    max_cursor_y = divider_y - 20

    # ── Cursor path — stays above the refinement categories ──
    cursor_pts = [
        (100, 55), (380, 35), (720, 90),
        (750, min(220, max_cursor_y)), (600, min(200, max_cursor_y)),
        (300, min(180, max_cursor_y)), (60, min(160, max_cursor_y)),
        (200, 100), (550, 120), (100, 55),
    ]
    samples, segs = _sample_cursor_path(cursor_pts)
    total_len = sum(s[4] for s in segs)
    peak_pos = SWELL_PEAK_PCT / 100 * CURSOR_DUR

    # Pre-compute swell info for each grid cell
    cell_swell = {}
    for row in range(grid_rows):
        for col in range(grid_cols):
            gx = col * CELL_W + CELL_W / 2
            gy = row * CELL_H + CELL_H
            best_d, best_t = 999, 0
            for sx, sy, st in samples:
                d = math.hypot(gx - sx, gy - sy)
                if d < best_d:
                    best_d = d
                    best_t = st
            if best_d < INFLUENCE_R:
                kind = "sb" if best_d < INNER_R else "ss"
                delay = round((peak_pos - best_t) % CURSOR_DUR, 2)
                cell_swell[(col, row)] = (kind, delay)

    # Quantize delays into buckets (0.5s) for CSS class reuse
    delay_buckets = {}
    for key, (kind, delay) in cell_swell.items():
        bucket = round(delay * 2) / 2
        cell_swell[key] = (kind, bucket)
        delay_buckets[bucket] = True

    # ── Hotspots for brightness variation ──
    hs_rng = random.Random(42)
    hotspots = [
        (hs_rng.randint(3, grid_cols - 3), hs_rng.randint(2, grid_rows - 2))
        for _ in range(6)
    ]

    def hotspot_boost(c, r):
        for hx, hy in hotspots:
            d = math.hypot(c - hx, r - hy)
            if d < 4:
                return max(0, 3 - int(d))
        return 0

    # ── Cursor CSS keyframes from waypoints ──
    cursor_kf = []
    cum = 0
    cursor_kf.append(
        f"0%{{transform:translate({cursor_pts[0][0]}px,{cursor_pts[0][1]}px)}}"
    )
    for si, (_, _, x1, y1, seg_len) in enumerate(segs):
        cum += seg_len
        pct = round(cum / total_len * 100, 1)
        cursor_kf.append(f"{pct}%{{transform:translate({x1}px,{y1}px)}}")

    # ── Build SVG ──
    o = []
    o.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {W} {H}" width="100%">'
    )

    o.append("<defs>")
    o.append(
        f'<clipPath id="gc"><rect width="{W}" height="{H}" rx="12"/></clipPath>'
    )
    # Clip numbers and cursor to area above the category section
    o.append(
        f'<clipPath id="nc"><rect width="{W}" height="{divider_y}" rx="12"/></clipPath>'
    )
    o.append(
        f'<radialGradient id="cg">'
        f'<stop offset="0%" stop-color="{t["swell_bright"]}" stop-opacity="0.18"/>'
        f'<stop offset="100%" stop-color="{t["swell_bright"]}" stop-opacity="0"/>'
        f'</radialGradient>'
    )
    # CRT scanline pattern — tighter lines
    o.append(
        f'<pattern id="sl" width="2" height="3" patternUnits="userSpaceOnUse">'
        f'<rect width="2" height="1" fill="black" opacity="{t["scanline_opacity"]}"/>'
        f'</pattern>'
    )
    # CRT vignette — heavier, tighter falloff
    o.append(
        f'<radialGradient id="vig" cx="50%" cy="50%" r="60%">'
        f'<stop offset="0%" stop-color="black" stop-opacity="0"/>'
        f'<stop offset="70%" stop-color="black" stop-opacity="0"/>'
        f'<stop offset="90%" stop-color="black" stop-opacity="0.08"/>'
        f'<stop offset="100%" stop-color="black" stop-opacity="{t["vignette_opacity"]}"/>'
        f'</radialGradient>'
    )
    # Number grid font — Input Sans (the show's MDR font) fallback chain
    GRID_FONT = "'Input Sans','SF Mono','Consolas','DejaVu Sans Mono',monospace"
    # UI font — Forma DJR (the show's UI font) fallback chain
    UI_FONT = "'Forma DJR','Helvetica Neue','Helvetica','Arial',sans-serif"

    # ── CSS ──
    delay_css = "\n".join(
        f"        .t{str(b).replace('.','_')}{{animation-delay:-{b}s}}"
        for b in sorted(delay_buckets)
    )
    o.append("<style>")
    o.append(f"""
        .bg{{fill:{t['bg']}}}
        .n{{font-family:{GRID_FONT};font-size:{FS_NUM}px;
            font-weight:400;text-anchor:middle;
            transform-box:fill-box;transform-origin:center}}
        .d0{{fill:{t['num_colors'][0]};opacity:.6}}
        .d1{{fill:{t['num_colors'][1]};opacity:.72}}
        .d2{{fill:{t['num_colors'][2]};opacity:.84}}
        .d3{{fill:{t['num_colors'][3]};opacity:.95}}
        @keyframes sb{{0%,{SWELL_WINDOW_PCT}%,100%{{transform:scale(1)}}
            {SWELL_PEAK_PCT}%{{transform:scale(3.2)}}}}
        @keyframes ss{{0%,{SWELL_WINDOW_PCT}%,100%{{transform:scale(1)}}
            {SWELL_PEAK_PCT}%{{transform:scale(2.0)}}}}
        .sb{{animation-name:sb;animation-duration:{CURSOR_DUR}s;
            animation-timing-function:linear;animation-iteration-count:infinite}}
        .ss{{animation-name:ss;animation-duration:{CURSOR_DUR}s;
            animation-timing-function:linear;animation-iteration-count:infinite}}
{delay_css}
        @keyframes bounce{{
            0%,100%{{transform:translateY(0)}}
            50%{{transform:translateY(-2px)}}
        }}
        @keyframes wiggle{{
            0%,100%{{transform:translateX(0)}}
            25%{{transform:translateX(-1.5px)}}
            75%{{transform:translateX(1.5px)}}
        }}
        @keyframes jitter{{
            0%,100%{{transform:translate(0,0)}}
            25%{{transform:translate(1px,-1px)}}
            50%{{transform:translate(-1px,0.5px)}}
            75%{{transform:translate(0.5px,1px)}}
        }}
        .b1{{animation:bounce 3s ease-in-out infinite}}
        .b2{{animation:bounce 4.2s ease-in-out .8s infinite}}
        .b3{{animation:bounce 5.5s ease-in-out 1.6s infinite}}
        .w1{{animation:wiggle 2.8s ease-in-out infinite}}
        .w2{{animation:wiggle 4s ease-in-out 1s infinite}}
        .w3{{animation:wiggle 5s ease-in-out 2s infinite}}
        .j1{{animation:jitter 3.5s ease-in-out infinite}}
        .j2{{animation:jitter 4.8s ease-in-out 1.4s infinite}}
        @keyframes cur{{{" ".join(cursor_kf)}}}
        .cur{{animation:cur {CURSOR_DUR}s linear infinite}}
        .pb{{fill:{t['panel_bg']};fill-opacity:{t['panel_opacity']}}}
        .ps{{stroke:{t['panel_border']};stroke-width:2;fill:none}}
        .tt{{fill:{t['title']};font-family:{UI_FONT};font-weight:600;
            letter-spacing:6px;text-transform:uppercase}}
        .sn{{fill:{t['stat_num']};font-family:{UI_FONT};font-weight:600}}
        .sl{{fill:{t['stat_label']};font-family:{UI_FONT};font-weight:500;
            font-size:10px;letter-spacing:2px;text-transform:uppercase}}
        .sr{{fill:{t['stat_range']};font-family:{UI_FONT};font-weight:400;
            font-size:9px;letter-spacing:1px}}
        .div{{stroke:{t['divider']};stroke-width:2}}
        @keyframes flicker{{
            0%,100%{{opacity:1}}
            92%{{opacity:1}}
            93%{{opacity:.97}}
            94%{{opacity:1}}
            97%{{opacity:.98}}
            98%{{opacity:1}}
        }}
        .crt{{animation:flicker 4s linear infinite}}
    """)
    o.append("</style></defs>")

    # ── Background ──
    o.append(f'<rect class="bg" width="{W}" height="{H}" rx="12"/>')

    # ── CRT wrapper — everything inside gets the flicker ──
    o.append('<g class="crt">')

    # ── Number grid — clipped to area above categories ──
    o.append('<g clip-path="url(#nc)">')
    for row in range(grid_rows):
        for col in range(grid_cols):
            x = round(col * CELL_W + CELL_W / 2, 1)
            y = round(row * CELL_H + CELL_H, 1)
            if y > H + 5:
                continue
            digit = random.randint(0, 9)

            boost = hotspot_boost(col, row)
            weights = [40, 30, 20, 10]
            if boost:
                for _ in range(boost):
                    weights = [max(0, w - 8) for w in weights[:2]] + \
                              [w + 8 for w in weights[2:]]
            dim = random.choices(["d0", "d1", "d2", "d3"], weights=weights)[0]

            swell = cell_swell.get((col, row))
            if swell:
                kind, bucket = swell
                bcls = f"t{str(bucket).replace('.', '_')}"
                o.append(
                    f'<text class="n {dim} {kind} {bcls}" '
                    f'x="{x}" y="{y}">{digit}</text>'
                )
            else:
                mot = ""
                r = random.random()
                if r < 0.15:
                    mot = f" b{random.randint(1, 3)}"
                elif r < 0.30:
                    mot = f" w{random.randint(1, 3)}"
                elif r < 0.38:
                    mot = f" j{random.randint(1, 2)}"
                o.append(
                    f'<text class="n {dim}{mot}" x="{x}" y="{y}">{digit}</text>'
                )
    o.append("</g>")

    # ── Divider + category background — rendered before panels/cursor ──
    o.append(
        f'<rect x="0" y="{divider_y}" width="{W}" height="{H - divider_y}" '
        f'fill="{t["bg"]}"/>'
    )
    o.append(
        f'<line x1="0" y1="{divider_y}" x2="{W}" y2="{divider_y}" '
        f'stroke="{t["bin_border"]}" stroke-width="3"/>'
    )

    # ── Cursor — simple arrow pointer, clipped above divider ──
    o.append(
        f'<g clip-path="url(#nc)">'
        f'<g class="cur">'
        f'<polygon points="0,0 0,18 6,13 12,13" '
        f'fill="{t["bg"]}" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>'
        f'</g></g>'
    )

    # ── Title panel ──
    _panel(o, title_y, title_h)
    o.append(
        f'<text class="tt" x="{cx}" y="{title_y + 28}" '
        f'text-anchor="middle" font-size="18">Hi there 👋</text>'
    )

    # ── Stats panel ──
    _panel(o, stats_y, stats_h)
    col_w = PANEL_W / 3
    left_x = PX + col_w / 2
    center_x = PX + col_w + col_w / 2
    right_x = PX + col_w * 2 + col_w / 2

    # Dividers
    o.append(
        f'<line class="div" x1="{PX + col_w}" y1="{stats_y + 12}" '
        f'x2="{PX + col_w}" y2="{stats_y + stats_h - 12}"/>'
    )
    o.append(
        f'<line class="div" x1="{PX + col_w * 2}" y1="{stats_y + 12}" '
        f'x2="{PX + col_w * 2}" y2="{stats_y + stats_h - 12}"/>'
    )

    # Center: Current Streak with dashed ring
    ring_r = 38
    ring_cy = stats_y + 70
    o.append(
        f'<circle cx="{center_x}" cy="{ring_cy}" r="{ring_r}" '
        f'stroke="{t["ring_stroke"]}" stroke-width="2.5" fill="none" '
        f'stroke-dasharray="6,4" opacity="0.7"/>'
    )
    o.append(
        f'<text class="sn" x="{center_x}" y="{ring_cy + 9}" '
        f'text-anchor="middle" font-size="28">{streak["current"]}</text>'
    )
    o.append(
        f'<text class="sl" x="{center_x}" y="{ring_cy + ring_r + 18}" '
        f'text-anchor="middle">Current Streak</text>'
    )
    cur_range = fmt_range(streak["current_start"], streak["current_end"])
    o.append(
        f'<text class="sr" x="{center_x}" y="{ring_cy + ring_r + 32}" '
        f'text-anchor="middle">{esc(cur_range)}</text>'
    )

    # Left: Total Contributions
    side_num_y = ring_cy + 4
    side_label_y = ring_cy + 22
    side_range_y = ring_cy + 36
    o.append(
        f'<text class="sn" x="{left_x}" y="{side_num_y}" '
        f'text-anchor="middle" font-size="26">{streak["total"]}</text>'
    )
    o.append(
        f'<text class="sl" x="{left_x}" y="{side_label_y}" '
        f'text-anchor="middle">Total Contributions</text>'
    )
    total_range = fmt_range(streak["total_start"], streak["total_end"])
    o.append(
        f'<text class="sr" x="{left_x}" y="{side_range_y}" '
        f'text-anchor="middle">{esc(total_range)}</text>'
    )

    # Right: Longest Streak
    o.append(
        f'<text class="sn" x="{right_x}" y="{side_num_y}" '
        f'text-anchor="middle" font-size="26">{streak["longest"]}</text>'
    )
    o.append(
        f'<text class="sl" x="{right_x}" y="{side_label_y}" '
        f'text-anchor="middle">Longest Streak</text>'
    )
    longest_range = fmt_range(streak["longest_start"], streak["longest_end"])
    o.append(
        f'<text class="sr" x="{right_x}" y="{side_range_y}" '
        f'text-anchor="middle">{esc(longest_range)}</text>'
    )

    # ── Language categories — two-tier: name box on top, pct bar below ──
    lang_pad = PX + 16
    lang_gap = 10
    avail = PANEL_W - 32
    col_w = (avail - lang_gap * (num_bins - 1)) / num_bins
    top_y = langs_y + 4
    bot_y = top_y + tier_h

    for i in range(num_bins):
        lang = langs[i]
        bx = lang_pad + i * (col_w + lang_gap)
        cx_col = bx + col_w / 2

        # Upper box — language name
        o.append(
            f'<rect x="{bx}" y="{top_y}" width="{col_w}" height="{tier_h}" '
            f'rx="1" fill="{t["bin_bg"]}" stroke="{t["bin_border"]}" stroke-width="1.5"/>'
        )
        o.append(
            f'<text style="fill:{t["bin_label"]};font-family:\'Forma DJR\',\'Helvetica Neue\',\'Helvetica\',\'Arial\',sans-serif;'
            f'font-weight:500;font-size:9px;letter-spacing:1px;text-transform:uppercase" '
            f'x="{cx_col}" y="{top_y + tier_h / 2 + 3}" text-anchor="middle">'
            f'{esc(lang["name"])}</text>'
        )

        # Lower box — percentage bar with fill + text
        o.append(
            f'<rect x="{bx}" y="{bot_y}" width="{col_w}" height="{tier_h}" '
            f'rx="1" fill="{t["bin_bg"]}" stroke="{t["bin_border"]}" stroke-width="1.5"/>'
        )
        fill_w = round(col_w * lang["pct"] / 100, 1)
        if fill_w > 0:
            o.append(
                f'<rect x="{bx}" y="{bot_y}" width="{fill_w}" height="{tier_h}" '
                f'rx="1" fill="{t["bin_fill"]}"/>'
            )
        o.append(
            f'<text style="fill:{t["bin_pct"]};font-family:\'Forma DJR\',\'Helvetica Neue\',\'Helvetica\',\'Arial\',sans-serif;'
            f'font-weight:500;font-size:10px;letter-spacing:1px" '
            f'x="{cx_col}" y="{bot_y + tier_h / 2 + 4}" '
            f'text-anchor="middle">{lang["pct"]}%</text>'
        )

    # ── Close CRT flicker wrapper ──
    o.append("</g>")

    # ── CRT scanlines overlay ──
    o.append(f'<rect width="{W}" height="{H}" fill="url(#sl)" rx="12"/>')

    # ── CRT vignette overlay ──
    o.append(f'<rect width="{W}" height="{H}" fill="url(#vig)" rx="12"/>')

    # ── CRT bezel — rounded screen edge ──
    o.append(
        f'<rect width="{W}" height="{H}" rx="12" fill="none" '
        f'stroke="#111" stroke-width="4"/>'
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
        random.seed(42)
        svg = build_svg(streak, langs, theme=theme)
        out = ASSETS / f"mdr-stats-{theme}.svg"
        out.write_text(svg)
        print(f"✓ Wrote {out} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()

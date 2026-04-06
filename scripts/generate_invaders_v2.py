#!/usr/bin/env python3
"""Generate a Space Invaders themed SVG with GitHub stats — v2.

Enhanced over v1 with:
- Lasers that actually hit and destroy aliens (pure CSS keyframes)
- Staggered kills with death flash + explosion particles
- New-wave respawn cycle (~15s loop)
- <use>-based sprites for dramatically smaller file size
- Smaller pixel art (PS=2) for a finer retro look
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
            "User-Agent": "invaders-stats",
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


# ── Pixel-art designs ──────────────────────────────────────────────
PS = 2  # pixel block size (finer than v1's 3)

def _mirror_design(rows):
    """Turn a list of half-row strings into (col, row) pairs.

    Each string represents one row; chars are columns from center outward.
    We mirror left and right to build the full sprite.
    """
    pts = []
    for r, row in enumerate(rows):
        w = len(row)
        for c, ch in enumerate(row):
            if ch == "#":
                pts.append((w - 1 - c, r))
                pts.append((w + c, r))
    return pts

ALIEN_A = _mirror_design([
    "..#..",
    ".#...",
    ".####",
    "##.##",
    "#####",
    ".#.#.",
    "#....",
    ".#...",
])

ALIEN_B = _mirror_design([
    "...#.",
    "..#..",
    ".####",
    "##.##",
    "#####",
    "..#..",
    ".#.#.",
    "#..#.",
])

ALIEN_C = _mirror_design([
    "..##.",
    ".####",
    "#####",
    "#.#.#",
    "#####",
    ".#.#.",
    "#.#.#",
    ".#..#",
])

SHIP_DESIGN = _mirror_design([
    "......#",
    ".....##",
    ".....##",
    ".######",
    "#######",
    "#######",
    "#######",
])

ALIEN_DESIGNS = [ALIEN_A, ALIEN_B, ALIEN_C]


# ── Animation constants ───────────────────────────────────────────
CYCLE_S = 15.0        # total animation loop
LASER_SPEED = 500     # px per second

# (row, col, hit_time_seconds) — pick aliens from different rows
KILLS = [
    (4, 3, 1.5),
    (3, 1, 3.5),
    (2, 2, 5.5),
    (1, 6, 7.5),
    (0, 5, 9.5),
]

# Particle scatter directions per kill
PARTICLE_DIRS = [(-14, -12), (12, -14), (-10, 10), (14, 8)]


# ── Themes ──────────────────────────────────────────────────────────
THEMES = {
    "dark": dict(
        bg="#0a0a1a",
        star_color="#ffffff",
        alien_row_colors=["#ff4444", "#ff8844", "#ffcc00", "#44ff44", "#44ccff"],
        ship_color="#33ff33",
        laser_color="#33ff33",
        panel_bg="rgba(0,0,0,0.75)",
        panel_border="#33ff33",
        title_color="#33ff33",
        stat_num="#ffffff",
        stat_label="#33ff33",
        stat_range="#22aa22",
        lang_bar_bg="#111122",
        lang_label="#aaaacc",
        lang_pct="#ffffff",
        divider="#1a331a",
        scanline_opacity="0.06",
        score_color="#ffffff",
        explosion_color="#ffff44",
        flash_color="#ffffff",
    ),
    "light": dict(
        bg="#e8eaf0",
        star_color="#8888aa",
        alien_row_colors=["#cc2222", "#cc6622", "#aa8800", "#228822", "#2266aa"],
        ship_color="#116611",
        laser_color="#116611",
        panel_bg="rgba(255,255,255,0.82)",
        panel_border="#116611",
        title_color="#116611",
        stat_num="#111122",
        stat_label="#226622",
        stat_range="#448844",
        lang_bar_bg="#d0d2d8",
        lang_label="#444466",
        lang_pct="#111122",
        divider="#99bb99",
        scanline_opacity="0.04",
        score_color="#111122",
        explosion_color="#ff8800",
        flash_color="#ffffff",
    ),
}


# ── SVG builder ─────────────────────────────────────────────────────
def build_svg(streak, langs, theme="dark"):
    t = THEMES[theme]
    random.seed(42)

    H = 620
    o = []                       # output lines
    a = o.append

    a(f'<svg xmlns="http://www.w3.org/2000/svg" '
      f'viewBox="0 0 {W} {H}" width="100%">')

    # ── layout constants ──
    alien_rows = 5
    aliens_per_row = 8
    alien_spacing_x = 72
    alien_spacing_y = 26
    grid_w = (aliens_per_row - 1) * alien_spacing_x
    grid_x0 = (W - grid_w) / 2
    alien_start_y = 20
    alien_w = 10 * PS       # sprite width  (20 px)
    alien_h = 8 * PS        # sprite height (16 px)
    ship_y = H - 48

    # Ship movement keyframes (matches CSS)
    ship_kf = [(0, 0), (25, W//3), (50, W//6), (75, -W//4), (100, 0)]

    def ship_x_at(pct):
        """Interpolate ship x offset at a given cycle percentage."""
        for j in range(len(ship_kf) - 1):
            p0, x0 = ship_kf[j]
            p1, x1 = ship_kf[j + 1]
            if p0 <= pct <= p1:
                f = (pct - p0) / (p1 - p0)
                return x0 + (x1 - x0) * f
        return 0

    # ── pre-compute kill geometry ──
    ship_base_cx = W / 2  # ship center x at rest
    kill_data = []
    for ki, (row, col, hit_t) in enumerate(KILLS):
        ay = alien_start_y + row * alien_spacing_y
        ax = grid_x0 + col * alien_spacing_x
        dist = ship_y - ay
        travel = dist / LASER_SPEED
        fire_t = max(0.0, hit_t - travel)
        fp = fire_t / CYCLE_S * 100
        # Where is the ship when this laser fires?
        fire_ship_x = ship_base_cx + ship_x_at(fp)
        kill_data.append(dict(
            i=ki, row=row, col=col,
            hit_t=hit_t, fire_t=fire_t,
            hp=hit_t / CYCLE_S * 100,
            fp=fp,
            ax=ax, ay=ay, dist=dist,
            lx=ax + alien_w / 2,  # laser fires straight up at alien's column
        ))
    killed_set = {(k["row"], k["col"]): k for k in kill_data}

    # ── CSS ──────────────────────────────────────────────────────────
    a("<style>")
    css_lines = []

    # row-slide keyframes
    slides = [
        ("slide-r1", -18, 18), ("slide-r2", 16, -16),
        ("slide-r3", -14, 14), ("slide-r4", 12, -12),
        ("slide-r5", -10, 10),
    ]
    for name, a0, a50 in slides:
        css_lines.append(
            f"@keyframes {name}{{0%,100%{{transform:translateX({a0}px)}}"
            f"50%{{transform:translateX({a50}px)}}}}"
        )

    # utility keyframes
    css_lines.append(
        "@keyframes twinkle{0%,100%{opacity:.3}50%{opacity:1}}"
    )
    # Ship moves to each alien's column, pauses to fire
    ship_base_cx = W / 2 - 7 * PS
    ship_kf_parts = [(0, 0)]
    sorted_kills = sorted(kill_data, key=lambda k: k["fp"])
    for k in sorted_kills:
        target_x = k["lx"] - (ship_base_cx + 7 * PS)
        arrive_pct = max(0.5, k["fp"] - 3)
        fire_end_pct = min(99, k["fp"] + 1.5)
        ship_kf_parts.append((arrive_pct, target_x))
        ship_kf_parts.append((k["fp"], target_x))  # hold at fire
        ship_kf_parts.append((fire_end_pct, target_x))  # hold after fire
    ship_kf_parts.append((100, 0))
    ship_kf_parts.sort(key=lambda x: x[0])
    ship_kf_str = "".join(
        f"{p:.1f}%{{transform:translateX({x:.0f}px)}}" for p, x in ship_kf_parts
    )
    css_lines.append(f"@keyframes ship-move{{{ship_kf_str}}}")
    css_lines.append(
        "@keyframes score-blink{0%,100%{opacity:1}50%{opacity:.6}}"
    )

    # row-slide classes
    durations = [4, 3.5, 4.5, 3.8, 5]
    for ri in range(5):
        css_lines.append(
            f".alien-r{ri+1}{{animation:slide-r{ri+1} {durations[ri]}s "
            f"ease-in-out infinite}}"
        )

    css_lines.append(f".ship{{animation:ship-move {CYCLE_S}s ease-in-out infinite}}")
    css_lines.append(".star{animation:twinkle 3s ease-in-out infinite}")

    # ── per-kill keyframes ──
    for k in kill_data:
        hp = k["hp"]
        fp = k["fp"]
        dist = k["dist"]

        # alien death (opacity only — reliable across renderers)
        pre   = max(0, hp - 1.5)
        flash = hp
        gone  = min(99, hp + 2)
        css_lines.append(
            f"@keyframes die-{k['i']}{{"
            f"0%,{pre:.1f}%{{opacity:1}}"
            f"{flash:.1f}%{{opacity:1}}"
            f"{min(99, flash+0.5):.1f}%{{opacity:0}}"
            f"{gone:.1f}%,80%{{opacity:0}}"
            f"90%{{opacity:.4}}"
            f"100%{{opacity:1}}}}"
        )
        css_lines.append(
            f".die-{k['i']}{{animation:die-{k['i']} {CYCLE_S}s "
            f"ease-in-out infinite}}"
        )

        # flash overlay (bright white rect appears at hit moment)
        css_lines.append(
            f"@keyframes flash-{k['i']}{{"
            f"0%,{max(0,hp-0.5):.1f}%{{opacity:0}}"
            f"{hp:.1f}%{{opacity:.85}}"
            f"{min(99,hp+2):.1f}%{{opacity:0}}"
            f"{min(99,hp+2.5):.1f}%,100%{{opacity:0}}}}"
        )
        css_lines.append(
            f".flash-{k['i']}{{animation:flash-{k['i']} {CYCLE_S}s "
            f"ease-in-out infinite}}"
        )

        # laser beam — fires straight up from alien's column
        pre_f = max(0, fp - 0.5)
        post_h = min(99, hp + 0.5)
        css_lines.append(
            f"@keyframes lzr-{k['i']}{{"
            f"0%,{pre_f:.1f}%{{opacity:0;transform:translateY(0)}}"
            f"{fp:.1f}%{{opacity:1;transform:translateY(0)}}"
            f"{hp:.1f}%{{opacity:1;transform:translateY(-{dist:.0f}px)}}"
            f"{post_h:.1f}%,100%{{opacity:0;transform:translateY(-{dist:.0f}px)}}}}"
        )
        css_lines.append(
            f".lzr-{k['i']}{{animation:lzr-{k['i']} {CYCLE_S}s linear infinite}}"
        )

        # explosion particles (4 per kill)
        for pi, (dx, dy) in enumerate(PARTICLE_DIRS):
            start = hp
            end = min(99, hp + 7)
            post = min(99, hp + 8)
            css_lines.append(
                f"@keyframes exp-{k['i']}-{pi}{{"
                f"0%,{start:.1f}%{{opacity:0;transform:translate(0,0)}}"
                f"{min(99,start+0.3):.1f}%{{opacity:1;transform:translate(0,0)}}"
                f"{end:.1f}%{{opacity:0;transform:translate({dx}px,{dy}px)}}"
                f"{post:.1f}%,100%{{opacity:0}}}}"
            )

    # panel & font
    css_lines.append(
        f".panel{{fill:{t['panel_bg']};stroke:{t['panel_border']};"
        f"stroke-width:1.5;rx:4}}"
    )
    css_lines.append(
        ".pixel-font{font-family:'Courier New','Lucida Console',monospace;"
        "font-weight:bold}"
    )

    a("\n".join(css_lines))
    a("</style>")

    # ── Defs ─────────────────────────────────────────────────────────
    a("<defs>")
    a(f'<clipPath id="frame"><rect width="{W}" height="{H}" rx="10"/></clipPath>')
    a(f'<pattern id="scanlines" width="2" height="4" '
      f'patternUnits="userSpaceOnUse">'
      f'<rect width="2" height="1" fill="black" '
      f'opacity="{t["scanline_opacity"]}"/></pattern>')

    # alien sprites (defined once, referenced via <use>)
    for di, design in enumerate(ALIEN_DESIGNS):
        sid = f"a{chr(97+di)}"
        a(f'<g id="{sid}">')
        for (px, py) in design:
            a(f'<rect x="{px*PS}" y="{py*PS}" width="{PS}" height="{PS}"/>')
        a("</g>")

    # ship sprite
    a('<g id="sp">')
    for (px, py) in SHIP_DESIGN:
        a(f'<rect x="{px*PS}" y="{py*PS}" width="{PS}" height="{PS}"/>')
    a("</g>")

    a("</defs>")

    # ── Background ───────────────────────────────────────────────────
    a(f'<g clip-path="url(#frame)">')
    a(f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>')

    # ── Stars ────────────────────────────────────────────────────────
    for _ in range(50):
        sx, sy = random.randint(0, W), random.randint(0, H)
        sr = random.choice([1, 1, 1.5])
        dl = round(random.uniform(0, 5), 1)
        dr = round(random.uniform(2, 5), 1)
        a(f'<circle class="star" cx="{sx}" cy="{sy}" r="{sr}" '
          f'fill="{t["star_color"]}" opacity=".5" '
          f'style="animation-delay:{dl}s;animation-duration:{dr}s"/>')

    # ── Alien grid ───────────────────────────────────────────────────
    row_colors = t["alien_row_colors"]
    for ri in range(alien_rows):
        di = ri % len(ALIEN_DESIGNS)
        sid = f"a{chr(97+di)}"
        color = row_colors[ri % len(row_colors)]
        ry = alien_start_y + ri * alien_spacing_y

        a(f'<g class="alien-r{ri+1}">')
        for ci in range(aliens_per_row):
            ax = grid_x0 + ci * alien_spacing_x
            kd = killed_set.get((ri, ci))
            if kd:
                # killed alien: wrapped in die-animation element
                a(f'<g class="die-{kd["i"]}">'
                  f'<use href="#{sid}" x="{ax}" y="{ry}" '
                  f'fill="{color}" opacity=".92"/></g>')
                # flash overlay
                a(f'<rect class="flash-{kd["i"]}" '
                  f'x="{ax}" y="{ry}" width="{alien_w}" height="{alien_h}" '
                  f'fill="{t["flash_color"]}" rx="2" opacity="0"/>')
                # explosion particles
                pcx = ax + alien_w / 2
                pcy = ry + alien_h / 2
                for pi in range(len(PARTICLE_DIRS)):
                    a(f'<rect x="{pcx-1}" y="{pcy-1}" width="3" height="3" '
                      f'fill="{t["explosion_color"]}" opacity="0" '
                      f'style="animation:exp-{kd["i"]}-{pi} '
                      f'{CYCLE_S}s linear infinite"/>')
            else:
                a(f'<use href="#{sid}" x="{ax}" y="{ry}" '
                  f'fill="{color}" opacity=".92"/>')
        a("</g>")

    # ── Player ship ──────────────────────────────────────────────────
    ship_cx = W / 2 - 7 * PS
    a(f'<g class="ship">'
      f'<use href="#sp" x="{ship_cx}" y="{ship_y}" '
      f'fill="{t["ship_color"]}"/></g>')

    # ── Lasers — positioned at ship's x when fired, go straight up ──
    for k in kill_data:
        a(f'<rect class="lzr-{k["i"]}" x="{k["lx"]-1}" y="{ship_y}" '
          f'width="2" height="12" fill="{t["laser_color"]}" rx="1" '
          f'opacity="0"/>')

    # ── Score header — increments as aliens die ──
    base_score = streak["total"]
    points_per_kill = 100
    sorted_by_hit = sorted(kill_data, key=lambda k: k["hp"])
    # Score layers: each appears at a kill time and hides at the next
    for si, k in enumerate(sorted_by_hit):
        score_val = base_score + (si + 1) * points_per_kill
        show_pct = k["hp"]
        if si + 1 < len(sorted_by_hit):
            hide_pct = sorted_by_hit[si + 1]["hp"]
        else:
            # Last score stays until reset
            hide_pct = 80  # then base score reappears
        css_lines.append(
            f"@keyframes sc{si}{{0%,{max(0,show_pct-0.5):.1f}%{{opacity:0}}"
            f"{show_pct:.1f}%{{opacity:1}}"
            f"{hide_pct:.1f}%{{opacity:1}}"
            f"{min(99,hide_pct+0.5):.1f}%,100%{{opacity:0}}}}"
        )
        css_lines.append(f".sc{si}{{animation:sc{si} {CYCLE_S}s linear infinite}}")
        a(f'<text class="pixel-font sc{si}" x="15" y="16" font-size="11" '
          f'fill="{t["score_color"]}" opacity="0">'
          f'SCORE  {score_val:,}</text>')
    # Base score (visible before first kill and after reset)
    first_hp = sorted_by_hit[0]["hp"] if sorted_by_hit else 100
    css_lines.append(
        f"@keyframes sc-base{{0%{{opacity:1}}"
        f"{max(0,first_hp-0.5):.1f}%{{opacity:1}}"
        f"{first_hp:.1f}%{{opacity:0}}"
        f"80%{{opacity:0}}82%{{opacity:1}}100%{{opacity:1}}}}"
    )
    css_lines.append(f".sc-base{{animation:sc-base {CYCLE_S}s linear infinite}}")
    a(f'<text class="pixel-font sc-base" x="15" y="16" font-size="11" '
      f'fill="{t["score_color"]}">'
      f'SCORE  {base_score:,}</text>')
    a(f'<text class="pixel-font" x="{W-15}" y="16" font-size="11" '
      f'fill="{t["score_color"]}" opacity=".7" text-anchor="end">'
      f'HI-SCORE  {streak["total"]:,}</text>')

    # ── Stats panels ─────────────────────────────────────────────────
    panel_w = 560
    panel_x = (W - panel_w) / 2

    # title panel
    title_y = 175
    title_h = 35
    a(f'<rect class="panel" x="{panel_x}" y="{title_y}" '
      f'width="{panel_w}" height="{title_h}"/>')
    a(f'<text class="pixel-font" x="{W/2}" y="{title_y+23}" '
      f'font-size="16" fill="{t["title_color"]}" text-anchor="middle">'
      f'Hi there 👋</text>')

    # streak stats panel
    stats_y = title_y + title_h + 10
    stats_h = 120
    a(f'<rect class="panel" x="{panel_x}" y="{stats_y}" '
      f'width="{panel_w}" height="{stats_h}"/>')

    col_w = panel_w / 3
    stat_items = [
        ("CURRENT STREAK", str(streak["current"]),
         fmt_range(streak["current_start"], streak["current_end"])),
        ("TOTAL CONTRIBS", f'{streak["total"]:,}',
         fmt_range(streak["total_start"], streak["total_end"])),
        ("LONGEST STREAK", str(streak["longest"]),
         fmt_range(streak["longest_start"], streak["longest_end"])),
    ]
    for i, (label, value, rng) in enumerate(stat_items):
        cx = panel_x + col_w * i + col_w / 2
        a(f'<text class="pixel-font" x="{cx}" y="{stats_y+40}" '
          f'font-size="28" fill="{t["stat_num"]}" text-anchor="middle">'
          f'{esc(value)}</text>')
        a(f'<text class="pixel-font" x="{cx}" y="{stats_y+60}" '
          f'font-size="9" fill="{t["stat_label"]}" text-anchor="middle">'
          f'{esc(label)}</text>')
        if rng:
            a(f'<text class="pixel-font" x="{cx}" y="{stats_y+76}" '
              f'font-size="7" fill="{t["stat_range"]}" text-anchor="middle">'
              f'{esc(rng)}</text>')
        if i < 2:
            dx = panel_x + col_w * (i + 1)
            a(f'<line x1="{dx}" y1="{stats_y+12}" x2="{dx}" '
              f'y2="{stats_y+stats_h-12}" '
              f'stroke="{t["divider"]}" stroke-width="1" opacity=".4"/>')

    # decorative dots
    dot_y = stats_y + 90
    for i in range(3):
        cx = panel_x + col_w * i + col_w / 2
        for dx in range(-2, 3):
            a(f'<rect x="{cx+dx*6-1}" y="{dot_y}" width="3" height="3" '
              f'fill="{t["stat_label"]}" opacity=".3" rx=".5"/>')

    # ── Languages panel ──────────────────────────────────────────────
    langs_y = stats_y + stats_h + 10
    n_langs = min(len(langs), 5)
    langs_h = 30 + n_langs * 22 + 10
    a(f'<rect class="panel" x="{panel_x}" y="{langs_y}" '
      f'width="{panel_w}" height="{langs_h}"/>')
    a(f'<text class="pixel-font" x="{panel_x+15}" y="{langs_y+18}" '
      f'font-size="10" fill="{t["stat_label"]}">TOP LANGUAGES</text>')

    bar_max_w = panel_w - 160
    for i, lang in enumerate(langs[:5]):
        ly = langs_y + 30 + i * 22
        a(f'<text class="pixel-font" x="{panel_x+15}" y="{ly+11}" '
          f'font-size="9" fill="{t["lang_label"]}">{esc(lang["name"])}</text>')
        bar_x = panel_x + 110
        a(f'<rect x="{bar_x}" y="{ly+1}" width="{bar_max_w}" height="12" '
          f'fill="{t["lang_bar_bg"]}" rx="2"/>')
        fill_w = max(4, bar_max_w * lang["pct"] / 100)
        a(f'<rect x="{bar_x}" y="{ly+1}" width="{fill_w:.1f}" height="12" '
          f'fill="{lang["color"]}" rx="2" opacity=".85"/>')
        a(f'<text class="pixel-font" x="{panel_x+panel_w-12}" y="{ly+11}" '
          f'font-size="9" fill="{t["lang_pct"]}" text-anchor="end">'
          f'{lang["pct"]}%</text>')

    # ── Scanline overlay ─────────────────────────────────────────────
    a(f'<rect width="{W}" height="{H}" fill="url(#scanlines)" opacity=".5"/>')

    # ── Border ───────────────────────────────────────────────────────
    a(f'<rect width="{W}" height="{H}" rx="10" fill="none" '
      f'stroke="{t["panel_border"]}" stroke-width="2" opacity=".5"/>')

    a("</g>")
    a("</svg>")
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
        out = ASSETS / f"space-invaders-{theme}.svg"
        out.write_text(svg)
        print(f"✓ Wrote {out} ({len(svg)} bytes)")


if __name__ == "__main__":
    # Generate test SVGs with mock data
    streak = dict(
        total=2456, total_start='2019-06-15', total_end='2026-04-05',
        current=15, current_start='2026-03-22', current_end='2026-04-05',
        longest=42, longest_start='2024-11-01', longest_end='2024-12-12',
    )
    langs = [
        dict(name='Python', pct=35.2, color='#3572A5'),
        dict(name='TypeScript', pct=22.1, color='#3178c6'),
        dict(name='Go', pct=18.4, color='#00ADD8'),
        dict(name='Rust', pct=12.8, color='#dea584'),
        dict(name='Shell', pct=11.5, color='#89e051'),
    ]

    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        random.seed(42)
        svg = build_svg(streak, langs, theme=theme)
        out = ASSETS / f"space-invaders-{theme}.svg"
        out.write_text(svg)
        print(f"✓ Wrote {out} ({len(svg)} bytes)")

#!/usr/bin/env python3
"""Draw assets/city.svg and assets/character.svg from your public GitHub repos.

Run once a day by .github/workflows/profile.yml. Standard library only.

  city.svg       every repo is a building: taller = more commits, brighter windows = pushed recently
  character.svg  RPG character sheet: level and XP from commits, repos and stars

Local test without the GitHub API:
    python3 scripts/build_profile.py --from-json repos.json
where repos.json is a list of {"name", "pushedAt", "commits", "stars", "languages": {name: bytes}}.
"""
import datetime
import html
import json
import math
import os
import random
import sys
import urllib.request
import zlib

# ---------- things you can edit ----------
DISPLAY_NAME = "AERO SCISSORS"
CLASS_NAME = "Backend Mage · ML multiclass"
INVENTORY = ["Python", "FastAPI", "Flask", "scikit-learn", "Docker", "Ollama", "JavaScript", "Git"]
# -----------------------------------------

OWNER = os.environ.get("OWNER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "AeroScissors"
TOKEN = os.environ.get("GITHUB_TOKEN")
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
MUTED, LINE, CYAN, VIOLET, GREEN, AMBER, RED = "#8792a8", "#2a3558", "#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#f87171"

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        pushedAt
        stargazerCount
        languages(first: 6, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
        defaultBranchRef { target { ... on Commit { history { totalCount } } } }
      }
    }
  }
}
"""


def fetch_repos():
    if not TOKEN:
        sys.exit("GITHUB_TOKEN is not set.")
    body = json.dumps({"query": QUERY, "variables": {"login": OWNER}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
        "User-Agent": f"{OWNER}-profile-city"})
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.load(res)
    if data.get("errors"):
        sys.exit(f"GitHub API error: {data['errors']}")
    repos = []
    for n in data["data"]["user"]["repositories"]["nodes"]:
        if n["name"].lower() == OWNER.lower():
            continue  # skip this profile repo itself
        ref = n.get("defaultBranchRef") or {}
        commits = ((ref.get("target") or {}).get("history") or {}).get("totalCount", 0)
        if not commits:
            continue  # empty repo
        repos.append({
            "name": n["name"], "pushedAt": n["pushedAt"], "stars": n.get("stargazerCount", 0), "commits": commits,
            "languages": {e["node"]["name"]: e["size"] for e in (n.get("languages") or {}).get("edges", [])},
        })
    return repos


# ---------- helpers ----------

def esc(s):
    return html.escape(str(s), quote=False)


def clip(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


def days_since(iso):
    d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.datetime.now(datetime.timezone.utc) - d).days


def pts(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def quad(points):
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points) + "Z"


# ---------- city ----------

W, H = 1000, 480
TW, TH, OX, OY = 140, 56, 395, 205           # isometric tile size and origin
COLS, ROWS = 6, 3                            # 18 plots
PALETTES = [("#16224a", "#22326a", "#2f4288"), ("#231c4f", "#33287a", "#44369c"),
            ("#123543", "#1a4c5f", "#24667d"), ("#3a1d4a", "#522a69", "#6b3888")]


def iso(gx, gy, z=0.0):
    return (OX + (gx - gy) * TW / 2, OY + (gx + gy) * TH / 2 - z)


def lit_ratio(days):
    for limit, ratio in ((14, .78), (60, .52), (180, .3), (365, .15)):
        if days <= limit:
            return ratio
    return .06


def building(repo, gx, gy, h, is_newest, is_tallest):
    rng = random.Random(zlib.crc32(repo["name"].encode()))
    dark, mid, light = PALETTES[rng.randrange(len(PALETTES))]
    m = .13
    x0, x1, y0, y1 = gx + m, gx + 1 - m, gy + m, gy + 1 - m
    out = [f'<polygon points="{pts([iso(x0, y1), iso(x1, y1), iso(x1, y1, h), iso(x0, y1, h)])}" fill="{dark}"/>',
           f'<polygon points="{pts([iso(x1, y1), iso(x1, y0), iso(x1, y0, h), iso(x1, y1, h)])}" fill="{mid}"/>',
           f'<polygon points="{pts([iso(x0, y0, h), iso(x1, y0, h), iso(x1, y1, h), iso(x0, y1, h)])}" fill="{light}"/>']
    ratio = lit_ratio(days_since(repo["pushedAt"]))
    off, on, flick = [], [], []
    for (ax, ay), (bx, by) in (((x0, y1), (x1, y1)), ((x1, y1), (x1, y0))):
        for r in range(int((h - 14) // 15)):
            z0 = 8 + r * 15
            for c in range(3):
                u0, u1 = .12 + c * .28, .30 + c * .28
                p = lambda u, z: iso(ax + (bx - ax) * u, ay + (by - ay) * u, z)
                d = quad([p(u0, z0), p(u1, z0), p(u1, z0 + 9), p(u0, z0 + 9)])
                if rng.random() < ratio:
                    (flick if rng.random() < .12 else on).append(d)
                else:
                    off.append(d)
    if off:
        out.append(f'<path d="{"".join(off)}" fill="#0b1228" opacity=".55"/>')
    if on:
        out.append(f'<path d="{"".join(on)}" fill="#ffd978"/>')
    for d in flick:
        out.append(f'<path d="{d}" fill="#ffe9a8"><animate attributeName="opacity" values="1;.15;1;1" keyTimes="0;.1;.2;1" '
                   f'dur="{rng.uniform(3, 8):.1f}s" begin="{rng.uniform(0, 4):.1f}s" repeatCount="indefinite"/></path>')
    cx, cy = iso((x0 + x1) / 2, (y0 + y1) / 2, h)
    top = cy
    if is_newest:   # construction crane on the repo you pushed to most recently
        out.append(f'<g stroke="{AMBER}" stroke-width="2" stroke-linecap="round" fill="none">'
                   f'<path d="M{cx:.1f} {cy:.1f} v-34 M{cx - 12:.1f} {cy - 34:.1f} h46"/>'
                   f'<g><path d="M{cx + 30:.1f} {cy - 34:.1f} v16"/><rect x="{cx + 26:.1f}" y="{cy - 18:.1f}" width="8" height="6" fill="{AMBER}" stroke="none"/>'
                   f'<animateTransform attributeName="transform" type="rotate" values="-7 {cx + 30:.1f} {cy - 34:.1f};7 {cx + 30:.1f} {cy - 34:.1f};-7 {cx + 30:.1f} {cy - 34:.1f}" dur="3s" repeatCount="indefinite"/></g></g>')
        top = cy - 38
    elif is_tallest:  # antenna with a beacon on the repo with the most commits
        out.append(f'<path d="M{cx:.1f} {cy:.1f} v-26" stroke="#9aa6c4" stroke-width="2"/>'
                   f'<circle cx="{cx:.1f}" cy="{cy - 28:.1f}" r="3.5" fill="{RED}"><animate attributeName="opacity" values="1;.15;1" dur="1.6s" repeatCount="indefinite"/></circle>')
        top = cy - 34
    return "".join(out), (cx, cy, top)


def park(gx, gy):
    rng = random.Random(gx * 31 + gy * 7)
    out = []
    for _ in range(3):
        x, y = iso(gx + rng.uniform(.25, .75), gy + rng.uniform(.25, .75))
        out.append(f'<path d="M{x:.1f} {y:.1f} v-9" stroke="#3b2a1c" stroke-width="2"/>'
                   f'<circle cx="{x:.1f}" cy="{y - 13:.1f}" r="{rng.uniform(6, 9):.1f}" fill="{rng.choice(["#14432f", "#1b5a3d", "#17503a"])}"/>')
    return "".join(out)


def render_city(repos):
    repos = sorted(repos, key=lambda r: r["pushedAt"], reverse=True)[: COLS * ROWS]
    n = len(repos)
    total_commits = sum(r["commits"] for r in repos)
    top_commits = max((r["commits"] for r in repos), default=1)
    newest = repos[0]["name"] if repos else None
    tallest = max(repos, key=lambda r: r["commits"])["name"] if repos else None

    # Plots from back to front; spread the buildings out and put the tallest at the back.
    plots = sorted(((gx, gy) for gx in range(COLS) for gy in range(ROWS)), key=lambda p: (p[0] + p[1], p[0]))
    picks = [round(i * (len(plots) - 1) / max(n - 1, 1)) for i in range(n)] if n > 1 else [len(plots) // 2][:n]
    by_height = sorted(repos, key=lambda r: r["commits"], reverse=True)
    placed = {plots[i]: r for i, r in zip(picks, by_height)}

    rng = random.Random(42)
    sky = []
    for _ in range(70):
        x, y, r = rng.uniform(0, W), rng.uniform(6, 200), rng.uniform(.5, 1.4)
        tw = (f'<animate attributeName="opacity" values="1;.2;1" dur="{rng.uniform(2, 5):.1f}s" begin="{rng.uniform(0, 3):.1f}s" repeatCount="indefinite"/>'
              if rng.random() < .25 else "")
        sky.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#fff" opacity="{rng.uniform(.3, .9):.2f}">{tw}</circle>')
    skyline = []
    for base, color, lo, hi in ((318, "#131c44", 40, 130), (330, "#18234f", 20, 80)):
        x = -10
        while x < W:
            w, h = rng.randrange(26, 60), rng.randrange(lo, hi)
            skyline.append(f'<rect x="{x}" y="{base - h}" width="{w}" height="{h + 160}" fill="{color}"/>')
            for _ in range(rng.randrange(0, 4)):
                skyline.append(f'<rect x="{x + rng.randrange(4, w - 6)}" y="{base - h + rng.randrange(6, max(h - 6, 8))}" width="3" height="4" fill="#ffd978" opacity=".35"/>')
            x += w + rng.randrange(0, 8)

    a, b, c, d = iso(0, 0), iso(COLS, 0), iso(COLS, ROWS), iso(0, ROWS)
    slab = 16
    ground = [f'<polygon points="{pts([d, c, (c[0], c[1] + slab), (d[0], d[1] + slab)])}" fill="#070b18"/>',
              f'<polygon points="{pts([c, b, (b[0], b[1] + slab), (c[0], c[1] + slab)])}" fill="#0a1022"/>',
              f'<polygon points="{pts([a, b, c, d])}" fill="#0e1736" stroke="{LINE}" stroke-width="1.5"/>']
    for i in range(1, COLS):
        ground.append(f'<line x1="{iso(i, 0)[0]:.1f}" y1="{iso(i, 0)[1]:.1f}" x2="{iso(i, ROWS)[0]:.1f}" y2="{iso(i, ROWS)[1]:.1f}" stroke="#fff" stroke-opacity=".06"/>')
    for j in range(1, ROWS):
        ground.append(f'<line x1="{iso(0, j)[0]:.1f}" y1="{iso(0, j)[1]:.1f}" x2="{iso(COLS, j)[0]:.1f}" y2="{iso(COLS, j)[1]:.1f}" stroke="#fff" stroke-opacity=".06"/>')

    body, roofs = [], {}
    for plot in plots:
        gx, gy = plot
        if plot in placed:
            r = placed[plot]
            h = 34 + 116 * math.log1p(r["commits"]) / math.log1p(top_commits)
            svg, roof = building(r, gx, gy, h, r["name"] == newest, r["name"] == tallest and r["name"] != newest)
            body.append(svg)
            roofs[r["name"]] = roof
        else:
            body.append(park(gx, gy))

    cars = []
    for (p, q, dur, color) in ((iso(.1, ROWS - .04), iso(COLS - .1, ROWS - .04), 9, "#ffe9a8"), (iso(COLS - .04, .1), iso(COLS - .04, ROWS - .1), 7, RED)):
        cars.append(f'<circle r="2.6" fill="{color}"><animateMotion dur="{dur}s" repeatCount="indefinite" path="M{p[0]:.1f} {p[1]:.1f} L{q[0]:.1f} {q[1]:.1f}"/></circle>')

    # Name tags for the most recently pushed repos, nudged upward until they stop overlapping.
    labels, boxes = [], []
    for r in repos[:6]:
        cx, cy, top = roofs[r["name"]]
        name = clip(r["name"], 22)
        w = len(name) * 6.7 + 14
        y = top - 12
        while any(abs(cx - bx) < (w + bw) / 2 + 4 and abs(y - by) < 19 for bx, by, bw in boxes):
            y -= 19
        boxes.append((cx, y, w))
        hot = r["name"] == newest
        labels.append(f'<path d="M{cx:.1f} {top:.1f} V{y + 8:.1f}" stroke="#fff" stroke-opacity=".35"/>'
                      f'<rect x="{cx - w / 2:.1f}" y="{y - 9:.1f}" width="{w:.1f}" height="18" rx="9" fill="#070b18" fill-opacity=".85" stroke="{AMBER if hot else LINE}"/>'
                      f'<text x="{cx:.1f}" y="{y + 4:.1f}" font-size="11" text-anchor="middle" fill="{AMBER if hot else "#dbe3f3"}">{esc(name)}</text>')

    plane_path = "M -60 150 C 240 70, 700 50, 1060 120"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="A night city where each building is one of my repositories. Taller buildings have more commits and brighter windows mean a more recent push. {n} repos, {total_commits} commits.">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#060914"/><stop offset=".7" stop-color="#101a3d"/><stop offset="1" stop-color="#1b2a5c"/></linearGradient>
    <linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="420" y2="0" spreadMethod="repeat">
      <stop offset="0" stop-color="{CYAN}"/><stop offset=".5" stop-color="#c4b5fd"/><stop offset="1" stop-color="{CYAN}"/>
      <animateTransform attributeName="gradientTransform" type="translate" from="0 0" to="420 0" dur="5s" repeatCount="indefinite"/>
    </linearGradient>
    <clipPath id="frame"><rect width="{W}" height="{H}" rx="20"/></clipPath>
  </defs>
  <g clip-path="url(#frame)" font-family="{MONO}">
    <rect width="{W}" height="{H}" fill="url(#sky)"/>
    {"".join(sky)}
    <circle cx="905" cy="72" r="44" fill="#f4f1de" opacity=".07"/><circle cx="905" cy="72" r="24" fill="#f4f1de"/><circle cx="897" cy="66" r="5" fill="#d9d5bd"/><circle cx="912" cy="80" r="3.5" fill="#d9d5bd"/>
    <g>
      <path d="M 14 0 L -14 -9 L -8 0 L -14 9 Z" fill="#dbe3f3"/>
      <circle cx="-10" cy="0" r="2.2" fill="{RED}"><animate attributeName="opacity" values="1;0;1" dur=".9s" repeatCount="indefinite"/></circle>
      <animateMotion dur="18s" repeatCount="indefinite" rotate="auto" path="{plane_path}"/>
    </g>
    {"".join(skyline)}
    <rect y="330" width="{W}" height="{H - 330}" fill="#080c1a" opacity=".55"/>
    {"".join(ground)}
    {"".join(cars)}
    {"".join(body)}
    {"".join(labels)}
    <text x="40" y="{H - 50}" font-family="{SANS}" font-weight="800" font-size="30" letter-spacing="2" fill="url(#shine)">{esc(DISPLAY_NAME)}</text>
    <text x="41" y="{H - 26}" font-size="13" fill="{MUTED}">commit city · {n} repos · {total_commits:,} commits</text>
    <g font-size="11.5" fill="{MUTED}" text-anchor="end">
      <text x="962" y="{H - 58}">taller = more commits</text>
      <text x="962" y="{H - 41}">brighter = pushed recently</text>
      <text x="962" y="{H - 24}">crane = latest push</text>
    </g>
  </g>
  <rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="20" fill="none" stroke="{LINE}" stroke-width="1.5"/>
</svg>
'''


# ---------- character sheet ----------

SPRITE = [  # 16 x 16 pixel pilot; each letter is a colour below
    "................",
    ".....hhhhhh.....",
    "....hhhhhhhh....",
    "...hggggggggh...",
    "...hgwwggwwgh...",
    "...hgwwggwwgh...",
    "....ssssssss....",
    "....ssssssss....",
    ".....ssssss.....",
    "...jjjccccjjj...",
    "..jjjjjccjjjjj..",
    "..jsjjjjjjjjsj..",
    "..jsjjjjjjjjsj..",
    "....pppppppp....",
    "....ppp..ppp....",
    "...bbbb..bbbb...",
]
SPRITE_COLORS = {"h": "#7a4b24", "g": "#27304f", "w": "#8fd8ff", "s": "#e9bf95", "j": "#3654c9", "c": RED, "p": "#26335f", "b": "#9aa6c4"}


def level_from_xp(xp):
    level, need = 1, 100
    floor = 0
    while xp >= need:
        level += 1
        floor = need
        need += 100 * level
    return level, xp - floor, need - floor


def bar(x, y, w, frac, color, delay):
    fw = max(w * min(max(frac, 0), 1), 4)
    return (f'<rect x="{x}" y="{y}" width="{w}" height="10" rx="5" fill="#0b1228"/>'
            f'<rect x="{x}" y="{y}" width="{fw:.1f}" height="10" rx="5" fill="{color}">'
            f'<animate attributeName="width" from="0" to="{fw:.1f}" dur="1.1s" begin="{delay}s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/></rect>')


def render_character(repos):
    repos = sorted(repos, key=lambda r: r["pushedAt"], reverse=True)
    commits = sum(r["commits"] for r in repos)
    have_stars = all(r.get("stars") is not None for r in repos)
    stars = sum(r.get("stars") or 0 for r in repos)
    langs = {}
    for r in repos:
        for name, size in r.get("languages", {}).items():
            langs[name] = langs.get(name, 0) + size
    xp = commits * 10 + len(repos) * 40 + stars * 25
    level, into, span = level_from_xp(xp)

    px = 10
    sprite = "".join(f'<rect x="{c * px}" y="{r * px}" width="{px}" height="{px}" fill="{SPRITE_COLORS[ch]}"/>'
                     for r, row in enumerate(SPRITE) for c, ch in enumerate(row) if ch in SPRITE_COLORS)

    def head(x, y, t):
        return f'<text x="{x}" y="{y}" font-size="12" letter-spacing="3" fill="{CYAN}" font-weight="700">{t}</text>'

    stats = [("STR", "commits pushed", commits, math.log1p(commits) / math.log1p(1000), CYAN),
             ("DEX", "repos shipped", len(repos), math.log1p(len(repos)) / math.log1p(50), VIOLET),
             ("INT", "languages used", len(langs), len(langs) / 10, GREEN)]
    if have_stars:
        stats.append(("CHA", "stars earned", stars, math.log1p(stars) / math.log1p(100), AMBER))
    s = []
    for i, (code, cap, value, frac, color) in enumerate(stats):
        y = 104 + i * 34
        s.append(f'<text x="330" y="{y}" font-size="14" font-weight="700" fill="{color}">{code}</text>'
                 f'<text x="372" y="{y}" font-size="12" fill="{MUTED}">{cap}</text>'
                 f'{bar(490, y - 9, 100, frac, color, .3 + i * .12)}'
                 f'<text x="644" y="{y}" font-size="14" font-weight="700" fill="#f1f5fb" text-anchor="end">{value:,}</text>')
    total = sum(langs.values()) or 1
    for i, (name, size) in enumerate(sorted(langs.items(), key=lambda kv: -kv[1])[:4]):
        y = 292 + i * 30
        s.append(f'<text x="330" y="{y}" font-size="13" fill="#dbe3f3">{esc(clip(name, 17))}</text>'
                 f'{bar(490, y - 9, 100, size / total, CYAN, .8 + i * .12)}'
                 f'<text x="644" y="{y}" font-size="13" fill="{MUTED}" text-anchor="end">{round(100 * size / total)}%</text>')

    q = []
    if repos:
        q.append(f'<path d="M690 99 l7 -7 l7 7 l-7 7 z" fill="{AMBER}"><animate attributeName="opacity" values="1;.25;1" dur="1.4s" repeatCount="indefinite"/></path>'
                 f'<text x="712" y="104" font-size="14" font-weight="700" fill="{AMBER}">{esc(clip(repos[0]["name"], 24))}</text>'
                 f'<text x="712" y="121" font-size="11" fill="{MUTED}">active quest</text>')
    for i, r in enumerate(repos[1:5]):
        y = 150 + i * 24
        q.append(f'<path d="M691 {y - 5} l4 4 l8 -9" fill="none" stroke="{GREEN}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
                 f'<text x="712" y="{y}" font-size="13" fill="#dbe3f3">{esc(clip(r["name"], 26))}</text>')
    inv = []
    for i, item in enumerate(INVENTORY[:8]):
        x, y = 690 + (i % 2) * 140, 276 + (i // 2) * 34
        inv.append(f'<rect x="{x}" y="{y}" width="130" height="26" rx="6" fill="#111a3a" stroke="{LINE}"/>'
                   f'<rect x="{x + 8}" y="{y + 9}" width="8" height="8" rx="2" fill="{[CYAN, VIOLET, GREEN, AMBER][i % 4]}"/>'
                   f'<text x="{x + 24}" y="{y + 17.5}" font-size="12" fill="#dbe3f3">{esc(clip(item, 14))}</text>')

    xp_w = max(250 * into / span, 6)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 420" width="1000" height="420" role="img" aria-label="RPG character sheet for {esc(DISPLAY_NAME)}: level {level}, {commits} commits, {len(repos)} repos.">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b1020"/><stop offset="1" stop-color="#141b34"/></linearGradient>
    <linearGradient id="xp" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>
    <pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#fff" opacity=".05"/></pattern>
    <clipPath id="frame"><rect width="1000" height="420" rx="20"/></clipPath>
  </defs>
  <g clip-path="url(#frame)" font-family="{MONO}">
    <rect width="1000" height="420" fill="url(#bg)"/><rect width="1000" height="420" fill="url(#dots)"/>
    <text x="36" y="38" font-size="12" letter-spacing="4" fill="#dbe3f3" font-weight="700">CHARACTER SHEET</text>
    <text x="964" y="38" font-size="11" fill="{MUTED}" text-anchor="end">recalculated daily from GitHub</text>
    <line x1="36" y1="50" x2="964" y2="50" stroke="{LINE}"/>

    <rect x="36" y="66" width="250" height="176" rx="12" fill="#0e1736" stroke="{LINE}"/>
    <path d="M36 90 v-12 a12 12 0 0 1 12 -12 h12 M286 218 v12 a12 12 0 0 1 -12 12 h-12" fill="none" stroke="{CYAN}" stroke-width="2.5"/>
    <ellipse cx="161" cy="232" rx="52" ry="5" fill="#000" opacity=".35"/>
    <g transform="translate(81 70)">
      <g>{sprite}<animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" keyTimes="0;.5;1" calcMode="discrete" dur="1.1s" repeatCount="indefinite"/></g>
    </g>
    <text x="36" y="272" font-family="{SANS}" font-size="21" font-weight="800" letter-spacing="1.5" fill="#f1f5fb">{esc(DISPLAY_NAME)}</text>
    <text x="36" y="293" font-size="12.5" fill="{MUTED}">{esc(CLASS_NAME)}</text>
    <text x="36" y="336" font-size="13" fill="{MUTED}">LV</text>
    <text x="62" y="338" font-family="{SANS}" font-size="32" font-weight="800" fill="{CYAN}">{level}</text>
    <text x="286" y="336" font-size="12" fill="{MUTED}" text-anchor="end">{into:,} / {span:,} XP</text>
    <rect x="36" y="350" width="250" height="14" rx="7" fill="#0b1228" stroke="{LINE}"/>
    <rect x="36" y="350" width="{xp_w:.1f}" height="14" rx="7" fill="url(#xp)">
      <animate attributeName="width" from="0" to="{xp_w:.1f}" dur="1.6s" begin=".3s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>
    </rect>
    <text x="36" y="386" font-size="10.5" fill="{MUTED}">XP = commits x10 + repos x40 + stars x25</text>

    <line x1="308" y1="66" x2="308" y2="392" stroke="{LINE}"/><line x1="668" y1="66" x2="668" y2="392" stroke="{LINE}"/>
    {head(330, 78, "STATS")}{head(330, 262, "SKILLS")}
    {"".join(s)}
    {head(690, 78, "QUEST LOG")}{head(690, 262, "INVENTORY")}
    {"".join(q)}
    {"".join(inv)}
  </g>
  <rect x=".75" y=".75" width="998.5" height="418.5" rx="20" fill="none" stroke="{LINE}" stroke-width="1.5"/>
</svg>
'''


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--from-json":
        with open(sys.argv[2], encoding="utf-8") as f:
            repos = json.load(f)
    else:
        repos = fetch_repos()
    if not repos:
        sys.exit("No public repos with commits found; leaving the images unchanged.")
    for name, svg in (("city.svg", render_city(repos)), ("character.svg", render_character(repos))):
        with open(os.path.join(ASSETS, name), "w", encoding="utf-8") as f:
            f.write(svg)
    print(f"drew {len(repos)} repos into city.svg and character.svg")


if __name__ == "__main__":
    main()

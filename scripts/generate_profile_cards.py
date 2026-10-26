#!/usr/bin/env python3
"""Generate the live profile cards used by the README.

Outputs (SMIL-animated SVG, no scripts, so they play inside GitHub READMEs):
  assets/hud.svg        profile HUD: handle, name, live stat tiles, language chips, dot-matrix emblem
  assets/city.svg       isometric "city" built from the last year of contributions
  assets/langstack.svg  repository-weighted language bars

Usage:
  GH_TOKEN=... python3 scripts/generate_profile_cards.py            # live data (used by the workflow)
  python3 scripts/generate_profile_cards.py --demo                  # offline placeholder state

Only the Python standard library is used.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
LOGIN = os.environ.get("PROFILE_USER", "dev-shubh-madara")
TITLE = os.environ.get("PROFILE_NAME", "Shubh")
ROLE = os.environ.get("PROFILE_ROLE", "Backend Developer  ·  Telegram Bots  ·  AI Apps")

MONO = "'Fira Code','JetBrains Mono',Consolas,'Courier New',monospace"
SANS = "'Segoe UI',Inter,Helvetica,Arial,sans-serif"

CYAN, VIOLET, PINK = "#22d3ee", "#a78bfa", "#f472b6"
LANG_COLORS = {
    "Python": "#3b82f6", "JavaScript": "#facc15", "TypeScript": "#38bdf8", "HTML": "#fb923c",
    "CSS": "#a78bfa", "Shell": "#4ade80", "Java": "#f87171", "Kotlin": "#c084fc", "C++": "#f472b6",
    "C": "#94a3b8", "Go": "#22d3ee", "Rust": "#fb7185", "Dockerfile": "#38bdf8", "Jupyter Notebook": "#fdba74",
}
FALLBACK_COLORS = ["#22d3ee", "#a78bfa", "#f472b6", "#4ade80", "#facc15", "#fb923c"]


# --------------------------------------------------------------------------- data
def graphql(query: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch_live(token: str) -> dict:
    q = """
    query {
      user(login: "%s") {
        name followers { totalCount }
        repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
          totalCount
          nodes { stargazerCount primaryLanguage { name } }
        }
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }""" % LOGIN
    u = graphql(q, token)["user"]
    repos = u["repositories"]["nodes"]
    langs = Counter(r["primaryLanguage"]["name"] for r in repos if r["primaryLanguage"])
    days = [
        (d["date"], d["contributionCount"])
        for w in u["contributionsCollection"]["contributionCalendar"]["weeks"]
        for d in w["contributionDays"]
    ]
    return {
        "live": True,
        "repos": u["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": u["followers"]["totalCount"],
        "contributions": u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "days": days,
        "langs": langs,
    }


def demo_data() -> dict:
    """Decorative placeholder shown until the first live run. Carries no real numbers."""
    rnd = random.Random(7)
    start = dt.date.today() - dt.timedelta(days=52 * 7 + dt.date.today().weekday() + 1)
    days = []
    for i in range(53 * 7):
        wave = 0.5 + 0.5 * math.sin(i / 23.0)
        days.append(((start + dt.timedelta(days=i)).isoformat(), int(rnd.random() * 12 * wave)))
    return {"live": False, "repos": None, "stars": None, "followers": None,
            "contributions": None, "days": days, "langs": Counter()}


# --------------------------------------------------------------------------- shared svg bits
def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def shade(hex_color: str, k: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    f = (lambda c: max(0, min(255, int(c * k)))) if k <= 1 else (lambda c: int(c + (255 - c) * (k - 1)))
    return "#%02x%02x%02x" % (f(r), f(g), f(b))


COMMON_DEFS = f"""
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#05060f"/><stop offset=".5" stop-color="#0d0a24"/><stop offset="1" stop-color="#050b1a"/></linearGradient>
<linearGradient id="ink" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset=".5" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>
<linearGradient id="edge" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>
<linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<radialGradient id="o1"><stop offset="0" stop-color="#7c3aed" stop-opacity=".7"/><stop offset="1" stop-color="#7c3aed" stop-opacity="0"/></radialGradient>
<radialGradient id="o2"><stop offset="0" stop-color="#06b6d4" stop-opacity=".55"/><stop offset="1" stop-color="#06b6d4" stop-opacity="0"/></radialGradient>
<pattern id="grid" width="44" height="44" patternUnits="userSpaceOnUse"><path d="M44 0H0V44" fill="none" stroke="#fff" stroke-opacity=".045"/></pattern>
<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
"""


def frame(w: int, h: int, body: str, extra_defs: str = "", orbs: bool = True) -> str:
    orb = ""
    if orbs:
        orb = (
            f'<circle r="{int(h * .7)}" fill="url(#o1)"><animate attributeName="cx" values="{int(w * .12)};{int(w * .38)};{int(w * .12)}" dur="13s" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{int(h * .2)};{int(h * .8)};{int(h * .2)}" dur="13s" repeatCount="indefinite"/></circle>'
            f'<circle r="{int(h * .6)}" fill="url(#o2)"><animate attributeName="cx" values="{int(w * .9)};{int(w * .65)};{int(w * .9)}" dur="16s" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{int(h * .85)};{int(h * .2)};{int(h * .85)}" dur="16s" repeatCount="indefinite"/></circle>'
        )
    perim = 2 * (w + h)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>{COMMON_DEFS}{extra_defs}<clipPath id="card"><rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="24"/></clipPath></defs>
<g clip-path="url(#card)">
<rect width="{w}" height="{h}" fill="url(#bg)"/>
{orb}
<rect width="{w}" height="{h}" fill="url(#grid)"/>
{body}
<rect y="0" width="160" height="3" fill="#fff" opacity=".8"><animate attributeName="x" values="-180;{w + 20}" dur="5s" repeatCount="indefinite"/></rect>
</g>
<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="24" fill="none" stroke="url(#edge)" stroke-width="2" stroke-opacity=".35"/>
<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="24" fill="none" stroke="url(#edge)" stroke-width="2.4" stroke-dasharray="160 {perim}"><animate attributeName="stroke-dashoffset" values="0;-{perim + 160}" dur="7s" repeatCount="indefinite"/></rect>
</svg>
"""


def fmt(n) -> str:
    return "--" if n is None else f"{n:,}"


# --------------------------------------------------------------------------- HUD card
M_ROWS = 15  # emblem is a dot-matrix "M"


def in_m_glyph(i: int, j: int) -> bool:
    """Dot-grid predicate for a bold 'M' (i,j in dot units, centred on 0)."""
    if not (-7 <= j <= 7):
        return False
    if -8 <= i <= -6 or 6 <= i <= 8:
        return True
    if j <= 3:
        centre = 6 - (j + 7) * 0.6
        return abs(abs(i) - centre) <= 1.3
    return False


def emblem(cx: float, cy: float, radius: float, pitch: float) -> str:
    n = int(radius / pitch)
    dots, twinkle = [], []
    rnd = random.Random(11)
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            x, y = i * pitch, j * pitch
            d = math.hypot(x, y)
            if d > radius:
                continue
            glyph = in_m_glyph(i, j)
            t = (x + radius) / (2 * radius)
            base = shade(CYAN, 0.55 + 0.6 * (1 - t)) if t < .5 else shade(PINK, 0.55 + 0.6 * t)
            sphere = 0.28 + 0.72 * math.sqrt(max(0.0, 1 - (d / radius) ** 2))
            if glyph:
                color, r, op = "#ffffff", pitch * 0.40, 1.0
            else:
                color, r, op = base, pitch * (0.14 + 0.2 * sphere), 0.25 + 0.6 * sphere
            anim = ""
            if not glyph and rnd.random() < 0.06:
                anim = f'<animate attributeName="opacity" values="{op:.2f};1;{op:.2f}" dur="{rnd.uniform(2, 5):.1f}s" begin="{rnd.uniform(0, 4):.1f}s" repeatCount="indefinite"/>'
            if glyph:
                anim = f'<animate attributeName="opacity" values="1;.55;1" dur="3.2s" begin="{(i + j) * 0.05 % 3:.2f}s" repeatCount="indefinite"/>'
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{color}" opacity="{op:.2f}">{anim}</circle>')
    ring = (f'<circle r="{radius + 14}" fill="none" stroke="url(#ink)" stroke-width="1.5" stroke-dasharray="3 9" stroke-opacity=".7">'
            f'<animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="40s" repeatCount="indefinite"/></circle>'
            f'<circle r="{radius + 30}" fill="none" stroke="{VIOLET}" stroke-opacity=".25" stroke-dasharray="1 7">'
            f'<animateTransform attributeName="transform" type="rotate" from="360" to="0" dur="60s" repeatCount="indefinite"/></circle>')
    scan = (f'<clipPath id="orbclip"><circle r="{radius}"/></clipPath>'
            f'<g clip-path="url(#orbclip)"><rect x="{-radius}" width="{2 * radius}" height="26" fill="url(#scanband)">'
            f'<animate attributeName="y" values="{-radius - 30};{radius}" dur="4.5s" repeatCount="indefinite"/></rect></g>')
    return f'<g transform="translate({cx},{cy})">{ring}<g filter="url(#glow)">{"".join(dots)}</g>{scan}</g>'


def stat_tile(x: int, y: int, icon: str, value: str, label: str, delay: float) -> str:
    return (
        f'<g transform="translate({x},{y})">'
        f'<g transform="translate(0,-4)" fill="none" stroke="{CYAN}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)">{icon}</g>'
        f'<text x="46" y="22" font-family="{SANS}" font-size="30" font-weight="800" fill="#f1f5f9">{esc(value)}'
        f'<animate attributeName="fill" values="#f1f5f9;{CYAN};#f1f5f9" dur="5s" begin="{delay}s" repeatCount="indefinite"/></text>'
        f'<text x="46" y="42" font-family="{MONO}" font-size="12" letter-spacing="2" fill="#94a3b8">{esc(label)}</text></g>'
    )


ICONS = {
    "repo": '<rect x="2" y="2" width="22" height="22" rx="4"/><path d="M8 10h10M8 15h6"/>',
    "star": '<path d="M13 1.5l3.5 7.2 7.9 1.1-5.7 5.5 1.4 7.8L13 19.3l-7.1 3.8 1.4-7.8-5.7-5.5 7.9-1.1z"/>',
    "commit": '<circle cx="13" cy="13" r="5"/><path d="M1 13h7M18 13h7"/>',
    "people": '<circle cx="13" cy="8" r="5"/><path d="M3 24c0-6 4.5-9 10-9s10 3 10 9"/>',
}


def render_hud(d: dict) -> str:
    W, H = 1200, 400
    top_langs = [n for n, _ in d["langs"].most_common(4)] or ["Python", "JavaScript", "FastAPI", "Telegram"]
    chips, x = [], 56
    for k, name in enumerate(top_langs):
        col = LANG_COLORS.get(name, FALLBACK_COLORS[k % len(FALLBACK_COLORS)])
        wd = 34 + len(name) * 9
        chips.append(
            f'<g transform="translate({x},340)"><rect width="{wd}" height="32" rx="16" fill="{col}" fill-opacity=".12" stroke="{col}" stroke-opacity=".6"/>'
            f'<circle cx="18" cy="16" r="5" fill="{col}"><animate attributeName="opacity" values="1;.35;1" dur="2.6s" begin="{k * .4}s" repeatCount="indefinite"/></circle>'
            f'<text x="30" y="21" font-family="{MONO}" font-size="13" fill="#e2e8f0">{esc(name)}</text></g>'
        )
        x += wd + 12
    status = "LIVE" if d["live"] else "SYNCING"
    body = f"""
<g transform="translate(56,64)">
<circle r="5" cx="4" cy="-4" fill="#3fb950"><animate attributeName="opacity" values="1;.25;1" dur="1.8s" repeatCount="indefinite"/></circle>
<text x="18" y="0" font-family="{MONO}" font-size="15" letter-spacing="3" fill="{CYAN}">@{esc(LOGIN)}</text>
<text x="560" y="0" text-anchor="end" font-family="{MONO}" font-size="12" letter-spacing="3" fill="#64748b">{status} · PROFILE HUD</text>
</g>
<g filter="url(#glow)"><text x="52" y="152" font-family="{SANS}" font-size="84" font-weight="900" letter-spacing="2" fill="url(#ink)">{esc(TITLE.upper())}</text></g>
<text x="56" y="188" font-family="{SANS}" font-size="19" fill="#cbd5e1" xml:space="preserve">{esc(ROLE)}</text>
<rect x="56" y="206" width="520" height="1.5" fill="url(#edge)" opacity=".35"/>
{stat_tile(56, 218, ICONS["repo"], fmt(d["repos"]), "REPOSITORIES", 0)}
{stat_tile(316, 218, ICONS["star"], fmt(d["stars"]), "STARS", 1)}
{stat_tile(56, 280, ICONS["commit"], fmt(d["contributions"]), "CONTRIBUTIONS", 2)}
{stat_tile(316, 280, ICONS["people"], fmt(d["followers"]), "FOLLOWERS", 3)}
{"".join(chips)}
<g transform="translate(600,0)"><path d="M0 40V360" stroke="url(#edge)" stroke-opacity=".25" stroke-dasharray="2 8"/></g>
{emblem(930, 200, 150, 10)}
"""
    extra = ('<linearGradient id="scanband" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
             '<stop offset=".5" stop-color="#22d3ee" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    return frame(W, H, body, extra)


# --------------------------------------------------------------------------- city card
LEVEL_COLORS = ["#1e293b", "#0e7490", CYAN, VIOLET, PINK]


def level_of(count: int, max_count: int) -> int:
    if count <= 0:
        return 0
    q = count / max(1, max_count)
    return 1 if q <= .25 else 2 if q <= .5 else 3 if q <= .75 else 4


def render_city(d: dict) -> str:
    W, H = 760, 380
    days = d["days"][-371:]
    cols = 19
    rows = math.ceil(len(days) / cols)
    max_count = max((c for _, c in days), default=1) or 1
    cw, ch, maxh = 8.6, 4.3, 78.0
    ox = W - 215
    oy = H - 26 - (cols + rows) * ch

    cells = [(k % cols, k // cols, date, cnt) for k, (date, cnt) in enumerate(days)]
    cells.sort(key=lambda c: (c[0] + c[1], c[0]))

    groups: dict[int, list[str]] = {}
    for cx, cy, date, cnt in cells:
        sx = ox + (cx - cy) * cw
        sy = oy + (cx + cy) * ch
        lvl = level_of(cnt, max_count)
        col = LEVEL_COLORS[lvl]
        h = 2.0 if cnt == 0 else 5 + (cnt / max_count) ** 0.8 * maxh
        top = f"{sx:.1f},{sy - h:.1f} {sx + cw:.1f},{sy - h + ch:.1f} {sx:.1f},{sy - h + 2 * ch:.1f} {sx - cw:.1f},{sy - h + ch:.1f}"
        left = f"{sx - cw:.1f},{sy - h + ch:.1f} {sx:.1f},{sy - h + 2 * ch:.1f} {sx:.1f},{sy + 2 * ch:.1f} {sx - cw:.1f},{sy + ch:.1f}"
        right = f"{sx + cw:.1f},{sy - h + ch:.1f} {sx:.1f},{sy - h + 2 * ch:.1f} {sx:.1f},{sy + 2 * ch:.1f} {sx + cw:.1f},{sy + ch:.1f}"
        groups.setdefault(cx + cy, []).append(
            f'<polygon points="{left}" fill="{shade(col, .55)}"/><polygon points="{right}" fill="{shade(col, .78)}"/>'
            f'<polygon points="{top}" fill="{shade(col, 1.18) if lvl else col}"/>'
        )
    span = max(groups) + 1
    city = []
    for key in sorted(groups):
        begin = key / span * 5
        city.append(f'<g>{"".join(groups[key])}<animate attributeName="opacity" values="1;.5;1" dur="5s" begin="{begin:.2f}s" repeatCount="indefinite"/></g>')

    active = sum(1 for _, c in days if c > 0)
    busiest = max((c for _, c in days), default=0)
    total = d["contributions"] if d["live"] else None
    body = f"""
<text x="34" y="52" font-family="{SANS}" font-size="24" font-weight="800" fill="#f1f5f9">The city I built this year</text>
<text x="34" y="92" font-family="{MONO}" font-size="12" letter-spacing="3" fill="{CYAN}">CONTRIBUTIONS</text>
<g filter="url(#glow)"><text x="34" y="146" font-family="{SANS}" font-size="54" font-weight="900" fill="url(#ink)">{fmt(total)}</text></g>
<text x="34" y="178" font-family="{MONO}" font-size="13" fill="#94a3b8">{active if d["live"] else "--"} active days</text>
<text x="34" y="200" font-family="{MONO}" font-size="13" fill="#94a3b8">Busiest day: {busiest if d["live"] else "--"}</text>
<g transform="translate(34,{H - 34})" font-family="{MONO}" font-size="11" fill="#64748b">
<text x="0" y="0">LESS</text>
{"".join(f'<rect x="{44 + k * 16}" y="-10" width="11" height="11" rx="2.5" fill="{c}"/>' for k, c in enumerate(LEVEL_COLORS))}
<text x="{44 + 5 * 16 + 4}" y="0">MORE</text></g>
{"".join(city)}
"""
    return frame(W, H, body)


# --------------------------------------------------------------------------- language card
def render_langs(d: dict) -> str:
    W, H = 400, 380
    items = d["langs"].most_common(6)
    total = sum(c for _, c in items) or 1
    peak = max((c for _, c in items), default=1) or 1
    rows = []
    if not items:
        items = [("Python", 0), ("JavaScript", 0), ("HTML", 0), ("Shell", 0), ("TypeScript", 0)]
    for k, (name, cnt) in enumerate(items):
        y = 128 + k * 42
        col = LANG_COLORS.get(name, FALLBACK_COLORS[k % len(FALLBACK_COLORS)])
        pct = cnt / total * 100 if d["live"] else None
        bar_w = 190 * (cnt / peak) if pct is not None else 190 * (0.9 - k * 0.14)
        label = f"{pct:.0f}%" if pct is not None else "--%"
        rows.append(
            f'<g transform="translate(34,{y})">'
            f'<circle cx="6" cy="-5" r="6" fill="{col}"/>'
            f'<text x="24" y="0" font-family="{MONO}" font-size="14" fill="#e2e8f0">{esc(name)}</text>'
            f'<text x="332" y="0" text-anchor="end" font-family="{MONO}" font-size="14" font-weight="700" fill="{col}">{label}</text>'
            f'<rect x="24" y="10" width="190" height="7" rx="3.5" fill="#1e293b"/>'
            f'<rect x="24" y="10" width="0" height="7" rx="3.5" fill="{col}" filter="url(#glow)"><animate attributeName="width" from="0" to="{max(bar_w, 4):.1f}" dur="1.4s" begin="{k * .18:.2f}s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/></rect>'
            f'<rect x="24" y="10" width="34" height="7" rx="3.5" fill="url(#shine)" opacity=".7"><animate attributeName="x" values="24;{24 + max(bar_w, 4) - 34:.1f};24" dur="3.4s" begin="{1.5 + k * .3:.1f}s" repeatCount="indefinite"/></rect></g>'
        )
    body = f"""
<text x="34" y="52" font-family="{SANS}" font-size="24" font-weight="800" fill="#f1f5f9">Language Stack</text>
<text x="366" y="52" text-anchor="end" font-family="{MONO}" font-size="13" fill="{CYAN}">&gt; stack.scan<tspan><animate attributeName="opacity" values="1;0;1" dur="1.1s" repeatCount="indefinite"/>_</tspan></text>
<text x="34" y="82" font-family="{MONO}" font-size="12" letter-spacing="1" fill="#64748b">Repository-weighted technologies</text>
{"".join(rows)}
"""
    return frame(W, H, body)


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="write the offline placeholder state")
    ap.add_argument("--out", default=str(ASSETS))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.demo:
        data = demo_data()
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            print("GH_TOKEN is not set; use --demo for offline output", file=sys.stderr)
            return 2
        try:
            data = fetch_live(token)
        except Exception as exc:  # keep the previous SVGs if GitHub is unreachable
            print(f"live fetch failed, leaving existing cards untouched: {exc}", file=sys.stderr)
            return 1

    (out / "hud.svg").write_text(render_hud(data), encoding="utf-8")
    (out / "city.svg").write_text(render_city(data), encoding="utf-8")
    (out / "langstack.svg").write_text(render_langs(data), encoding="utf-8")
    print(f"wrote hud.svg, city.svg, langstack.svg ({'live' if data['live'] else 'demo'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

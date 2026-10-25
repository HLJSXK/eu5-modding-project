"""Build the self-contained HTML report from summary.json (no external assets)."""
from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
S = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
D = S["decades"]
YEARS = [r["year"] for r in D]

INK, PAPER, RULE, MUTED = "#1d2a36", "#f2f3ee", "#c9ccc2", "#6c737a"
CUT, BOOST, BAD, OK, WARN = "#2f5d9a", "#b9832a", "#a8322f", "#4c7a5f", "#c9a23c"


def e(text):
    return html.escape(str(text))


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


# ---------------------------------------------------------------- SVG helpers
class Plot:
    def __init__(self, w, h, x0, x1, y0, y1, pad=(46, 16, 18, 30)):
        self.w, self.h = w, h
        self.l, self.r, self.t, self.b = pad
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.parts = []

    def X(self, v):
        return self.l + (v - self.x0) / (self.x1 - self.x0) * (self.w - self.l - self.r)

    def Y(self, v):
        return self.h - self.b - (v - self.y0) / (self.y1 - self.y0) * (self.h - self.t - self.b)

    def add(self, s):
        self.parts.append(s)

    def yaxis(self, ticks, fmt):
        for v in ticks:
            y = self.Y(v)
            self.add(f'<line x1="{self.l}" x2="{self.w - self.r}" y1="{y:.1f}" y2="{y:.1f}" stroke="{RULE}" stroke-width="0.6"/>')
            self.add(f'<text x="{self.l - 6}" y="{y + 3.5:.1f}" text-anchor="end" class="tick">{e(fmt(v))}</text>')

    def xaxis(self, ticks, fmt):
        for v in ticks:
            x = self.X(v)
            self.add(f'<text x="{x:.1f}" y="{self.h - self.b + 16}" text-anchor="middle" class="tick">{e(fmt(v))}</text>')

    def line(self, xs, ys, color, width=2, dash=None):
        pts = " ".join(f"{self.X(x):.1f},{self.Y(y):.1f}" for x, y in zip(xs, ys))
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"{d} stroke-linejoin="round"/>')

    def band(self, xs, lo, hi, color, op):
        pts = [f"{self.X(x):.1f},{self.Y(y):.1f}" for x, y in zip(xs, hi)]
        pts += [f"{self.X(x):.1f},{self.Y(y):.1f}" for x, y in zip(xs[::-1], lo[::-1])]
        self.add(f'<polygon points="{" ".join(pts)}" fill="{color}" fill-opacity="{op}"/>')

    def svg(self, label):
        return (f'<svg viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{e(label)}">'
                + "".join(self.parts) + "</svg>")


# ---------------------------------------------------------------- hero grid
CHECKS = [
    ("每个有领土的国家都有替代结果", lambda r: "ok" if r["noinit"] == 0 else "warn",
     lambda r: f"{r['noinit']} 个新国家尚未初始化" if r["noinit"] else "全部有"),
    ("结果不超过一年没更新", lambda r: "ok" if r["stale"] == 0 else "warn",
     lambda r: f"{r['stale']} 国沿用旧结果，占人口 {r['stale_pop_pct']:.3f}%" if r["stale"] else "全部 ≤1 年"),
    ("价格档位与市场价格一致", lambda r: "ok" if r["tier_match"] >= .9999 else "warn",
     lambda r: f"吻合 {pct(r['tier_match'], 2)}" + ("（一月）" if r["tier_offset"] == 5 else "（年中重算）")),
    ("贵的降、便宜的升", lambda r: "ok" if r["corr"] <= -.5 else "warn",
     lambda r: f"价格与倍率相关 {r['corr']:.2f}"),
    ("倍率与独立复算一致", lambda r: "ok" if (r["oracle_ok"] or 0) >= .95 else "warn",
     lambda r: f"误差 <0.01 的支出占 {pct(r['oracle_ok'])}"),
    ("外部需求读数干净", lambda r: "ok" if r["polluted"] == 0 else "bad",
     lambda r: f"{r['polluted']} 国读错（新国家第二次刷新）" if r["polluted"] else "无误读"),
    ("实际修正与账本一致", lambda r: "ok" if r["orphans"] == 0 else "bad",
     lambda r: f"{r['orphans']} 国有残留修正，占人口 {r['orphan_pop_pct']:.2f}%" if r["orphans"] else "一致"),
    ("灭亡国家的缓存已清理", lambda r: "ok" if r["dead_caches"] == 0 else "bad",
     lambda r: f"{r['dead_caches']} 个死国家仍挂着缓存，约 {r['dead_mb']} MB"),
]
COLORS = {"ok": OK, "warn": WARN, "bad": BAD}


def hero_grid():
    cw, ch, lw = 13, 22, 236
    w = lw + cw * len(D) + 8
    h = ch * len(CHECKS) + 34
    parts = []
    for i, (name, rule, note) in enumerate(CHECKS):
        y = i * ch + 4
        parts.append(f'<text x="{lw - 10}" y="{y + 15}" text-anchor="end" class="rowlab">{e(name)}</text>')
        for j, r in enumerate(D):
            status = rule(r)
            x = lw + j * cw
            parts.append(f'<rect x="{x}" y="{y}" width="{cw - 2}" height="{ch - 3}" fill="{COLORS[status]}"'
                         f' fill-opacity="{1 if status != "ok" else .78}"><title>{r["year"]}：{e(note(r))}</title></rect>')
    for j, r in enumerate(D):
        if r["year"] % 100 == 0 or r["year"] == 1340:
            x = lw + j * cw + (cw - 2) / 2
            parts.append(f'<text x="{x}" y="{len(CHECKS) * ch + 20}" text-anchor="middle" class="tick">{r["year"]}</text>')
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="51 个存档逐项检查">{"".join(parts)}</svg>'


# ---------------------------------------------------------------- charts
def direction_chart():
    p = Plot(560, 250, 1340, 1840, 0, 1)
    p.yaxis([0, .25, .5, .75, 1], lambda v: f"{int(v * 100)}%")
    p.xaxis(range(1340, 1841, 100), str)
    p.line(YEARS, [r["exp"]["down"] for r in D], CUT, 2.4)
    p.line(YEARS, [r["cheap"]["up"] for r in D], BOOST, 2.4)
    p.line(YEARS, [-r["corr"] for r in D], INK, 1.2, "3 3")
    p.add(f'<text x="{p.X(1600)}" y="{p.Y(.9)}" class="lab" fill="{CUT}">变贵的商品：需求被调低的比例</text>')
    p.add(f'<text x="{p.X(1600)}" y="{p.Y(.5)}" class="lab" fill="{BOOST}">变便宜的商品：需求被调高的比例</text>')
    p.add(f'<text x="{p.X(1350)}" y="{p.Y(.97)}" class="lab" fill="{INK}">价格与倍率的负相关强度（虚线）</text>')
    return p.svg("方向检查随时间")


def scatter_1840():
    r = D[-1]
    zh = S["goods_zh"]
    pts = r["goods_points"]
    p = Plot(440, 300, math.log(.25), math.log(5.5), math.log(.5), math.log(1.45), pad=(44, 14, 14, 32))
    p.yaxis([math.log(v) for v in (.6, .8, 1, 1.2, 1.4)], lambda v: f"×{math.exp(v):.1f}")
    p.xaxis([math.log(v) for v in (.25, .5, 1, 2, 4)], lambda v: f"{math.exp(v):g}倍")
    p.add(f'<line x1="{p.X(0)}" x2="{p.X(0)}" y1="{p.t}" y2="{p.h - p.b}" stroke="{MUTED}" stroke-width=".8"/>')
    p.add(f'<line x1="{p.l}" x2="{p.w - p.r}" y1="{p.Y(0)}" y2="{p.Y(0)}" stroke="{MUTED}" stroke-width=".8"/>')
    label = {"tea", "coffee", "potato", "cocoa", "wine", "amber", "legumes", "fish"}
    for q in pts:
        x, y = math.log(q["p"]), math.log(q["m"])
        c = CUT if q["m"] < 1 else BOOST
        p.add(f'<circle cx="{p.X(x):.1f}" cy="{p.Y(y):.1f}" r="4" fill="{c}" fill-opacity=".85">'
              f'<title>{e(zh.get(q["g"], q["g"]))}：价格 {q["p"]:.2f} 倍默认价，世界平均倍率 ×{q["m"]:.2f}</title></circle>')
        if q["g"] in label:
            p.add(f'<text x="{p.X(x) + 6:.1f}" y="{p.Y(y) + 4:.1f}" class="pt">{e(zh.get(q["g"], q["g"]))}</text>')
    p.add(f'<text x="{p.w - p.r}" y="{p.h - 2}" text-anchor="end" class="axis">一月市场价 ÷ 默认价</text>')
    p.add(f'<text x="{p.l + 4}" y="{p.t + 10}" class="axis">国家需求倍率（按支出加权的世界平均）</text>')
    return p.svg("1840 年各商品价格与倍率")


def magnitude_chart():
    p = Plot(560, 230, 1340, 1840, .5, 1.4)
    p.yaxis([.6, .8, 1, 1.2, 1.4], lambda v: f"×{v:.1f}")
    p.xaxis(range(1340, 1841, 100), str)
    q = [r["mq"] for r in D]
    p.band(YEARS, [a[0] for a in q], [a[4] for a in q], CUT, .14)
    p.band(YEARS, [a[1] for a in q], [a[3] for a in q], CUT, .28)
    p.line(YEARS, [a[2] for a in q], INK, 1.6)
    p.line(YEARS, [r["sum_ratio"] for r in D], BAD, 1.6, "5 3")
    p.add(f'<text x="{p.X(1345)}" y="{p.Y(1.33)}" class="lab" fill="{CUT}">最宽一档覆盖 90% 的支出，深色覆盖中间 50%</text>')
    p.add(f'<text x="{p.X(1600)}" y="{p.Y(.93)}" class="lab" fill="{BAD}">总支出变化（虚线）</text>')
    return p.svg("倍率分布随时间")


def oracle_chart():
    bins = S["oracle_bins"]
    w, rowh, lw = 520, 30, 110
    parts = []
    for i, b in enumerate(bins):
        y = i * rowh + 6
        good = 1 - b["over_001"]
        bw = (w - lw - 170) * good
        parts.append(f'<text x="{lw - 10}" y="{y + 15}" text-anchor="end" class="rowlab">{e(b["label"])}</text>')
        parts.append(f'<rect x="{lw}" y="{y}" width="{w - lw - 170}" height="{rowh - 10}" fill="{RULE}" fill-opacity=".5"/>')
        parts.append(f'<rect x="{lw}" y="{y}" width="{bw:.1f}" height="{rowh - 10}" fill="{OK}"/>')
        parts.append(f'<text x="{lw + bw + 6:.1f}" y="{y + 15}" class="tick">{pct(good)}（{b["n"]:,} 项）</text>')
    return f'<svg viewBox="0 0 {w} {len(bins) * rowh + 10}" role="img" aria-label="复算吻合度">{"".join(parts)}</svg>'


def pickup_chart():
    bins = S["pickup_bins"]
    ref = next(b["y"] for b in bins if b["lo"] == -.03)
    p = Plot(400, 300, -.55, .5, -.55, .7, pad=(44, 14, 14, 32))
    p.yaxis([math.log(v) for v in (.6, .8, 1, 1.25, 1.6, 2)], lambda v: f"×{math.exp(v):.2f}".rstrip("0").rstrip("."))
    p.xaxis([math.log(v) for v in (.6, .8, 1, 1.25, 1.6)], lambda v: f"×{math.exp(v):.2f}".rstrip("0").rstrip("."))
    p.add(f'<line x1="{p.X(-.55)}" y1="{p.Y(-.55)}" x2="{p.X(.5)}" y2="{p.Y(.5)}" stroke="{MUTED}" stroke-dasharray="4 3"/>')
    p.add(f'<text x="{p.X(.12)}" y="{p.Y(.5) + 4}" class="axis">完全传导</text>')
    for b in bins:
        y = b["y"] - ref
        c = CUT if b["x"] < -.02 else BOOST if b["x"] > .02 else MUTED
        r = 3 + math.sqrt(b["n"]) / 18
        p.add(f'<circle cx="{p.X(b["x"]):.1f}" cy="{p.Y(y):.1f}" r="{r:.1f}" fill="{c}" fill-opacity=".85">'
              f'<title>国家倍率约 ×{math.exp(b["x"]):.2f}：市场实际人口需求相对中性组 ×{math.exp(y):.2f}（{b["n"]:,} 个市场×商品）</title></circle>')
    p.add(f'<text x="{p.w - p.r}" y="{p.h - 2}" text-anchor="end" class="axis">SOL 写给国家的倍率</text>')
    p.add(f'<text x="{p.l + 4}" y="{p.t + 10}" class="axis">存档里市场实际的人口需求（扣价格影响）</text>')
    return p.svg("引擎是否吃进倍率")


def slope_chart():
    pk = S["pickup"]
    p = Plot(400, 170, 1330, 1850, 0, 2, pad=(44, 14, 12, 26))
    p.yaxis([0, .5, 1, 1.5, 2], lambda v: f"{v:g}")
    p.xaxis(range(1350, 1851, 100), str)
    p.add(f'<line x1="{p.l}" x2="{p.w - p.r}" y1="{p.Y(1)}" y2="{p.Y(1)}" stroke="{OK}" stroke-width="1.2"/>')
    for q in pk:
        x = p.X(q["year"])
        p.add(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{p.Y(q["slope"] - 2 * q["se"]):.1f}" y2="{p.Y(q["slope"] + 2 * q["se"]):.1f}" stroke="{INK}" stroke-width="1"/>')
        p.add(f'<circle cx="{x:.1f}" cy="{p.Y(q["slope"]):.1f}" r="3.2" fill="{INK}"><title>{q["year"]}：传导系数 {q["slope"]:.2f} ± {2 * q["se"]:.2f}</title></circle>')
    return p.svg("各年传导系数")


def dead_chart():
    p = Plot(560, 200, 1340, 1840, 0, 30)
    p.yaxis([0, 10, 20, 30], lambda v: f"{int(v)} MB")
    p.xaxis(range(1340, 1841, 100), str)
    p.band(YEARS, [0] * len(D), [r["dead_mb"] for r in D], BAD, .25)
    p.line(YEARS, [r["dead_mb"] for r in D], BAD, 2)
    p.line(YEARS, [r["alive_mb"] for r in D], OK, 2)
    p.add(f'<text x="{p.X(1600)}" y="{p.Y(r_dead(1600)) - 8}" class="lab" fill="{BAD}">已灭亡国家的替代缓存</text>')
    p.add(f'<text x="{p.X(1600)}" y="{p.Y(r_alive(1600)) + 16}" class="lab" fill="{OK}">在世国家的替代缓存</text>')
    return p.svg("存档中的替代缓存体积")


def r_dead(y):
    return next(r["dead_mb"] for r in D if r["year"] == y)


def r_alive(y):
    return next(r["alive_mb"] for r in D if r["year"] == y)


# ---------------------------------------------------------------- tables
def orphan_table():
    rows = []
    for o in S["orphan_cases"]:
        goods = "，".join(f'{g["zh"]} {g["S"]:+.0%}' if abs(g["S"]) >= .01 else f'{g["zh"]} {g["S"]:+.1%}' for g in o["goods"])
        rows.append(f'<tr><td>{o["year"]}</td><td>{e(o["tag"])}</td><td class="n">{o["nloc"]}</td>'
                    f'<td class="n">{o["pop_pct"]:.2f}%</td><td>{e(goods)}</td><td>{e(", ".join(o["donor"]))}</td></tr>')
    return ("<table><thead><tr><th>存档</th><th>国家</th><th class='n'>地块</th><th class='n'>世界人口占比</th>"
            "<th>账本说 ×1，实际仍挂着的修正</th><th>与之完全相同的已灭亡叛乱国</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def examples_block():
    ex = S["examples"]["1840"]
    names = {"FRA": "法兰西", "HUN": "匈牙利", "MAM": "马穆鲁克", "CHI": "中国"}
    out = []
    for tag in ("FRA", "CHI", "MAM", "HUN"):
        if tag not in ex:
            continue
        x = ex[tag]
        low = "、".join(f'{g["zh"]}（价 {g["p"]:.1f} 倍 → 需求 ×{g["M"]:.2f}）' for g in x["low"])
        high = "、".join(f'{g["zh"]}（价 {g["p"]:.1f} 倍 → ×{g["M"]:.2f}）' for g in x["high"])
        out.append(f'<p class="ex"><b>{names[tag]}</b>　压得最多：{e(low)}。抬得最多：{e(high)}。</p>')
    return "".join(out)


# ---------------------------------------------------------------- numbers for prose
first, last = D[0], D[-1]
tot_alive = sum(r["alive"] for r in D)
stale_total = sum(r["stale"] for r in D)
noinit_total = sum(r["noinit"] for r in D)
pol = S["polluted_cases"]
pol_cells = sum(p["cells"] for p in pol)
pol_match = sum(p["two_minus_m"] for p in pol)
pol_r2 = sum(1 for p in pol if p["refresh"] == 2)
orph = S["orphan_cases"]
rev = S["revived_cases"]
rev_old = sorted(rev, key=lambda r: r["since"] - r["year"])[:3]
pk = S["pickup"]
pk_late = [q for q in pk if q["year"] >= 1700]
bins = S["pickup_bins"]
ref = next(b["y"] for b in bins if b["lo"] == -.03)
big_cut = next(b for b in bins if b["hi"] == -.25)
mid_cut = next(b for b in bins if b["lo"] == -.25)
small_cut = next(b for b in bins if b["lo"] == -.1)
big_up = next(b for b in bins if b["lo"] == .25)
mid_up = next(b for b in bins if b["lo"] == .1)
save_growth = last["save_mb"]


def ratio(b):
    return math.exp(b["y"] - ref)


CSS = f"""
:root {{ color-scheme: light; --ink:{INK}; --paper:{PAPER}; --rule:{RULE}; --muted:{MUTED}; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink);
  font: 16px/1.75 "PingFang SC","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC",sans-serif;
  font-variant-numeric: tabular-nums; }}
main {{ max-width: 1060px; margin: 0 auto; padding: 48px 28px 80px; }}
h1, h2 {{ font-family: "Songti SC","Noto Serif CJK SC","Source Han Serif SC","SimSun",serif; font-weight: 700; letter-spacing:.02em; }}
h1 {{ font-size: 2.35rem; line-height:1.25; margin: 0 0 .4em; max-width: 22em; }}
h2 {{ font-size: 1.45rem; margin: 2.6em 0 .5em; padding-top: .9em; border-top: 2px solid var(--ink); }}
h3 {{ font-size: 1.02rem; margin: 1.6em 0 .3em; }}
p, li {{ max-width: 40em; }}
.lede {{ font-size: 1.12rem; max-width: 38em; }}
.src {{ color: var(--muted); font-size: .86rem; }}
.grid-wrap {{ margin: 28px 0 10px; overflow-x: auto; }}
.grid-wrap svg {{ min-width: 880px; width: 100%; height: auto; }}
.key {{ display:flex; gap: 22px; flex-wrap: wrap; font-size: .88rem; color: var(--muted); }}
.key span::before {{ content:""; display:inline-block; width: 11px; height: 11px; margin-right: 6px; vertical-align: -1px; background: var(--c); }}
.verdict {{ display:grid; grid-template-columns: repeat(3, 1fr); gap: 0; margin: 30px 0 0; border-top: 1px solid var(--rule); }}
.verdict div {{ padding: 14px 18px 4px 0; }}
.verdict div + div {{ padding-left: 18px; border-left: 1px solid var(--rule); }}
.verdict b {{ display:block; font-family: "Songti SC","Noto Serif CJK SC","SimSun",serif; font-size: 1.1rem; margin-bottom: 4px; }}
.verdict p {{ margin: 0; font-size: .95rem; }}
.pair {{ display:grid; grid-template-columns: 1.25fr 1fr; gap: 34px; align-items: start; }}
.pair.even {{ grid-template-columns: 1fr 1fr; }}
figure {{ margin: 18px 0; }}
figure svg {{ width: 100%; height: auto; display:block; }}
figcaption {{ font-size: .86rem; color: var(--muted); margin-top: 6px; max-width: 40em; }}
svg text {{ font-family: inherit; fill: var(--ink); }}
svg .tick {{ font-size: 11px; fill: var(--muted); }}
svg .rowlab {{ font-size: 12.5px; }}
svg .lab {{ font-size: 12px; font-weight: 600; }}
svg .pt {{ font-size: 11px; }}
svg .axis {{ font-size: 11px; fill: var(--muted); }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; margin: 12px 0; }}
th, td {{ text-align: left; padding: 6px 10px 6px 0; border-bottom: 1px solid var(--rule); vertical-align: top; }}
th {{ font-weight: 600; border-bottom: 1.5px solid var(--ink); }}
td.n, th.n {{ text-align: right; }}
.ex {{ font-size: .95rem; margin: .5em 0; }}
.issue {{ border-left: 4px solid {BAD}; padding: 2px 0 2px 18px; margin: 26px 0; }}
.issue.minor {{ border-color: {WARN}; }}
.issue h3 {{ margin-top: 0; }}
.decide {{ counter-reset: d; padding: 0; list-style: none; }}
.decide li {{ margin: 0 0 1.1em; padding-left: 0; }}
code {{ font-family: "Cascadia Mono", Consolas, monospace; font-size: .86em; background: #e3e6dd; padding: 1px 4px; }}
@media (max-width: 760px) {{
  h1 {{ font-size: 1.7rem; }} .pair, .pair.even, .verdict {{ grid-template-columns: 1fr; }}
  .verdict div + div {{ border-left: 0; padding-left: 0; border-top: 1px solid var(--rule); }}
}}
"""

body = f"""
<main>
<h1>替代组功能 500 年验收：主体达标，有三处边角漏洞</h1>
<p class="lede">观察档 <code>d2d1d136</code> 从 1340 到 1840 年每十年一个存档，共 51 个。我逐一读出各国的替代结果，
用存档里的人口和市场价格独立复算一遍，再看市场上的实际人口需求有没有跟着变。</p>
<p class="src">游戏版本 1.4.3，SOL 261023（含缓存驱动的国家自动修正），观察者模式，AI 年度刷新开启；每档 {first['alive']}→{last['alive']} 个在世国家，共 {tot_alive:,} 个国家·存档。</p>

<div class="grid-wrap">{hero_grid()}</div>
<div class="key"><span style="--c:{OK}">符合预期</span><span style="--c:{WARN}">轻微偏差</span><span style="--c:{BAD}">需要修</span><span>每列一个存档；鼠标停在格子上看具体数字</span></div>

<div class="verdict">
 <div><b>该做的都做到了</b><p>贵的商品需求被压低、便宜的被抬高，方向全期稳定；幅度适中且没有越跑越偏；每国每年准时刷新一次；国家倍率和我独立复算的结果吻合。</p></div>
 <div><b>引擎确实吃进去了</b><p>把存档里的市场人口需求和 SOL 写给国家的倍率对比，倍率高的地方需求确实更高，平均传导系数约为 1。大幅压低也能看到，小幅压低在数据里不明显。</p></div>
 <div><b>漏洞都在国家生死交替时</b><p>新国家第二次刷新会读错外部需求；叛乱国并回后会把它的修正留在母国身上；灭亡国家的缓存从不清理，存档里已经堆了 {last['dead_mb']} MB。影响的人口都很小。</p></div>
</div>

<h2>方向：贵的降，便宜的升</h2>
<div class="pair">
<figure>{direction_chart()}
<figcaption>按国家支出加权。“变贵”指该国所在市场一月价格档位权重低于 1（高于默认价 1.3 倍），“变便宜”指权重高于 1。剩下没被调低的贵商品，大多是同组成员也一样贵，相对来说并不贵。</figcaption></figure>
<figure>{scatter_1840()}
<figcaption>1840 年，每个点是一种商品在全世界的平均情况。左上和右下的点就是预期的形状。价格高于默认价 1.3 倍的商品，没有一个被平均抬高。</figcaption></figure>
</div>
<p>1340 年变贵商品有 {pct(first['exp']['down'],0)} 被调低，到 1840 年升到 {pct(last['exp']['down'],0)}；变便宜的商品被调高的比例从 {pct(first['cheap']['up'],0)} 升到 {pct(last['cheap']['up'],0)}。
价格和倍率的负相关从 {first['corr']:.2f} 加强到 {last['corr']:.2f}，因为后期各市场的价格分化更明显，替代有更多可做的事。</p>
{examples_block()}

<h2>幅度：适中，而且不漂移</h2>
<div class="pair">
<figure>{magnitude_chart()}
<figcaption>每种商品在每国的倍率，按基础支出加权后的分位数。中位数始终是 ×1.00：一半以上的支出所在商品不需要替代。</figcaption></figure>
<div>
<p>中间一半支出的倍率始终在 ×{min(r['mq'][1] for r in D):.2f} 到 ×{max(r['mq'][3] for r in D):.2f} 之间，90% 的支出落在 ×{min(r['mq'][0] for r in D):.2f} 到 ×{max(r['mq'][4] for r in D):.2f} 之间。
倍率偏离 1 超过一成的支出占 {pct(min(r['big_share'] for r in D),0)}–{pct(max(r['big_share'] for r in D),0)}，前后没有越来越极端。</p>
<p>替代后按默认价计的总支出比替代前少 {pct(1-first['sum_ratio'])}（1340）到 {pct(1-last['sum_ratio'])}（1840）。设计文档写明当前算法不保证组内守恒，
所以这是预期内的：被压低的贵商品略多于被抬高的便宜商品。后面的生活水平求解器会根据新篮子重新定总量，不会因此少花钱。</p>
</div>
</div>

<h2>计算：和独立复算对得上</h2>
<div class="pair even">
<div>
<p>我用存档里的人口、市场价格档位和供应标记，按设计文档的算法 A 自己写了一遍（没有调用模组生成的代码），对每个国家每种商品算出倍率，再和存档里游戏算的结果比。</p>
<p>只比当年刷新过的国家。按支出加权，除 1800、1820 两档外，各存档有 {pct(min(r['oracle_ok'] for r in D if r['tier_offset']==5),0)}–{pct(max(r['oracle_ok'] for r in D if r['tier_offset']==5),0)} 的支出误差小于 0.01。
对不上的主要是基础支出极小的商品，比如一个只有几户贵族的小国的珠宝，引擎的五位小数精度不够，属于正常舍入；其余来自刷新之后到存档之间（最多三个月）领土和人口的变动。</p>
<p>1800 和 1820 两档较低（{pct(next(r['oracle_ok'] for r in D if r['year']==1800),0)}、{pct(next(r['oracle_ok'] for r in D if r['year']==1820),0)}），原因是那年年中触发了一次全世界市场档位重算（脚本在国家发现自己的市场没有缓存时会这样做，很可能是新出现了市场），存档里留下的是重算后的档位，而一月到三月刷新的国家用的是重算前的档位。把 1820 年的档位换回一月价格后，吻合度回到 89%。这不是错误，只是档位会在年中跳一次。</p>
<p>价格档位缓存也核对了：{S['tier_total']:,} 个“市场×商品”档位中，{S['tier_ok']:,} 个与某一个月的价格严格对应（49 档对应一月，1800、1820 对应年中重算的月份），说明档位阈值和档位表与设计一致。</p>
<p>刷新节奏：持续在世的国家，相邻两档之间恰好刷新 10 次的占 99.9%（34,904 / 34,946），例外都是中途灭亡又复活的国家。人类玩家为 0（观察者）。倍率回到 1 的商品，{S['zero_removed']:,} 次全部按设计删掉了尺寸变量，自动修正不会常驻。</p>
</div>
<figure>{oracle_chart()}
<figcaption>按该国该商品的基础支出大小分档：绿色是误差小于 0.01 的比例。支出越大越准。</figcaption></figure>
</div>

<h2>引擎：市场需求确实跟着倍率走</h2>
<div class="pair even">
<figure>{pickup_chart()}
<figcaption>{sum(q['n'] for q in pk):,} 个“市场×商品”，取 12 个年份（1340、1350，此后每 50 年）。每个点把倍率相近的放在一起，点越大样本越多。已扣掉同一商品的平均水平和价格本身对需求的影响。</figcaption></figure>
<div>
<p>存档不记录每个国家修正最终生效了多少，只有市场上的人口需求总量。我用 SOL 自己的口径（人口 × 单位消费 × 地点修正）算出“不考虑替代时该有多少”，再看实际值和国家倍率的关系。</p>
<p>倍率越高，实际需求越高，排序完全一致：最低一组（约 ×{math.exp(big_cut['x']):.2f}）比中性组低 {pct(1-ratio(big_cut),0)}，最高一组（约 ×{math.exp(big_up['x']):.2f}）高 {pct(ratio(big_up)-1,0)}。
但是抬高的几组都高出了虚线，小幅压低的两组（×{math.exp(small_cut['x']):.2f}、×{math.exp(mid_cut['x']):.2f}）反而不低于中性组。这说明“中性组”本身偏低（里面混着引擎另有折扣的市场），所以不能拿单个点的高度当生效比例，只能看整体斜率。</p>
<p>这是间接证据，引擎还乘了价格、宗教、缺粮等 SOL 账本外的系数，所以只能看趋势。它够说明自动修正在起作用，大幅的负值也生效；但小幅压低到底有没有足额生效，还需要进游戏看一次人口需求明细。</p>
<figure>{slope_chart()}
<figcaption>每个年份单独拟合的传导系数，竖线为约 95% 区间。1 表示国家倍率每变 10%，市场需求也变 10%。1700 年以后都在 1 附近。</figcaption></figure>
</div>
</div>

<h2>三处漏洞</h2>
<div class="issue">
<h3>1. 新国家第二次刷新时把外部需求读错</h3>
<p>{len(pol)} 次（{pol_r2} 次发生在国家刚刷新过两次时），共 {pol_cells} 个商品的外部需求读数不是原版那种整齐的数（1、1.2、1.5），而是一个奇怪的值。其中 {pol_match} 个恰好等于“2 减去倍率”。</p>
<p>这和之前审计时担心的情况完全一致：新国家初始化时算一次，同一天月度脉冲又算一次，这期间引擎还没来得及把第一次的结果挂上去，脚本却按“已经挂上”把它扣掉了。
举例：某商品该抬高到 ×1.3，第二次刷新把外部需求读成 0.7，最后实际只抬了 ×1.21，SOL 账本里却记成 ×0.91，抬高变成了压低。</p>
<p>受影响的都是刚冒出来的小国，最多占世界人口 {max(r['polluted_pop_pct'] for r in D):.2f}%；到下一次刷新就自动恢复（{sum(1 for _ in pol)} 例中，下一档仍在世的都已恢复）。但年度刷新的 AI 要错一整年。</p>
</div>
<div class="issue">
<h3>2. 叛乱国并回母国后，修正留在母国身上</h3>
<p>{len(orph)} 个存档里各有一个国家，账本说某商品倍率是 ×1（不该有修正），身上却挂着修正。每一例都能在同一存档里找到一个刚灭亡的叛乱国（标记为 <code>某国_REVOLT_…</code>），它的这些数值和母国身上多出来的完全相同。
看起来是叛乱结束时，叛乱国的变量被并入了母国：母国已有的变量不动，母国当时没有的（也就是刚因倍率回到 1 而删掉的尺寸变量）被叛乱国的值补上。</p>
{orphan_table()}
<p>最大的一例是 1800 年的葡萄牙（397 块地，占世界人口 1.46%），玉米被多压了 8%。这些残留到母国下一次刷新时会被覆盖，所以最多持续一年。外部需求读数也不会被带歪，因为扣除时用的是同一个值。</p>
</div>
<div class="issue">
<h3>3. 灭亡国家的缓存从不清理</h3>
<div class="pair">
<figure>{dead_chart()}
<figcaption>按存档文本估算的字节数。1840 年存档总大小 {save_growth} MB，其中替代相关的死国家缓存约占 {pct(last['dead_mb']/save_growth)}。</figcaption></figure>
<div>
<p>清理写在“月度国家脉冲”里，条件是国家没有地块。但从结果看，国家灭亡后这段清理从没执行过，最可能的原因是引擎不再给灭亡国家跑月度脉冲（这点是推断，没有在原版文档里找到明确说明）。到 1840 年有 {last['dead_caches']:,} 个死国家仍挂着替代缓存，其中 {last['dead_sizes']:,} 个尺寸变量还在，比在世国家的缓存（{last['alive_mb']} MB）多一倍还多。</p>
<p>更实际的问题在复活时：死国家重新出现后，到它第一次年度刷新之前，会直接用灭亡前的旧值。全期 {len(rev)} 次，最久的一次是 {rev_old[0]['year']} 年的 {rev_old[0]['tag']}，用的是 {rev_old[0]['since']} 年的结果。同样只影响小国（最多占人口 {max(r['stale_pop_pct'] for r in D):.2f}%）。</p>
</div>
</div>
</div>
<div class="issue minor">
<h3>另外两个小现象，不需要修</h3>
<p>市场档位表里会留下已经消失的市场（1840 年有 {last['stale_market_keys']} 个），只是占地方，不影响计算。偶尔有新国家在存档那一刻还没初始化（全期 {noinit_total} 次），下个月就会补上。</p>
</div>

<h2>需要你拍板的事</h2>
<ol class="decide">
<li><b>新国家读错外部需求要不要修？</b>现在的做法是刷新时假设上一次的结果已经生效，所以同一天连算两次就会扣错。可以改成：如果这个国家本月已经算过，就沿用上次读到的外部需求，不再重读。我建议修，改动只在刷新开头加一个判断。</li>
<li><b>叛乱国并回留下的修正要不要处理？</b>选项一：不管，最多错一年，影响很小。选项二：每月顺手检查“账本说 ×1 但身上有尺寸变量”的商品并删掉，代价是每国每月多 56 次判断。我倾向于不管，或者只在叛乱结束的事件里清一次（需要先查有没有这样的 on_action）。</li>
<li><b>死国家缓存怎么清？</b>月度脉冲碰不到死国家，得换地方。可以在每年一月市场刷新时遍历一次所有国家，把没有地块的国家清掉；或者在国家灭亡的 on_action 里清。我建议前者，一年一次，成本可控，也顺带解决“复活后用旧值”的问题。</li>
<li><b>要不要进游戏核实小幅压低？</b>存档数据看不清 ×0.85～×0.95 这一段到底生效了多少。找一个替代倍率在这个区间的国家，打开某个人口的需求明细看一眼即可，十分钟左右。</li>
</ol>

<h2>方法与复现</h2>
<p>脚本在 <code>docs/analysis/sol_substitution_decades_20261023/</code>：<code>extract.py</code> 逐档读取国家缓存、地块人口、市场价格历史和全局档位表，并独立复算算法 A；
<code>demand_check.py</code> 对比市场人口需求；<code>analyze.py</code> 汇总成 <code>summary.json</code>；<code>build_report.py</code> 生成本页。中间结果在 <code>data/save_analysis/substitution_decades/</code>（不入库）。</p>
<p>几点口径说明：复算的价格用存档中月度价格历史倒数第 5 个值（即一月），它与游戏保存的档位逐一吻合；“外部需求读数异常”的判定是该值既不是 0.05 也不是 0.01 的整数倍；
残留修正的判定是存档里的尺寸变量不等于“外部需求 ×（倍率 − 1）”；引擎传导分析排除了基础量为 0 的市场。人类国家数为 0，所以人类每月刷新的路径没有被这份存档检验到。</p>
<pre class="src">$env:PYTHONUTF8='1'
& $env:EU5_PYTHON docs/analysis/sol_substitution_decades_20261023/extract.py --all
& $env:EU5_PYTHON docs/analysis/sol_substitution_decades_20261023/demand_check.py 1340 1350 1400 1450 1500 1550 1600 1650 1700 1750 1800 1840
& $env:EU5_PYTHON docs/analysis/sol_substitution_decades_20261023/analyze.py
& $env:EU5_PYTHON docs/analysis/sol_substitution_decades_20261023/build_report.py</pre>
</main>
"""

page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SOL 替代组 500 年验收</title><style>{CSS}</style></head><body>{body}</body></html>
"""
(HERE / "REPORT.html").write_text(page, encoding="utf-8")
print("wrote", HERE / "REPORT.html", len(page))

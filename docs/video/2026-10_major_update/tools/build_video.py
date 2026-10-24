# -*- coding: utf-8 -*-
"""Build the SOL Oct-2026 release video package: slides, placeholder cards,
subtitle-burned animatic, SRT, narration script and timing table.

Run: python3 build_video.py <out_dir> <project_root> [--title-only]
"""
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT, ROOT = sys.argv[1], sys.argv[2]
W, H = 1920, 1080
RATE = 4.6  # spoken units per second, measured from the 2026-04 SOL video (1958 chars / 431 s)
SANS_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
SANS_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FA = "/usr/share/fonts/truetype/font-awesome/fontawesome-webfont.ttf"
RED, BLUE, INK, GREY, GREEN = (200, 40, 40), (30, 90, 180), (30, 30, 30), (120, 120, 120), (40, 140, 60)
ICON = os.path.join(ROOT, "assets/icons/sol_living_standard.png")
VARIANTS = os.path.join(ROOT, "data/generated_icons/variants")


def font(size, bold=True):
    path = SANS_B if bold else SANS_R
    if os.path.exists(path):
        return ImageFont.truetype(path, size, index=2)
    # The Windows workstation has the same Noto Sans SC family as a variable font.
    f = ImageFont.truetype("C:/Windows/Fonts/NotoSansSC-VF.ttf", size)
    f.set_variation_by_name("Bold" if bold else "Regular")
    return f


def fa(size):
    return ImageFont.truetype(FA, size)


COL = {"r": RED, "b": BLUE, "g": GREEN, "k": INK, "y": GREY}


def rich(d, xy, text, size, bold=True, default=INK, anchor_center=False):
    """Draw text with {r:..} {b:..} {g:..} {y:..} colour spans."""
    parts = re.split(r"(\{[rbgky]:[^}]*\})", text)
    f = font(size, bold)
    segs = []
    for p in parts:
        if not p:
            continue
        m = re.match(r"\{([rbgky]):(.*)\}", p)
        segs.append((m.group(2), COL[m.group(1)]) if m else (p, default))
    total = sum(d.textlength(s, font=f) for s, _ in segs)
    x, y = xy
    if anchor_center:
        x -= total / 2
    for s, c in segs:
        d.text((x, y), s, font=f, fill=c)
        x += d.textlength(s, font=f)
    return total


def slide(title):
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 130], fill=(245, 245, 245))
    d.rectangle([0, 130, W, 136], fill=RED)
    rich(d, (90, 30), title, 60)
    if os.path.exists(ICON):
        ic = Image.open(ICON).convert("RGBA").resize((104, 104))
        im.paste(ic, (W - 150, 14), ic)
    return im, d


def bullets(d, items, top=210, size=50, gap=105, left=150):
    y = top
    for it in items:
        d.ellipse([left - 40, y + size * 0.45, left - 22, y + size * 0.45 + 18], fill=RED)
        rich(d, (left, y), it, size)
        y += gap
    return y


def bubble(im, d, xy, who, text, color, side="left", w=1050, icon=None):
    x, y = xy
    f = font(46)
    # avatar
    ax = x if side == "left" else x + w + 40
    d.ellipse([ax, y, ax + 130, y + 130], fill=color)
    if icon is not None:
        ic = icon.resize((110, 110))
        im.paste(ic, (ax + 10, y + 10), ic)
    else:
        d.text((ax + 65, y + 65), "", font=fa(70), fill="white", anchor="mm")
    d.text((ax + 65, y + 150), who, font=font(32), fill=INK, anchor="mm")
    bx = x + 170 if side == "left" else x - 30
    lines = wrap(d, text, f, w - 60)
    bh = 50 + 62 * len(lines)
    d.rounded_rectangle([bx, y + 10, bx + w, y + 10 + bh], radius=36, fill=(238, 243, 250) if side == "left" else (252, 238, 236), outline=color, width=4)
    for i, ln in enumerate(lines):
        rich(d, (bx + 34, y + 30 + 62 * i), ln, 46)


def wrap(d, text, f, maxw):
    out, cur = [], ""
    plain = re.sub(r"\{[rbgky]:([^}]*)\}", r"\1", text)
    if d.textlength(plain, font=f) <= maxw:
        return [text]
    for ch in plain:
        if d.textlength(cur + ch, font=f) > maxw:
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return out


def save(im, name):
    p = os.path.join(OUT, "slides", name + ".png")
    im.save(p)
    return p


os.makedirs(os.path.join(OUT, "slides"), exist_ok=True)
os.makedirs(os.path.join(OUT, "_frames"), exist_ok=True)
sol_icon = Image.open(ICON).convert("RGBA") if os.path.exists(ICON) else None

# ---------------- slides ----------------
S = {}

# T00 title card (dark, usable alone) + transparent overlay for key art
for variant in ("full", "overlay"):
    if variant == "full":
        im = Image.new("RGB", (W, H), (22, 26, 34))
        g = Image.new("L", (W, H))
        gd = ImageDraw.Draw(g)
        for r in range(0, 900, 6):
            gd.ellipse([W / 2 - r * 1.4, H / 2 - r, W / 2 + r * 1.4, H / 2 + r], outline=max(0, 60 - r // 15))
        im.paste((60, 48, 30), (0, 0, W, H), g.filter(ImageFilter.GaussianBlur(40)))
    else:
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        band = Image.new("RGBA", (W, 520), (0, 0, 0, 150))
        im.paste(band, (0, (H - band.height) // 2), band)
    d = ImageDraw.Draw(im)
    title_lines = [
        ("Standard of Living", font(130), "white"),
        ("大版本更新：替代组回归 · 生活水平 · 全新界面", font(58), (240, 200, 120)),
    ]
    bounds = [d.textbbox((0, 0), text, font=f) for text, f, _ in title_lines]
    gap = 44
    y = (H - sum(b[3] - b[1] for b in bounds) - gap) / 2
    for (text, f, color), (left, top, right, bottom) in zip(title_lines, bounds):
        # Center the visible glyphs, including both lines as one vertical block.
        x = (W - (right - left)) / 2 - left
        d.text((x, y - top), text, font=f, fill=color)
        y += bottom - top + gap
    if sol_icon is not None and variant == "full":
        ic = sol_icon.resize((200, 200))
        im.paste(ic, (W // 2 - 100, 790), ic)
    p = os.path.join(OUT, "slides", f"T00_title_{variant}.png")
    im.save(p)
S["T00"] = os.path.join(OUT, "slides", "T00_title_full.png")

if "--title-only" in sys.argv:
    raise SystemExit(0)


def timeline(stage):
    im, d = slide("替代组的一生")
    xs = [330, 960, 1590]
    labels = ["EU5 1.1", "EU5 1.2", "EU5 1.4 · 本次更新"]
    d.line([200, 330, 1720, 330], fill=GREY, width=6)
    for i, x in enumerate(xs):
        on = i <= stage
        d.ellipse([x - 26, 304, x + 26, 356], fill=RED if on else (210, 210, 210))
        d.text((x, 410), labels[i], font=font(54), fill=INK if on else (200, 200, 200), anchor="mm")
    if stage >= 0:
        for yy, lab in ((490, "替代组"), (570, "恩格尔曲线")):
            d.text((150, yy + 8), "\uf00c", font=fa(50), fill=GREEN)
            rich(d, (220, yy), lab, 54)
        rich(d, (150, 650), "{y:（当年的得意之作）}", 40)
    if stage >= 1:
        d.text((960, 600), "", font=fa(300), fill=(150, 110, 80), anchor="mm")
        rich(d, (960, 790), "Johan 的大手", 54, anchor_center=True)
        rich(d, (960, 860), "{r:接口：已摧毁}", 50, anchor_center=True)
        d.line([140, 500, 540, 720], fill=RED, width=10)
        d.line([140, 720, 540, 500], fill=RED, width=10)
    if stage >= 2:
        for k, dx in enumerate((-150, -50, 50, 150)):
            d.text((1590 + dx, 700 + (k % 2) * 16), "\uf06d", font=fa(120), fill=(235, 90 + k * 35, 30), anchor="mm")
        if sol_icon is not None:
            ic = sol_icon.resize((230, 230))
            im.paste(ic, (1590 - 115, 420), ic)
        rich(d, (1590, 790), "{r:替代组：从地狱归来}", 54, anchor_center=True)
        rich(d, (1590, 870), "{y:恩格尔曲线：那我呢？}", 36, anchor_center=True)
    return im


for i, n in enumerate("abc"):
    S[f"P01{n}"] = save(timeline(i), f"P01{n}_timeline")

im, d = slide("这次更新做了什么？")
y = 260
for num, head, sub in (("1", "替代组回归", "贵了就换着买"), ("2", "生活水平加入建筑修正", "钱，加上钱买不到的东西"), ("3", "界面完全重做", "四格信息栏 + 四个地图模式")):
    d.ellipse([170, y, 290, y + 120], fill=RED)
    d.text((230, y + 60), num, font=font(70), fill="white", anchor="mm")
    rich(d, (340, y + 4), head, 66)
    rich(d, (340, y + 84), "{y:" + sub + "}", 40, bold=False)
    y += 230
S["P02"] = save(im, "P02_three_things")

for stage in (0, 1):
    im, d = slide("替代组：贵了就换着买")
    bubble(im, d, (120, 220), "农民", "小麦涨到{r:两倍价}了……", (120, 150, 90))
    bubble(im, d, (560, 470), "原版", "规定就是规定，小麦{r:一粒都不能少}。", (110, 110, 110), side="right", w=1050)
    if stage == 1:
        d.rectangle([555, 465, 1890, 700], fill=(255, 255, 255))
        bubble(im, d, (560, 470), "原版", "规定就是规定，小麦{r:一粒都不能少}。", (200, 200, 200), side="right", w=1050)
        d.line([560, 524, 1560, 524], fill=RED, width=7)
        bubble(im, d, (560, 760), "SOL", "那今年多吃点{b:小米}和{b:豆子}吧。", (240, 200, 140), side="right", w=1050, icon=sol_icon)
    S[f"P03{'ab'[stage]}"] = save(im, f"P03{'ab'[stage]}_bubble_wheat")

GROUPS = {
    "必需": ["主粮", "蛋白质", "基本衣物", "取暖", "粗制品"],
    "日用": ["调味", "家用", "体面衣物", "酒与烟草", "药材", "祭祀", "书写"],
    "奢侈": ["珍馐", "奢侈饮品", "奢侈品", "香料", "贵金属", "珍宝", "武器", "坐骑"],
}
im, d = slide("56 种商品 · 20 个替代组")
y = 200
tint = {"必需": (230, 240, 230), "日用": (230, 236, 248), "奢侈": (250, 236, 226)}
for tier, gs in GROUPS.items():
    d.text((110, y + 52), tier, font=font(54), fill=RED, anchor="lm")
    x = 290
    for g in gs:
        tw = d.textlength(g, font=font(42)) + 50
        if x + tw > 1850:
            x = 290
            y += 110
        d.rounded_rectangle([x, y, x + tw, y + 90], radius=18, fill=tint[tier])
        d.text((x + tw / 2, y + 45), g, font=font(42), fill=INK, anchor="mm")
        x += tw + 22
    y += 150
rich(d, (110, 840), "每个阶层{r:按整组消费}：农民需要的是{b:「主粮」}，不一定非得是小麦", 46)
rich(d, (110, 910), "{y:部分商品同属多个组，比如葡萄酒既是日常饮品，也是奢侈饮品}", 36, bold=False)
S["P04"] = save(im, "P04_groups")

im, d = slide("组内按价格分七档")
tiers = [("< 0.40", "×2", GREEN), ("0.40–0.65", "×1.5", GREEN), ("0.65–0.85", "×1.25", GREEN), ("0.85–1.30", "×1", GREY), ("1.30–1.70", "×0.75", RED), ("1.70–2.30", "×0.5", RED), ("> 2.30", "×0.25", RED)]
bw = 230
for i, (rng, wgt, c) in enumerate(tiers):
    x = 140 + i * (bw + 15)
    hh = {"×2": 420, "×1.5": 330, "×1.25": 270, "×1": 220, "×0.75": 170, "×0.5": 120, "×0.25": 70}[wgt]
    d.rectangle([x, 730 - hh, x + bw, 730], fill=c)
    d.text((x + bw / 2, 730 - hh - 45), wgt, font=font(52), fill=c, anchor="mm")
    d.text((x + bw / 2, 775), rng, font=font(34, False), fill=INK, anchor="mm")
rich(d, (140, 840), "横轴：{b:市场价 ÷ 基础价}　　柱高：{b:购买偏好}", 42)
rich(d, (140, 905), "越便宜越受欢迎，{r:越贵越没人买}；整组的需求在成员之间{b:重新分配}", 42)
S["P05"] = save(im, "P05_price_tiers")

im, d = slide("购买力 ≠ 生活水平")
for x, head, c, lines in ((120, "购买力", BLUE, ["手里的钱，", "够买多少基本生活所需", "", "→ 决定{b:买多少东西}"]),
                          (1000, "生活水平", RED, ["钱，", "{r:加上钱买不到的东西}", "", "→ 影响{r:移民}、{r:人口增长}、{r:排名}"])):
    d.rounded_rectangle([x, 210, x + 800, 860], radius=30, outline=c, width=6)
    d.text((x + 400, 290), head, font=font(80), fill=c, anchor="mm")
    yy = 420
    for ln in lines:
        if ln:
            rich(d, (x + 60, yy), ln, 48)
        yy += 90
rich(d, (W / 2, 895), "{y:生活水平加成不会凭空变出钱，也不会改变需求}", 40, bold=False, anchor_center=True)
S["P06"] = save(im, "P06_pp_vs_sol")

im, d = slide("首批 17 种建筑影响生活水平")
cols = [("+", "固定值提高", GREEN, "", ["医院", "隔离所 · 疫病院", "引水渠", "著名医疗机构"], "关乎生存：对穷人最重要"),
        ("−", "固定值降低", RED, "", ["制革作坊/工场/厂", "腐化处理作坊/厂", "炼铁厂 · 炼钢厂"], "污染"),
        ("%", "按比例提高", BLUE, "", ["剧院", "歌剧院", "图书馆"], "关乎品质：越富裕越明显")]
for i, (sym, head, c, glyph, items, foot) in enumerate(cols):
    x = 110 + i * 590
    d.rounded_rectangle([x, 190, x + 550, 830], radius=28, fill=(250, 250, 250), outline=c, width=5)
    d.text((x + 120, 285), glyph, font=fa(105), fill=c, anchor="mm")
    d.text((x + 330, 285), sym, font=font(125), fill=c, anchor="mm")
    d.text((x + 275, 405), head, font=font(50), fill=c, anchor="mm")
    yy = 480
    for it in items:
        d.text((x + 275, yy), it, font=font(44), fill=INK, anchor="mm")
        yy += 80
    d.text((x + 275, 785), foot, font=font(32, False), fill=GREY, anchor="mm")
S["P07"] = save(im, "P07_buildings")

im, d = slide("生活水平不只是一个数字")
bubble(im, d, (120, 220), "市民", "隔壁城里有{b:医院}，还有{b:歌剧院}！", (190, 150, 60))
bubble(im, d, (560, 480), "SOL", "那就搬过去吧。", (240, 200, 140), side="right", w=1050, icon=sol_icon)
rich(d, (180, 790), "{g:▲} 生活水平越高 → {g:移民吸引力}越高", 48)
rich(d, (180, 870), "{r:▼} 生活水平太低 → 人口增长{r:变慢}；足够高 → {g:变快}", 48)
S["P08"] = save(im, "P08_bubble_migration")

im, d = slide("国家按钮下方：四格信息栏")
cells = [("1", "生活水平", "等级徽章 + 同比"), ("2", "购买力", "各阶层的钱够不够花"), ("3", "商品替代", "所有替代组的供应"), ("4", "全球排名", "国家与各阶层")]
for i, (n, a, b) in enumerate(cells):
    x = 110 + i * 435
    d.rounded_rectangle([x, 250, x + 410, 620], radius=24, fill=(40, 46, 58))
    d.ellipse([x + 160, 280, x + 250, 370], fill=RED)
    d.text((x + 205, 325), n, font=font(56), fill="white", anchor="mm")
    d.text((x + 205, 440), a, font=font(56), fill="white", anchor="mm")
    d.text((x + 205, 540), b, font=font(34, False), fill=(210, 210, 210), anchor="mm")
rich(d, (110, 720), "{b:悬停}：预览对应地图模式　　{b:点击}：切换过去", 52)
rich(d, (110, 810), "原来的「生活水平」局势已{r:移除}，信息全部搬到了这里", 46)
S["P10"] = save(im, "P10_topbar_schema")

im, d = slide("图标全部重画")
names = [("sol_living_standard", "生活水平"), ("sol_purchasing_power", "购买力"), ("sol_substitution", "商品替代"), ("sol_ranking", "排行榜")]
for i, (k, lab) in enumerate(names):
    p = os.path.join(VARIANTS, k + ".png")
    x = 170 + i * 420
    if os.path.exists(p):
        ic = Image.open(p).convert("RGBA").resize((300, 300))
        im.paste(ic, (x, 260), ic)
    d.text((x + 150, 640), lab, font=font(52), fill=INK, anchor="mm")
rich(d, (W / 2, 800), "{y:一碗面包、奶酪、苹果和麦穗 —— 四个地图模式各带一个角标}", 42, bold=False, anchor_center=True)
S["P11"] = save(im, "P11_icons")

im, d = slide("其他改动")
bullets(d, ["按 {b:1340 年各国中位数}重新校准各阶层基础消费",
            "AI 默认{b:每年}结算一次经济，玩家仍按月",
            "SOL 独立版与 {b:PP / M&T / Just Goods} 兼容子模组同步更新",
            "改动较大，{r:强烈建议开新档}"], top=240, size=54, gap=150)
S["P12"] = save(im, "P12_misc")

im, d = slide("欢迎订阅与反馈")
bullets(d, ["Steam 创意工坊：{b:Standard of Living}",
            "QQ 群：{b:1070041687}",
            "Discord：{b:discord.gg/Yy87G2hBHz}",
            "完整说明：GitHub Wiki / B站专栏"], top=240, size=56, gap=140)
S["P13"] = save(im, "P13_ending")

# ---------------- user footage placeholders ----------------
U = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots.json"), encoding="utf-8"))
for k, v in U.items():
    im = Image.new("RGB", (W, H), (52, 56, 64))
    d = ImageDraw.Draw(im)
    d.rectangle([60, 60, W - 60, H - 60], outline=(240, 200, 120), width=6)
    d.text((W / 2, 330), f"【素材 {k}】请替换为你的游戏录屏/截图", font=font(60), fill=(240, 200, 120), anchor="mm")
    ln = wrap(d, v["what"], font(46), 1600)
    for i, t in enumerate(ln):
        d.text((W / 2, 480 + i * 70), t, font=font(46, False), fill="white", anchor="mm")
    S[k] = save(im, f"_placeholder_{k}")

# ---------------- timeline ----------------
SC = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "script.json"), encoding="utf-8"))


def units(t):
    return len(re.findall(r"[一-鿿]", t)) + len(re.findall(r"[A-Za-z0-9&]+", t))


t = 0.0
rows, srt, frames = [], [], []
# silent title card
frames.append((S["T00"], None, 4.0))
t = 4.0
for sc in SC:
    st = t
    for line, vis in sc["lines"]:
        dur = max(1.4, units(line) / RATE) + 0.25
        srt.append((t, t + dur - 0.1, line))
        frames.append((S[vis], line, dur))
        t += dur
    t += sc.get("pause", 0.4)
    frames[-1] = (frames[-1][0], frames[-1][1], frames[-1][2] + sc.get("pause", 0.4))
    rows.append((sc["id"], sc["name"], st, t, sum(units(l) for l, _ in sc["lines"])))


def ts(x, sep=","):
    h, r = divmod(x, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}"


with open(os.path.join(OUT, "subtitles_estimated.srt"), "w", encoding="utf-8") as f:
    for i, (a, b, l) in enumerate(srt, 1):
        f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{l}\n\n")

with open(os.path.join(OUT, "timing.json"), "w", encoding="utf-8") as f:
    json.dump({"total_seconds": round(t, 1), "scenes": [dict(id=a, name=b, start=round(c, 1), end=round(e, 1), units=u) for a, b, c, e, u in rows]}, f, ensure_ascii=False, indent=1)

# narration script for recording
with open(os.path.join(OUT, "口播稿.txt"), "w", encoding="utf-8-sig") as f:
    for sc in SC:
        f.write(f"【{sc['id']} {sc['name']}】\n")
        for line, vis in sc["lines"]:
            f.write(line + "\n")
        f.write("\n")

# animatic frames with burned subtitles
lst = []
sf = font(52)
for i, (img, line, dur) in enumerate(frames):
    im = Image.open(img).convert("RGB")
    if line:
        d = ImageDraw.Draw(im)
        d.text((W / 2, H - 70), line, font=sf, fill="white", anchor="mm", stroke_width=5, stroke_fill="black")
    p = os.path.join(OUT, "_frames", f"f{i:03d}.png")
    im.save(p)
    lst.append(f"file '{p}'\nduration {dur:.3f}\n")
lst.append(f"file '{p}'\n")
open(os.path.join(OUT, "_frames", "list.txt"), "w").write("".join(lst))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(OUT, "_frames", "list.txt"),
                "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-crf", "28", os.path.join(OUT, "animatic_粗剪预览.mp4")], check=True)
print("total", round(t, 1), "s")
for r in rows:
    print(r)

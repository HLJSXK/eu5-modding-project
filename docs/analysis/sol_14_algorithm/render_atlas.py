"""Generate the reviewed SOL algorithm SVG figures; no game files are changed."""
from pathlib import Path
import html
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = Path(__file__).resolve().parent
INK, MUTED, TEAL, BLUE, RED = '#19354a', '#546b7b', '#147d73', '#2563a1', '#bd4d45'
COLORS = {'blue': ('#edf4fc', BLUE), 'teal': ('#edf8f4', TEAL),
          'gold': ('#fff7e6', '#ad7124'), 'red': ('#fff1ed', RED), 'gray': ('#f1f4f6', MUTED)}


class Figure:
    def __init__(self, num, title, subtitle, height=1000):
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="{height}" viewBox="0 0 1440 {height}" role="img" aria-labelledby="title desc">',
                      f'<title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(subtitle)}</desc>',
                      '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z" fill="#7d909e"/></marker></defs>',
                      '<rect width="1440" height="100%" fill="white"/>']
        self.text(48, 46, f'SOL / 1.4     ALGORITHM ATLAS     {num:02}', 16, TEAL, 700)
        self.text(48, 99, title, 32, INK, 700)
        self.text(48, 135, subtitle, 17, MUTED)
        self.line(48, height - 47, 1392, height - 47, False)
        self.text(48, height - 20, '2026-10-15 · substitution / 5bc51c51 · 源码与离线计数，不代表 EU5 实测秒数', 14, MUTED)
        self.text(1330, height - 20, f'{num:02} / 06', 14, MUTED)

    def text(self, x, y, value, size=20, color=INK, weight=400):
        self.parts.append(f'<text x="{x}" y="{y}" font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{html.escape(str(value))}</text>')

    def rect(self, x, y, w, h, fill, stroke='none', radius=12):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def box(self, x, y, w, h, title, lines, kind='blue', tag=None):
        fill, color = COLORS[kind]
        self.rect(x, y, w, h, fill, '#dce5eb')
        self.rect(x, y, 5, h, color, radius=2)
        self.text(x + 20, y + 34, title, 22, color, 700)
        for i, content in enumerate(lines):
            self.text(x + 20, y + 65 + 27 * i, content, 17)
        if tag:
            self.text(x + 20, y + h - 18, tag, 17, color, 700)

    def line(self, x1, y1, x2, y2, arrow=True, dashed=False):
        marker = ' marker-end="url(#arrow)"' if arrow else ''
        dash = ' stroke-dasharray="6 5"' if dashed else ''
        self.parts.append(f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="#7d909e" stroke-width="2"{marker}{dash}/>')

    def path(self, points):
        self.parts.append(f'<polyline points="{points}" fill="none" stroke="#7d909e" stroke-width="2" marker-end="url(#arrow)"/>')

    def save(self, name):
        (HERE / name).write_text('\n'.join(self.parts) + '\n</svg>\n', encoding='utf-8')


f = Figure(1, '过月时，究竟是哪条路径在运行？', '默认 CMF：人类每月求解；降频 AI 每月检查，年度或 dirty 时才完整求解。', 1020)
f.box(48, 175, 420, 148, '世界市场缓存', ['一月 / 缺失时刷新；加载时全刷新', '缓存供给、价格权重与逐商品支出'], 'teal', '世界市场数 W × 商品 / 人口条目')
f.box(510, 175, 420, 148, '人类 / 未开启降频的 AI', ['每月直接进入完整国家求解', '不用先走 AI clean / dirty 分流'], 'blue', '每月一次完整链')
f.box(972, 175, 420, 148, '降频 AI', ['月度检查：领土、市场、商品修正', '自身年度 pulse：完整求解并应用'], 'gold', 'clean 月仍做 O(N + G) 检查')
f.line(720, 323, 720, 443)
f.text(743, 380, '每月', 16, BLUE)
f.path('1182,323 1182,385 980,385 980,443')
f.text(990, 371, 'dirty / 年度 / 首次无缓存', 16, '#ad7124')
f.path('1275,323 1413,323 1413,740 1392,740')
f.text(1140, 420, 'clean：跳过完整链', 16, TEAL)
f.line(258, 323, 258, 443, dashed=True)
f.text(278, 381, '提供缓存输入', 16, TEAL)
f.rect(34, 430, 1372, 225, '#f7f9fb', '#cddbe4')
f.text(54, 462, '完整国家求解 sol_solve_country_pop_demand', 20, INK, 700)
f.box(55, 483, 302, 150, '① 国家商品替代', ['按市场 × 人口类型算响应', '得到每种商品统一倍率 M'], 'teal', '图 2 · 图 3')
f.box(398, 483, 302, 150, '② 地点 raw 系数', ['市场总支出 × 地点人口', '资金 ÷ 基础支出 → α'], 'blue', '每个地点一次')
f.box(741, 483, 302, 150, '③ 国家四阶层求解', ['分类 + 4×4 精确解', '必要时 209 候选 sweep'], 'gold', 'N < 5 / 求解关闭时跳过')
f.box(1084, 483, 302, 150, '④ 缓存最终系数', ['有解：β = α × 类系数', '否则：保留 raw α'], 'blue', '供每月地点 modifier 复用')
for x in (357, 700, 1043):
    f.line(x, 557, x + 41, 557)
f.line(1235, 655, 1235, 689)
f.box(744, 689, 648, 121, '每月应用地点 modifier', ['size = β − 1；有效期一个月；逐地点续写'], 'gold', 'clean AI 也支付 O(N) 次写入')
f.box(48, 689, 648, 121, 'UI 与地图', ['读取已有 SOL / 商品缓存；人类有独立面板刷新'], 'gray', '面板绘制不等于每国再做 209 次求解')
f.line(744, 745, 696, 745, dashed=True)
f.box(48, 842, 1344, 105, '最容易误读的门槛', ['小国早退发生在①之后：N < 5 不免除替代组和地点 raw 计算。', 'AI 年度刷新按各国周年分散；世界市场缓存的一月刷新是另一条调度。'], 'red')
f.save('01_monthly_dispatch.svg')

f = Figure(2, '替代组 Algorithm A：从价格到一个国家倍率', 'G = 56 商品，P = 7 人口类型，20 组，H = 67 成员关系；一个商品可以属于多个组。', 1120)
f.box(48, 175, 420, 165, '① 市场价格档位', ['r = 市场价 / 默认价', 'r 越低，分段权重 w 越高', '偏好固定为 1；无恩格尔/时代缩放'], 'teal')
f.box(510, 175, 420, 165, '② 每类人口的有效成员', ['有供给；消费常量 q > 0', '外部需求基准 E > 0', 'E=max(1+总修正−实际自身,0)'], 'blue')
f.box(972, 175, 420, 165, '③ 汇总本国市场人口', ['n[m,p]=Σ 同市场拥有地点人口', '同市场地点共用篮子响应', '没有逐人口实体循环'], 'teal')
f.line(468, 255, 510, 255)
f.line(930, 255, 972, 255)
f.rect(48, 369, 1344, 90, '#f1f4f6')
f.text(69, 400, '价格比 r', 17, MUTED, 700)
f.text(69, 436, '权重 w', 17, MUTED, 700)
for i, (r, w) in enumerate([('<0.40', '2.00'), ('[0.40,0.65)', '1.50'), ('[0.65,0.85)', '1.25'), ('[0.85,1.30]', '1.00'), ('(1.30,1.70]', '0.75'), ('(1.70,2.30]', '0.50'), ('>2.30', '0.25')]):
    f.text(208 + 166 * i, 400, r, 16)
    f.text(230 + 166 * i, 436, w, 18, TEAL, 700)
f.box(48, 490, 648, 218, '④ 每个“市场 × 人口类型”遍历各组', ['每组两次成员扫描：先计数/总权重，再分配', 'C[g] += 历史组规模 × w[g] / Σ 有效成员 w', 'Z[g] += 历史组规模 / 有效成员个数', '跨组响应 D[m,p,g] = C[g] / Z[g]；无分母时 1'], 'blue', '20 组顺序遍历，不是组间笛卡尔积')
f.box(744, 490, 648, 218, '⑤ 将各市场/人口响应压成国家倍率', ['基准权重 b = n[m,p] × q[p,g] × 默认价[g]', 'M[g] = Σ b × D / Σ b；无基准时 M = 1', '同商品的默认价在比值中抵消', '不是按地点 raw α 或当前市价加权'], 'teal', '价格权重相同，人口资格不同，D 仍可不同')
f.path('1182,340 1182,352 1413,352 1413,475 372,475 372,490')
f.line(696, 592, 744, 592)
f.box(48, 751, 648, 170, '⑥ 写为加法 modifier', ['目标 size[g] = E[g] × (M[g] − 1)', '只在值变化 / 丢失 / 实际强度漂移时写入', '永久 country modifier；零 size 删除自身修正'], 'gold', '内部有效值=max(E+写入后实际强度,0)')
f.box(744, 751, 648, 170, '两商品例子：解释规则，不是实机预测', ['同组规模 2；w[A]=0.5，w[B]=1', 'D[A]=2/3，D[B]=4/3；中性贡献均为 1', '基准数量 90:10 → 60:13.33'], 'gray', 'Algorithm A 不保证数量或预算守恒')
f.path('1068,708 1068,731 372,731 372,751')
f.text(48, 980, '当前一次替代刷新：O(G + N·P + M·(G + Q + R))', 27, INK, 700)
f.text(48, 1025, 'N=地块，M=该国市场；Q=215 个正消费条目，R=271 个有消费的组成员×人口条目。', 18, MUTED)
f.save('02_substitution_algorithm.svg')

f = Figure(3, '三层缓存：真正省下的是重复展开', '世界市场明细共享；国家保存倍率；带 owner 的市场总支出只允许对应国家复用。', 960)
f.box(48, 181, 330, 183, 'L1 · 世界市场明细', ['键：市场 / 商品 / 人口类型', '价格档位、供给、q × 有效价', '一月 / 加载 / 缺失时刷新'], 'teal', '有效价=min(市场价,默认价)')
f.box(555, 181, 330, 183, 'L2 · 国家商品倍率', ['每国商品：E、M、实际 own', '人类月度；AI 年度或 dirty', '仅改变时写商品 modifier'], 'gold', 'A 国的 M 不可给 B 国使用')
f.box(1062, 181, 330, 183, 'L3 · 市场七类总支出', ['u=Σ 商品明细 × 有效倍率', '市场 key + owner=c 标记', '首次计算，后续地点读总数'], 'blue', '非永久二维 (c,m) 缓存')
f.line(378, 272, 555, 272)
f.text(399, 254, '读市场输入', 16, MUTED)
f.line(885, 272, 1062, 272)
f.text(907, 254, '逐商品乘倍率', 16, MUTED)
f.box(48, 410, 648, 190, '180 地点 / 3 市场 / 7 类人口', ['旧：180 × 7 篮子；180 × 215 商品支出条目', '今：3 × 7 篮子；3 × 215 商品支出条目', '另付 180 × 7 次总支出读取和人口聚合'], 'teal', '复用比例来自 N/M；单地点没有这项红利')
f.box(744, 410, 648, 190, '共享市场：A → B → A', ['A 写 owner=A；A 后续地点命中', 'B 看到 owner≠B → 重算并改 owner=B', 'A 再来必须重算，不能误用 B 的倍率'], 'gold', '按国家连续遍历：O(M·Q + N·P)')
f.path('1227,364 1227,390 1068,390 1068,410')
f.box(48, 644, 648, 178, '什么时候失效？', ['世界市场刷新 → 清除对应 owner', '国家替代刷新 → 清除该国所涉市场 owner', '下次地点读取 → 惰性重建七类总支出'], 'blue', '临时市场人口 map 用完即移除')
f.box(744, 644, 648, 178, '空间复杂度与实现边界', ['世界 O(W·(G+Q+P))；各国 O(C·G)', '地点系数/快照 O(L)；临时人口 O(M·P)', '4×4 求解状态固定；原生 map/getter 内耗未知'], 'gray', '共享缓存反复换 owner 会再次付重建成本')
f.text(48, 875, '小国提醒：1 地点 / 1 市场的替代变量操作 3,855 → 4,163；并非每条路径都变快。', 19, RED, 700)
f.save('03_cache_hierarchy.svg')

f = Figure(4, '地点 α 与国家 β：昂贵部分如何被再次调用', '替代刷新后才判断 N≥5 与求解开关；商品替代本身不是 209 候选搜索。', 1170)
f.box(48, 176, 420, 179, '① 地点 raw 闭合', ['F = 非负净收入 × 非负资金倍率', 'B = Σ 7 类人口 × 单位支出', 'α=max(F/B,0)；B=0 时 α=1'], 'blue', 'α 无上限；±50% 是 UI 展示刻度')
f.box(510, 176, 420, 179, '② 四类地点分组', ['贵族 / 教士 / 市民 / 下层', '相对代表度评分 → confidence排序', '扣已分配容量惩罚，再决定类别'], 'teal', '多遍 O(N) + 排序 S(N)')
f.box(972, 176, 420, 179, '③ 4×4 国家矩阵', ['A[s,k]=Σ k类地点 α[l]×B[l,s]', 't[s]=Σ 该阶层地点资金', '下层=commoners+tribesmen'], 'blue', 'A·f=t；最终 β[l]=α[l]·f[k]')
f.line(468, 263, 510, 263)
f.line(930, 263, 972, 263)
f.box(48, 408, 420, 173, '④ 开启精确求解？', ['4×4 消元，负系数与残差验证', '成功 → strategy 7，直接采用', '关闭 / 失败 → 近似分流'], 'blue', 'O(K³)，固定 K=4')
f.box(510, 408, 420, 173, '⑤ 近似开启且 raw 超容差？', ['条件不满足 → 保持 raw', '满足 → 以 f=(1,1,1,1) 为起点', '把 raw 误差设为双重不退步上界'], 'gold', '原 solver 在 1.3 支持版本已存在')
f.box(972, 408, 420, 173, '⑥ 209 种固定候选组合', ['选 exact 行 + 归零列 + 行排列', '每种解 ≤4 维子系统，再评分', '候选须通过非负与误差门槛'], 'red', 'O(V·K³)，K=4、V=209')
f.path('1182,355 1182,384 258,384 258,408')
f.line(468, 495, 510, 495)
f.line(930, 495, 972, 495)
f.box(48, 624, 648, 177, '接受与回退', ['相对误差均值 L1、最大值 L∞ 均不得比 raw 差', '优先 L1；1% tie 区间比较 L∞', '有可采纳改进 → strategy 8；否则 f=1'], 'teal', 'raw 始终保留，不强制接受候选')
f.box(744, 624, 648, 177, '209 从哪里来？', ['V = Σ(k=0..4) C(4,k)² × k!', '   = 1 + 16 + 72 + 96 + 24 = 209', '行排列覆盖无换行消元的不同枢轴顺序'], 'gold', '固定维度时 O(1)，不意味着执行便宜')
f.path('1182,581 1182,603 372,603 372,624')
f.box(48, 844, 1344, 106, '分类与排序的边界', ['每类至少有总 raw 支出 1% 的目标容量，其余 96% 按 raw 超支压力分配；不是四等分。', 'S(N) 是原生排序成本；常规比较排序可估 O(N log N)，引擎实现未测。'], 'gray')
f.text(48, 997, '完整刷新 = 替代 + 单位支出/地点 raw + 分类排序 + 当次求解分支 + 地点应用', 23, INK, 700)
f.text(48, 1040, '固定商品与四类维度后：随地块增长主要为 O(N + M + S(N))，再乘当月触发次数。', 20, MUTED)
f.text(48, 1080, '推广到 K 类时 V(K)=Σ C(K,k)²k! 是组合增长；当前运行时 K 固定为 4。', 19, MUTED)
f.save('04_country_solver.svg')

f = Figure(5, '为什么替代开关可能放大整条月度链？', 'dirty = 缓存已失效、必须同步；它决定 AI 年度求解能否在普通月省掉。', 1070)
f.box(48, 176, 420, 178, '当前每月 guard', ['查初始化 / 开关 / 领土 / 市场', '再查 56 个商品原始总修正', '原始总值相同：clean 快路'], 'blue', 'clean 最坏遍历 O(N + G)')
f.box(510, 176, 420, 178, '总值变化时回读', ['读取实际 own，区分自身漂移', 'E_now=max(1+total−own,0)', '外部未变则只更新 observed'], 'teal', '当前下限已使用 value 算术块')
f.box(972, 176, 420, 178, '确实 dirty 时', ['替代刷新 → 全部地点 raw', '→ 分类矩阵 → 精确 / sweep', '→ 新快照与最终系数'], 'gold', '替代失效会触发已有 solver')
f.line(468, 263, 510, 263)
f.line(930, 263, 972, 263)
f.text(48, 412, '历史故障链 · 旧存档实证 · 当前 clamp 已修复', 25, RED, 700)
f.box(48, 440, 300, 172, '总修正回读滞后', ['actual own 已变化', 'aggregate 随后才追上', '下一月进入细查'], 'red')
f.box(396, 440, 300, 172, '旧 effect 的 min=0', ['正确 E 本应为 1', '旧写法把它压成 0', '误报外部需求变化'], 'red')
f.box(744, 440, 300, 172, 'AI 大规模误报 dirty', ['年度缓存无法复用', '普通月重跑完整链', '又更新 own / observed'], 'red')
f.box(1092, 440, 300, 172, '下一月重复', ['不仅多算替代篮子', '也重跑已有国家求解', '持续额外工作'], 'red')
for x in (348, 696, 1044):
    f.line(x, 526, x + 48, 526)
f.path('1242,612 1242,650 198,650 198,612')
f.box(48, 698, 648, 192, '1337.5.15 → 6.15 · 旧版本存档', ['1,570 个可比 AI；1,461 次 dirty', 'AI 完整替代刷新 1,461 次', '93.1% 可比 AI 走了 dirty 重算'], 'gold', '只能计事件，不能换算 EU5 CPU 秒数')
f.box(744, 698, 648, 192, '1337.6.15 → 7.15 · 旧版本存档', ['1,577 个可比 AI；1,415 次 dirty', '完整刷新 1,494 次，另含年度等刷新', '89.7% AI dirty；不能把 1,494 全算异常'], 'gold', '4,311 个 reason 6 样本：total=own，E却记0')
f.text(48, 948, '当前源码已修复确认的 false dirty；修复后真实过月耗时仍需实机验证。', 22, INK, 700)
f.text(48, 989, '若仍慢，先看 dirty 增量，再隔离 solver 调用、引擎需求刷新与 UI 绘制成本。', 19, MUTED)
f.save('05_dirty_amplification.svg')

counts = json.loads((HERE / 'operation_counts.json').read_text(encoding='utf-8'))
case = next(x for x in counts['scenarios'] if x['locations'] == 180 and x['nonneutral'])
f = Figure(6, '操作计数：省在哪里，没省在哪里', '同一离线场景：180 地点 / 3 市场 / 七种人口 / 非中性价格；早期 1.4 与当前源码对照。', 980)
rows = [('替代刷新：变量操作', case['before']['refresh']['variable_operations'], case['after']['refresh']['variable_operations']),
        ('地点支出：商品条目读取', case['before']['all_location_spending']['map_reads']['goods'], case['after']['all_location_spending']['map_reads']['goods']),
        ('clean 快照：条件节点执行', case['before']['clean_snapshot']['condition_evaluations'], case['after']['clean_snapshot']['condition_evaluations'])]
for i, (title, old, new) in enumerate(rows):
    y = 184 + i * 183
    f.text(48, y + 16, title, 23, INK, 700)
    maximum = max(old, new)
    for j, (label, value, color) in enumerate([('早期 1.4', old, MUTED), ('当前', new, TEAL)]):
        yy = y + 37 + j * 46
        f.text(48, yy + 23, label, 18, MUTED)
        width = max(5, value / maximum * 940)
        f.rect(190, yy, width, 28, color, radius=3)
        f.text(210 + width, yy + 23, f'{value:,}', 21, color, 700)
    f.text(48, y + 158, f'变化 {(new / old - 1) * 100:+.1f}% · 本行单独刻度；不同操作不能相加当作时间', 16, MUTED)
f.box(48, 754, 648, 145, '当前 clean 月仍付出的工作', ['本例总修正 getter 56 次，strength getter 0 次', '仍有地点遍历 + 每地点一个月期限 modifier 续写'], 'gold', '相同商品 modifier 的 add / remove = 0 / 0')
f.box(744, 754, 648, 145, '离线计数未覆盖', ['国家矩阵 / 209 sweep / 世界缓存 / 引擎需求刷新', '也不含地点 modifier 续写与原生 map/getter 内耗'], 'red', '这些百分比不是总过月速度提升')
f.save('06_operation_counts.svg')
print('Generated six SVG figures')

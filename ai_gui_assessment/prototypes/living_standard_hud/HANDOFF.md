# 交接：HUD「生活水平」徽章（方案 B，靠左）

状态（2026-10-18）：**B 方案原来的 topbar 悬挂位置已由新版左面板行设计替换；新版已接入 stable/standalone，实机验收待完成。**
新版位置、Glorp UI 顺延兼容和渲染验收见 [`living_standard_leftrow/DESIGN.md`](../living_standard_leftrow/DESIGN.md) 与 [`EU5_GUI_SOL_Notes.md`](../../../docs/guides/EU5_GUI_SOL_Notes.md)。正式生成入口仍为 `scripts/gen_sol_lshud.py` 与 `scripts/gen_sol_chain.py`；以下第 3–5 节保留为原始数据/tooltip 合同，实现细节见 [`SOL_Topbar_HUD_Implementation_20261017.md`](../../../docs/technical/SOL_Topbar_HUD_Implementation_20261017.md)。
实际单位为“每千人每年净收入”（月收入 ×12）；总计取求解器五阶层各自扣维护后非负净收入之和。同比使用去年同月的完整样本，首次满一年之前保持待结算；不将不足一年的周年间隔视为同比。排序采用具名 script value 与显式总数，无需未经核实的 `position` 循环索引。
用户已确认采用 B、删除 A/C、徽章从左往右靠左放置。

- 原始设计对比记录不再保留；A（顶栏内嵌指标）与 C（国家横幅侧签）已按用户要求删除，相关生成物与渲染图已清除。
- 本目录 `sol_lshud.gui` / `sol_lshud_l_simp_chinese.yml` 是 `build.py` 的生成物，**不要手改**。

## 1. 交付物

| 路径 | 内容 |
|---|---|
| `ai_gui_assessment/prototypes/living_standard_hud/build.py` | 生成 GUI/本地化，并渲染 5 个状态 |
| `.../sol_lshud.gui` | `sol_lshud_root` 根控件 + `SOL_LSHUD_tooltip` 模板 |
| `.../sol_lshud_l_simp_chinese.yml` | 简中键（UTF-8 BOM、直引号） |
| `ai_gui_assessment/images/living_standard_hud_20261016/` | 渲染结果（见第 6 节） |

```powershell
$env:PYTHONUTF8='1'
& C:/Users/Hades/anaconda3/envs/eu5/python.exe ai_gui_assessment/prototypes/living_standard_hud/build.py
```

渲染器报告：0 个未解析原型绑定、0 张缺失贴图；5 个状态（中/增长、高/大增长、低/大降低、第 2 名、待结算）均无问题。

## 2. 已定的视觉与交互（不要再改，除非用户提出）

**徽章（常驻 HUD）**
- 位置：`position = { 636 34 }`，从顶栏下沿“挂”下来，在左侧国家横幅右侧的花饰之外；整块 `132×100`
  （66px 圆形徽章 + 下方 30px 金框名牌）。左面板展开（`left_panel` 右侧边缘 x≈550）时不重叠；暂停横幅（y≈150 起）不受影响。
- 圆形徽章：深蓝底盘 `circle_background` + 文化相关金环 `GetGraphicalCultureTexture('circle_frame')` + 等级图标。
- 名牌：`pause_label_frame` 金框，内容 `人均收入 + 趋势箭头 + 同比%`；数据未就绪时显示「待年度结算」。
- 徽章与名牌都可悬停，共用同一个 tooltip。

**等级图标（低/中/高）**：复用 SOL 的 `sol_proto/tier_need`（麦穗）/ `tier_daily`（陶罐）/ `tier_lux`（钻石），
三个叠放、按 `sol_ls_tier` 互斥显示。数据未就绪时显示 `icons/sol/sol_living_standard.dds`（0.6 alpha）。

**同比四档**：内联 `@arrow_bonus_tier_2!` 大增长 / `@arrow_bonus_tier_1!` 增长 / `@arrow_malus_tier_1!` 降低 /
`@arrow_malus_tier_2!` 大降低，文字 `#P` / `#N` 着色；百分比 `|+=1%`。

**Tooltip**（460 宽，实测 460×560 / 待结算 460×166）
1. 英雄区：80px 徽章、`生活水平：中`、32 号人均收入 + `@gold!`、单位「每千人每年收入」；右侧同比色块（绿/红底）+ 百分比 + 一年前数值。
2. 各阶层：`人均收入 | 发散条（中点 0，满格 ±10%）| 同比% | 箭头`；人口为 0 的阶层整行隐藏。
3. 全球位置：右侧「第 12 / 87 · 高于 87% 的国家」；行内为 第 1 名、`⋯`、本国上 2 名、本国（金框金条）、下 2 名；
   每条长度 = 该国人均 / 第一名。第 1 名在排名 ≤3 时不重复出现；`⋯` 仅在排名 ≥5 时出现。
4. 脚注（12 号灰字）：口径、分档阈值、刷新节奏。

## 3. 变量契约（GUI 已按此写死，后端必须照此产出）

GUI 只读显示就绪的变量；**排序、除法、分档不在 GUI 里做**。

### 每国（country 作用域变量）
| 变量 | 类型 | 含义 / 来源 |
|---|---|---|
| `sol_ls_pci` | CFixedPoint | 人均收入显示值 = `gls_total_income / gls_pop_all`（下节给单位） |
| `sol_ls_pci_<estate>` | CFixedPoint | 分阶层 = `gls_income_<estate> / gls_pop_<estate>` |
| `sol_ls_pop_<estate>` | int | 阶层人口；GUI 用 `> 0` 决定是否显示该行 |
| `sol_ls_pci_prev` | CFixedPoint | 一年前的人均收入 |
| `sol_ls_pci_yoy` | CFixedPoint | 同比比例（0.045 = +4.5%）；`prev ≤ 0` 时写 0 |
| `sol_ls_pci_yoy_<estate>` | CFixedPoint | 分阶层同比 |
| `sol_ls_pci_yoy_class` | int | 2 / 1 / −1 / −2 = 大增长 / 增长 / 降低 / 大降低 |
| `sol_ls_pci_yoy_class_<estate>` | int | 同上，分阶层 |
| `sol_ls_tier` | int | 0 / 1 / 2 = 低 / 中 / 高 |
| `sol_ls_rank` | int | 世界排名（1 = 最高人均） |
| `sol_ls_percentile` | CFixedPoint | 超过的国家比例 = `(count − rank) / (count − 1)` |
| `sol_ls_above_1` / `above_2` / `below_1` / `below_2` | **country 作用域变量** | 排名相邻国家；不存在则不设（GUI 用 `.IsSet` 隐藏整行） |

estate 键必须是 `nobles` / `clergy` / `burghers` / `commoners` / `tribesmen`（与现有 `gls_pop_*` 一致）。

### 全局
| 变量 | 含义 |
|---|---|
| `sol_ls_top_1 … sol_ls_top_10` | 前十名（country 作用域）；GUI 目前只用 `top_1` |
| `sol_ls_top_pci` | 第一名的人均（行内条长度的分母；GUI 已保护 0） |
| `sol_ls_rank_count` | 参与排名的国家数 |
| `sol_ls_world_pci` | 世界人口加权平均（分档基准） |
| `sol_ls_tier_count_0/1/2` | 各档国家数（预留给后续分布显示，当前 GUI 未用） |

### 阈值（脚本值，不要散落成魔法数）
- 分档：`pci < 0.75 × world_pci` → 低；`> 1.33 × world_pci` → 高；否则中。
- 同比四档：`≥ +5%` → 2；`> 0` → 1；`> −5%` → −1；`≤ −5%` → −2。
- 参与排名：`total_population > 0` 且 `num_locations > 0`（排除无领土/无人）。

### 单位（必须先定，再动手）
`gls_income_*` / `gls_pop_*` 的原始口径尚未在实机核对。`local_sol_total_income` 已扣除各阶层**建筑维护费**
（`SOL_pop_values.txt:423`），是“净收入”。建议：人均收入 = 净收入 ÷ 人口，再乘一个固定年化系数，
使 1337 年典型国家的数值落在 1–3 的可读区间（mock 用 1.86）。**系数与单位写进脚注**，脚注文本也要同步改。

## 4. 后端实施步骤

所有 `src/` 下的效果/值文件都是生成物；改源文件后跑 `scripts/gen_sol_chain.py`。

### 4.1 每国累计（唯一新增的重遍历成本）
现状：`gls_income_*` / `gls_pop_*` 只在 `gls_accumulate_panel_stats`（`A_SOL_economy_effects.txt:5486`，
每国 `every_owned_location` 一次）里产出，而它**只对人类国家运行**（`SOL_economy_situation.txt:23-36`），
且只在年初/缺失时运行。AI 国家因此没有任何 `gls_income_*`。

- 源文件：`scripts/sol_economy_effects_source.py`，`emit_section_50_panel_stats_stable`（2013 行）与
  `emit_section_50_panel_stats_standalone`（2770 行）——两边要一致。
- 方案：把同一段遍历抽成 `sol_ls_accumulate_country_income`，在**已有的**周年遍历里调用
  （`sol_ai_yearly_pop_demand_pulse` → `sol_update_local_pop_demand_modifiers`，AI 每年一次；人类沿用月度/年初），
  **不要**新增一次 `every_owned_location`，也不要放进 `situations/*.txt` 的 `on_monthly`（见 BRIEF 的 `yearly_january_pulse_spike`）。
- 遍历后立即在每国写 `sol_ls_pci` / `sol_ls_pci_<estate>` / `sol_ls_pop_<estate>`。

### 4.2 同比快照
- 每国 `yearly_country_pulse`（`in_game/common/on_action/SOL_economy_on_actions.txt:70`，stable 与 standalone 各一份）。
  顺序：先 `pci_prev = pci(旧)`，再算 `yoy` / `yoy_class`，最后更新 `pci`。
- 新游戏/无 `pci_prev` 时不写 `sol_ls_pci`（GUI 显示「待年度结算」），或写 `pci` 但不写 `yoy`——
  **推荐前者**，语义更干净：第一次周年结算后一次性写齐全部变量。
- 注意：AI 是周年制，所以 AI 的“同比”间隔恰好一年；人类若为月度累计，同比会变成“一年前的当月”，
  这正好是想要的，但要求人类每月都写一次 `pci`，而 `pci_prev` 只在周年日滚存。

### 4.3 年度排行（全局，一次）
- 放在现有全局 1 月 1 日分支（`gls_recalculate_global_living_standard` 一带）。
- 读的是**缓存变量**，不遍历地块：
  ```text
  ordered_country = {
      limit = { total_population > 0 num_locations > 0 has_variable = sol_ls_pci }
      order_by = var:sol_ls_pci
      max = 10
      # position = 1..
      # 写 sol_ls_top_<position>（global）、sol_ls_rank（本国变量）
  }
  ```
  `order_by = var:<name>` 与 `position` 的写法：`effects.log` 的 `ordered_country` 条目（4650 行）列出
  `limit / order_by / position / min / max`，但语料里**没有**可运行的上游例子；`order_by = total_population`
  有原版实例（`events/DHE/flavor_brapru.txt:1081`）。先做一次最小实机测试确认 `order_by = var:x` 与
  `position` 可用，失败则退回两遍 `every_country`（先算 count，再用 `ordered_country` 取前十）。
- 相邻国家：同一次遍历里用“前一名/后一名”变量传递，或第二遍 `every_country` 读 `sol_ls_rank`、
  把自己的 rank 与 `player.sol_ls_rank` 比较后写入对方的 `sol_ls_above_*` / `below_*`。后者更简单，
  与“一次遍历、无排序”的目标不冲突。
- 同时写 `rank_count`、`percentile`、`top_pci`、`world_pci`（人口加权）、`tier_count_*`。
- 全局变量统一用 `set_global_variable`；国家作用域用 `set_variable`，值是 `Country` 作用域（`effects.log:10966/11247`）。
- 读回：`global_var:sol_ls_top_1`（原版先例 `situations/rise_of_timur.txt:8`），脚本里可 `global_var:sol_ls_top_1 = { ... }`。

### 4.4 生成链接入
`gen_sol_chain.py` 里已有 `gen_sol_ls_gui.py` 负责 SOL 的经济 UI 生成。建议：
- 新增 `scripts/gen_sol_lshud.py`，或在 `gen_sol_ls_gui.py` 里加一个 `render_hud_badge()`，
  以本目录两份文件为蓝本生成到 `src/stable/` 与 `src/sol_standalone/`；
- `.gui` 不带 BOM、`.yml` 必须带 BOM（`gen_sol_ls_gui.py:442`）；
- 在 `gen_sol_chain.py` 的 `base_targets` 段调用（`gen_sol_ls_gui.py` 之后）；
- 简中与英文各一份 localization；英文键值按第 2 节文案翻译。

### 4.5 挂载（scripted widget，不覆盖 `hud_topbar.gui`）
- 新建 `in_game/gui/SOL_lshud.gui`（内容 = 本目录 `sol_lshud.gui` 的 `sol_lshud_root` + 模板），
- 新建 `in_game/gui/scripted_widgets/SOL_lshud_scripted_widgets.txt`：
  ```text
  gui/SOL_lshud.gui = sol_lshud_root
  ```
  先例：本仓库 `SOL_migration_scripted_widgets.txt`、参考 mod `3599735023/.../IV2_scripted_widgets.txt`。
- **不要**改 `hud_topbar.gui`（GUI 只能整路径覆盖）。`sol_lshud_root` 是 100% 大小的 `layer = topbar` 透明根，
  只会盖住地图，徽章本体很小；`alwaystransparent = yes` 让空白区域不吞鼠标。
- `hud_topbar.gui` 自己也是 `layer = bottom`（`hud_topbar.gui:143`）——徽章在 `topbar` 层，会画在顶栏之上，
  这正是“悬挂”的效果；如果实机被顶栏遮住，把根控件改成 `layer = hud` 再测。

## 5. 待实机确认（按风险排序）

1. **scripted widget 的叠放层**：`layer = topbar` 是否压过 `ingame_topbar` 与 `hud_topbar`；`alwaystransparent` 是否真的不挡地图点击。
2. **坐标**：`636/34` 来自离线渲染的原版横幅几何；不同文化（`GetGraphicalCultureTexture` 的花饰宽度）与 UI 缩放需要复核；
   若左面板展开后与徽章重叠，改为左面板头部内的相对锚定。
3. **`ordered_country` 的 `order_by = var:x` / `position`**（见 4.3）。
4. **tooltip 高度**：560px @100% 缩放；高缩放/低分辨率下会顶到屏幕下沿（引擎会把 tooltip 整体上移，不会裁切）。
5. **数值单位**：见 3 节最后一段。
6. **性能**：新增的每国遍历必须落在已有的周年遍历里；用 CMF 性能日志确认 AI 月/年开销没有第二个 `every_owned_location`。

## 6. 渲染图对照

| 文件 | 内容 |
|---|---|
| `B_hud.png` / `B_hud_top.png` | 整屏 / 顶部 300px |
| `B_hover.png` | tooltip 叠在 HUD 上（悬停示意） |
| `B_tooltip.png` | 单独 tooltip（正常：中 / +4.5%） |
| `B_states.png` | 五种状态的徽章特写并排 |
| `B_{high_bigup,low_bigdown,rank2,pending}_{bar,hover,tooltip}.png` | 各状态单独图 |
| `B_tree.txt` | 布局坐标树 |

## 7. 已核对的引用

- `Scope.GetVariable(Arg0)` → Scope（`data_types_script.txt:2346`）；`Scope.GetValue` → CFixedPoint（3292）；`Scope.IsSet`（3427）。
  原版读值：`attribute_columns/country.gui:1401`。变量内国家作 datacontext：`panels/situation/hussite_wars.gui:112`。
- `GetGlobalVariable(Arg0)` 全局 promote（`data_types_script.txt:28`）；`ObjectsEqual(Country.Self, Player.Self)`（`diplomacy_macrobuilder_lateralview.gui:1462`）。
- `ordered_country`（`effects.log:4650`）；`set_global_variable`（10966）；`set_variable`（11247）；`save_scope_as`（原版 `00_event_illustration_effects.txt:41`）。
- 徽章美术：`circle_background.dds` + `GetGraphicalCultureTexture('circle_frame')`（`hud_topbar.gui:1885`）；
  `pause_label_frame.dds`, `Corneredstretched`, `spriteborder = { 26 0 }`（`ui_library.gui:205`）。
- 内联图标：`font_icons.gui:2084-2136`（arrow_*_tier_*）、`:1067`（gold）、`:3687-3730`（estates）。
- 输入现状：`gls_accumulate_panel_stats`（`A_SOL_economy_effects.txt:5486`），人类专属调用
  （`SOL_economy_situation.txt:23-36`），周年入口（`SOL_economy_on_actions.txt:70-113`），
  净收入口径（`script_values/SOL_pop_values.txt:423-433`）。
- 抗锯齿/防坑：`#gold` 不是合法文本格式（必须用 `@gold!` 或 `color_gold_texture`）；
  隐藏行在渲染器里仍会求值 `datacontext`（实机不会），mock 需要兜底。

## 8. 给知识库的条目

已在 `docs/knowledge/anti_patterns.yaml` 增加 `gui_country_ranking_reads_backend_slots`（GUI 只读后端排好序的槽位），
并运行 `scripts/gen_brief.py`。实现完成后，按 Knowledge Capture 规则再补一条实机发现（scripted widget 的层与坐标）。

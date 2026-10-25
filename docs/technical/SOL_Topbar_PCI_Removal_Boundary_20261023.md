# 顶栏第一格：废弃"千人均年净收入"、改显示生活水平 —— 改动边界

日期：2026-10-23　状态：已实施并通过离线验证；游戏内图标对齐、悬停和缩放待验收。下文旧调用描述保留为实施依据。

图标注册文件采用 `SOL_font_icons.gui`，供现有渲染器自动发现；图标名、尺寸与偏移遵循 §8。历史 `sol_lshud_income_source.py` 路径保留，但仅生成 SOL 同比。

验证：SOL 同比 14 项、生活水平 23 项、排名 14 项、Windows 界面渲染 11 项、地图 5 项、计算频率 12 项及校验器 10 项均通过；完整 `gen_sol_chain.py --check`、`validate.py --changed` 和共享/本地知识合并校验通过。中英文、双目标预览见 `ai_gui_assessment/images/sol_topbar_20261023/`。

## 1. 结论

"千人均年净收入"（`sol_ls_pci*`）是定义修正前顶栏的残余。现在它在游戏里**只剩两个读者**：顶栏第一格（数字 + 同比）和第一格的悬浮窗（"收入与同比"表）；此外它的"是否已设置"被当成整个顶栏和排名悬浮窗的"首次计算完成"开关。排名、等级、地图都已经读生活水平（`sol_ls_sol*`）。

所以这次改动 = **把第一格及其悬浮窗换成生活水平，把同比搬到生活水平上，删掉国家级收入汇总**。上游的地点净收入不是废弃量，必须保留。

算例（玩家国，按原型样本数据）：现在第一格显示人均净收入 `1.86 @gold! ↑+4.5%`；改后显示 `18.0 ↑+x%`，与悬浮窗标题、第四格排名里的"生活水平 18.0"是同一个数。

## 2. 要删的（国家级收入汇总，纯展示）

| 对象 | 位置 | 说明 |
|---|---|---|
| `sol_ls_income_all/<e>`、`sol_ls_current_pci_*`、`sol_ls_pci`、`sol_ls_pci_<e>`、`sol_ls_pci_prev*`、`sol_ls_pci_yoy*`、`sol_ls_pci_yoy_class*` | `scripts/sol_lshud_income_source.py` 生成 | 无脚本、事件、AI 读取；只有 GUI 和本地化读 |
| 每地点 6 次 `change_variable`（income_all + 5 阶层 income） | `sol_ls_accumulate_country_income` | 两条求解路径各一处调用（`sol_economy_effects_source.py:1537`、`:1811`） |
| 第一格悬浮窗的"年净收入""人均"列、`SOL_LSHUD4_PREV_LINE`（"一年前人均…全国年净收入…"） | `living_standard_4sections/build.py` | |
| 本地化：`SOL_LSHUD4_T1_TITLE/SUB/COL_INCOME/COL_PCI/PREV_LINE`、`SOL_LSHUD_PENDING_BODY` 里"人均收入"字样 | `build.py` LOC + `gen_sol_lshud.py` 英文表 | 要改写，不是全删 |
| `gen_sol_lshud.py` 里的死代码：`leftrow_source`、`_legacy_tooltip_source`、`estate_row`、`ladder_row`、`diverging`、`medallion` 等，以及 21 个已无 GUI 引用的本地化键（`SOL_LSHUD_ROW_*`、`SOL_LSHUD_UNIT`、`SOL_LSHUD_FOOTNOTE*` 等） | `outputs()` 从未写出它们 | 它们大量引用 `sol_ls_pci`，留着会误导后续会话；一并删 |
| 地图本地化 `SOL_LSHUD4_PREV_LINE_MAP` | 自动派生 | 地图不复用悬浮窗 1，本来就是死键 |

计算量收益：每个有主陆地地点、每次刷新少 6 次变量写入；人口累加并入生活水平累加器后，再少一次 `save_scope_as` 和一次 `owner` 切换。这是每地点开销，是本次唯一有意义的性能项。

## 3. 必须保留（容易误删）

| 对象 | 原因 |
|---|---|
| `sol_location_<e>_net_income`、`sol_location_total_income` | 求解器上游：流动资金 = 净收入 × 资金倍率（`sol_economy_effects_source.py:1021-1072`）。只是国家级"人均净收入"废弃，地点净收入不是 |
| `sol_ls_pop_all/<e>` | 生活水平按人口加权要用（`sol_living_standard_source.py:246`），悬浮窗人口列和各阶层显隐也用。目前由收入累加器产生，要**搬进** `sol_ls_accumulate_country_living_standard`，重置搬进 `sol_ls_reset_country_living_standard` |
| `sol_ls_annualization_factor`（×12） | 生活水平公式里"月流动资金→年"在用。从收入值文件挪到生活水平值文件 |
| `sol_ls_yoy_big_increase/decrease_threshold`、同月样本轮转逻辑 | 同比若保留（决策 1），整套搬到生活水平上复用 |
| `gls_income_*` | 情势面板的毛收入诊断，和本改动无关 |
| 第二格购买力、地点悬浮窗、情势面板条、`sol_purchasing_power` 地图 | 之前的用户决定：继续显示购买力 |
| 排名、等级、`sol_living_standard` / `sol_ranking` 地图 | 已经读生活水平，不改 |

## 4. 要改的（替换，不是删除）

1. **"首次计算完成"开关**：`READY = IsSet('sol_ls_pci')` 同时门控第一格、悬浮窗 1、第四格、悬浮窗 4 和国家地图悬浮窗 4（`SOL_map_tooltips.gui:4279`）。改为 `IsSet('sol_ls_sol')`。差别：旧变量人口为 0 时被置 0（仍算"已设置"），`sol_ls_sol` 人口为 0 时被移除，所以零人口国家会显示"等待首次计算"而不是 0。可接受。
2. **第一格**：数字改为 `sol_ls_sol`，格式与标题、排名一致用 `|1`；同比改读生活水平同比。点击仍切到 `sol_living_standard` 地图——现在格子里的数和地图颜色终于是同一个量。
3. **悬浮窗 1**："收入与同比"→"生活水平与同比"。大数字 = 生活水平；标题只保留等级（目前标题已带生活水平数字，换后会和大数字重复）；表格变为 `阶层 | 人口(千) | 生活水平 | 同比`。副标题写公式：固定值之和 +（1 + 百分比之和）× 千人均年流动资金。目前唯一解释这个公式的文字在已死的 `SOL_LSHUD_FOOTNOTE` 里，玩家看不到，这次要让它活在悬浮窗 1。
4. **同比样本必须换新变量名**（如 `sol_ls_sol_sample_<m>_*`），**不能复用** `sol_ls_sample_*`。旧档里的样本是收入，若沿用名字，升级后一年内会拿生活水平除以去年收入，得出约 +870% 这类假同比（18.0 ÷ 1.86 − 1）。换名后升级首年显示"暂无去年数据"，这是正确行为。
5. **旧存档残留**：旧档国家身上的 `sol_ls_pci*`、`sol_ls_income_*`、`sol_ls_sample_*` 不再被读写也不参与计算，按既定原则不清理。
6. **生活水平同比的含义变化**：建了医院、开了剧院，同比会跳——这正是设计意图（生活水平不只是钱）。

## 5. 测试与生成物

- `test_sol_lshud_income.py`：整个文件测的是收入汇总与同比。改写为生活水平同比测试（年份轮转、同月比较、缺年、零基准不除零这些用例原样保留，只换量）；收入发布用例删除。
- `test_sol_living_standard.py:91-95, 455-459`：现在断言"收入累加在生活水平累加之前""生活水平收尾在收入收尾之前"。合并后改为断言人口与生活水平在同一个累加器里、同比在生活水平收尾之后。
- `test_sol_lshud_ui.py:108-109, 223-236`：模拟值和"超长数字不溢出"用例换成生活水平变量。
- `test_sol_lshud_ranking.py:228-229`：断言排名不写 `sol_ls_pci_*`，删变量后自然成立，可改为断言不写生活水平同比。
- 原型：`living_standard_4sections/build.py`（是第一格真正的源码）的 `EXTRA` 和 mocks；它从 `living_standard_hud/build.py` 借 `PLAYER_VARS/STATES/state_mocks`，那份夹具里的 `sol_ls_pci*` 也要换。`living_standard_hud/`、`living_standard_leftrow/` 两个旧原型除夹具外只当历史存档，不改。
- 重新生成：`gen_sol_lshud.py`（两个目标 `stable`、`sol_standalone`）、`A_SOL_economy_effects.txt`、`data/index/scripted_effects.txt`；跑 `validate.py --changed` 与 Windows 端 UI 测试。

## 6. 文档

- 本文件取代 `SOL_Living_Standard_Formula_Correction_Plan_20261023.md` §2.3 中"顶栏第一格人均收入与同比：不改"一行。
- 更新 `living_standard_4sections/DESIGN.md`（§1 第 1 节、悬浮窗 1、§变量清单）、`SOL_Topbar_HUD_Implementation_20261017.md`、`PROJECT_OVERVIEW.md`、`CHANGELOG.md`，然后 `gen_brief.py`。
- `docs/analysis/` 下引用 `sol_ls_pci` 的历史报告和脚本不改（它们记录当时存档）。

## 7. 不在本次范围

- 悬浮窗 1 里拆分"资金部分 / 修正部分"：需要新增国家级累加变量，属于修正来源功能的展示，单独做。
- 生活水平等级改绝对档 / 相对档：已有未决问题，与本次无关。
- 情势面板条是否改显示生活水平：已有未决问题，与本次无关。

## 8. 已拍板（2026-10-23）

1. **同比**：改成生活水平同比（按 §4.4 用新样本变量名）。
2. **单位图标**：不用 @gold!，换成专用图标 `@sol_living_standard!`。

**Verification** — Step 3, Reference: `.eu5-base/reference_mods/3599735023/in_game/gui/IV2_texticons.gui:7`, Quote: `"texticon = {\n\ticon = iv2_icon\n\ticonsize = {\n\t\ttexture = ..."` — mod 可在自己的 .gui 文件里定义 texticon。
层级检查：`font_icons.gui` 里没有表示"生活水平"的图标。最接近的 `prosperity`、`satisfaction`、`wealth`、`pop_needs` 都是原版已有含义的量（地点繁荣、阶层满意度、财富、人口需求），借用会和金币一样误导，所以走第 3 层自绘。

图标：`ai_gui_assessment/prototypes/living_standard_4sections/make_sol_texticon.py` 生成，64px DXT5，图案是一座亮着窗、冒着炊烟的小屋（家庭生活）。按用户要求刻意避开 SOL 徽章（天平）和等级徽章（碗），不会被看成第二枚等级徽章。预览：`ai_gui_assessment/images/living_standard_4sections_20261018/tier_icons/sol_texticon_preview.png`。实施时：DDS 拷到 `src/*/in_game/gfx/interface/...`，新建 `SOL_texticons.gui` 定义 `icon = sol_living_standard`（尺寸、偏移照 `font_icons.gui` 的 `@font_icon_default_*`：20×20、偏移 0 4、字号 16），并需游戏内截图验证对齐。

用法边界：第一格左侧已有等级徽章，数字后面不加单位图标；单位图标用于悬浮窗 1 大数字、表格和排名悬浮窗里的生活水平数值。

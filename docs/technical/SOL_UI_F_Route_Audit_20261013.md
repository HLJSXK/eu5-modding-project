# SOL UI 草案 F 路线审计与改进方案

日期：2026-10-13
审计对象：`substitution` 分支当前 HEAD（`2f50b610`）
基线：草案 F 提交 `1d9d8e4c`（`tmp/F-route-SOL-UI-1d9d8e4c.bundle`）

## 结论

当前界面不是草案 F 的小幅视觉回归，而是原型、半成品提交和后续扩展叠加后的混合产物：

```text
旧版 estate-first 重设计（原型到提交时仍未移除）
        + F 路线的顶部仪表盘
        + 国家商品替代的动态商品块
        + 替代组悬停、市场权重、供应变暗和 +/- 标记
        = 当前结果
```

F 视觉原型的核心信息结构没有被完整迁移。最明显的证据是：F 图片和结构树中的两条“谁多、谁富”人口/收入分布条使用 `barchart`/`barslice`，而当前生成的 stable、standalone GUI 中完全没有这两类节点；当前反而保留了原型中未出现的 `sol_ring`、`sol_ledger_header/row` 和消费系数 KV 表。需要特别区分：F 的实际提交 `1d9d8e4c` 源码本身也保留了 ring/ledger/KV，因此“原型图 → F 提交源码”已经先发生了一次断链，不能把全部责任归给 `09ab11b1`。

因此，修复的正确单位是“重新建立 F 的单一事实来源并重做两面 UI 的信息架构”，不是继续在现有生成文件上补间距、换颜色或压缩高度。

## F 基线及当前结果

F 的可复核资产和结构树位于：

- [F_cty.png](../../ai_gui_assessment/images/proto/F_cty.png) / `F_cty_tree.txt`：500×1178，全国面板。
- [F_loc.png](../../ai_gui_assessment/images/proto/F_loc.png) / `F_loc_tree.txt`：420×1241，地点 tooltip。
- [F_good.png](../../ai_gui_assessment/images/proto/F_good.png) / `F_good_tree.txt`：442×333，商品 tooltip。
- `sheet3_f.png`：F 路线的组合审阅图。

F 的结构顺序是：

1. 总体消费平衡仪表：dial、系数、可支配资金、基准消费、存款/目标和进度条。
2. 五个阶层仪表：每阶层的 dial、系数、资金/基准和进度条。
3. “谁多、谁富”：人口占比和收入占比两条横向分布图，带钢点、金点和说明。
4. 本地市场货篮或全国货篮：按 20 个需求组排列商品。

F_good 还明确包含原版商品信息、替代组成员和“本市场价格档位”七档区间；这不是当前通用商品 tooltip 的静态成员列表。

当前 renderer 快照显示：

| Surface | F | 当前 | 主要偏差 |
|---|---:|---:|---|
| location | 420×1241 | 484×1003 | 外框、宽度和层级不同；缺少两条分布图，加入 ring/ledger/KV |
| country | 500×1178 | situation 宿主 570×1080 | F 单面板被原生 situation card 包裹；缺少两条分布图，加入 ring/ledger/KV |
| goods | 442×333 | 442×372 | 通用商品详情只有静态替代组；location 的 market-context cell 另有替代倍率/权重 pending 文本，但仍缺少 F 的七档价格条 |

当前图像证据可在 `ai_gui_assessment/images/substitution_integration/` 查看；F 对照图在 `ai_gui_assessment/images/codex_f_check/`。这些预览都是 renderer 结果，不能替代实机验收。

## 错误责任链

### 1. F 从未成为当前实现的父路线，且原型到 F 提交已先断链

F 提交 `1d9d8e4c` 与当前 `09ab11b1` 是同一父提交 `eb9cc074` 的兄弟提交；F 没有被 merge 或 cherry-pick 到当前分支。当前历史是：

```text
eb9cc074
├─ 1d9d8e4c  F-route SOL in-game UI with read-only substitute UI
└─ 09ab11b1  Complete SOL economy dashboard and GUI renderer updates
   └─ dfd3055f  Implement country goods substitution and initial GUI integration
      └─ 2f50b610  Align substitution groups with the SOL economy GUI
```

这解释了为什么“现结果和 F 差别大”首先是路线和规格断链问题，而不是某一处提交造成的回归。F 的 PNG/tree 是视觉原型证据；F 提交源码是一个仍带旧 ring/ledger 的半成品，二者不能直接视为同一份实现。

### 2. `09ab11b1` 只把 F 仪表增量接入已有半成品

当前生成器在 [scripts/gen_sol_ls_gui.py](../../scripts/gen_sol_ls_gui.py) 中定义了 F 资源和顶部仪表：

- `F_TEX`：第 76 行。
- `f_dashboard()`：第 133 行，输出总仪表和五个阶层仪表。
- `f_meter()`：第 117 行，输出 F 的进度条。

但同一个生成器之后仍然在 `render_tooltip()` 和 `render_panel()` 中调用：

- `composition()`：第 273 行及调用点 454、605；
- `ledger()`：第 313 行及调用点 472、621；
- `kv_rows()`：第 343 行及调用点 499、651；
- `goods_block()`：第 369 行及调用点 511、663。

也就是说，`f_dashboard()` 是一个增量模块，不是 F 页面的完整 renderer。`09ab11b1` 的代码注释还明确把替代组计算留给“下一项 backend task”，这表明当时的实现决策是“保留旧页面，再加 F 顶部仪表”，而不是“用 F 替换旧页面”。

### 3. F 的关键可视化没有迁移

F 视觉原型的结构树中有两条真实的 `barchart`/`barslice`：

- `F_cty_tree.txt` 中约第 174–188 行；
- `F_loc_tree.txt` 中约第 196–210 行。

F 提交源码以及当前生成输出中 `rg barchart|barslice src/stable/in_game/gui` 结果都为空。当前 renderer 虽已支持这些节点，说明缺失原因是原型到 GUI 源码的迁移遗漏，不是 EU5 或 renderer 不支持。

### 4. 一个模板被错误地用于两种 F 尺寸

F 对 location 和 country 使用不同预算：

- 主 dial：location 约 196×113，country 约 236×136；
- 阶层卡片：location dial 约 66×38、卡片宽约 76；country dial 约 80×46、卡片宽约 92。

当前 `f_dashboard()` 固定使用主 dial 176×102、阶层 dial 74×43、卡片宽约 82。这会同时破坏两种 surface 的比例、留白和文字密度。当前统一模板不能达到 F 的两个目标尺寸。

### 5. 替代组接入改变了产品范围，却没有重新定义 F 规格

`dfd3055f` 和 `2f50b610` 在 F 混合布局上继续加入：

- 每个商品的 tooltip；
- 市场权重和 pending 状态；
- full/dim 供应图标；
- +/- 替代标记；
- 国家替代刷新年、商品数和最大修正摘要；
- PP/JTG 的额外商品和重建 goods vbox。

这些功能本身可以成立，但它们不是 F 的原始信息层级。它们直接造成当前页面更高、更密，并把 F 的“按组读取”变成了“商品逐项悬停读取”。

F_good 还暴露出一个未解决的范围冲突：它要求“本市场价格档位”，而当前通用 `goods_details` 没有单一 market 或 consuming country。`scripts/gen_sol_goods_tooltip.py` 因此只注入静态替代组成员；location 的 `scripts/sol_goods_ui.py` cell 则可以读取 market-scoped 的替代权重并显示 pending 状态，但仍没有 F 所需的七档价格条。这是合理的作用域保护，但它意味着当前商品 tooltip 不能宣称与 F 一致。

### 6. 没有 golden spec 和结构回归门槛

F 只有 PNG 和树文件，没有与 GUI 生成器绑定的结构规格。handoff 把旧版 ring/ledger 顺序描述成设计决策，后续代码生成通过了 `--check` 和 renderer，却没有检查：

- 是否存在两条 F 分布图；
- 是否仍意外生成 `sol_ring`/`sol_ledger_*`；
- section 顺序是否与 F 相同；
- location/country 是否使用各自尺寸；
- F_good 的 market scope 是否存在；
- 当前提交、目标 mod、语言、UI 缩放是否与截图匹配。

所以“生成成功”和“符合 F”被错误地当成同一件事。

## 完备改进方案

### 阶段一：冻结规格并拆分路线

1. 将 F 正式命名为 `F-route` golden spec，保留 PNG/tree 作为视觉证据，但新增机器可读的 `data/sol_ui_f_spec.yaml`（或等价 JSON）。至少记录：surface、目标尺寸、section 顺序、节点类型、关键尺寸、脚本值、scope、商品组顺序、允许的兼容扩展。
2. 明确产品选择：F 是基础信息架构；替代功能只能作为 F goods 区的受控扩展，不能再次把旧 ring/ledger/KV 自动追加到 F 后面。
3. 把“F 原型”“当前兼容扩展”“未实机验证”分开标记，避免把 renderer 快照或旧 handoff 当作最终实机规格。

### 阶段二：重建生成器，而不是修补生成文件

在 `scripts/gen_sol_ls_gui.py` 中建立按 surface 参数化的完整 F renderer：

```text
render_f_surface(kind=location|country, goods, compatibility)
├─ render_f_dashboard(kind)          # 两种尺寸，不共享错误的固定宽度
├─ render_f_distribution_bars(kind) # 两条 barchart + steel/gold markers
├─ render_f_goods_groups(kind)       # 本地市场 / 全国市场
└─ render_f_extensions(...)           # 替代状态等受控附加信息
```

具体要求：

- 实现两条 `barchart`/`barslice`，使用 F 的人口占比、收入占比、钢点、金点和说明文案。
- location 与 country 使用独立的尺寸常量和布局预算；不要用一个 176×102/74×43 模板覆盖两者。
- 从 F route 中移除或显式关闭 `composition()`、`ledger()`、`kv_rows()`。若确实要保留某项，必须在 F 规格中重新登记为新增 section，并重新做高度预算。这样既修复原型到提交的断链，也避免继续沿用当前半成品。
- goods 组仍由共享 renderer 输出，以保持 stable、standalone、PP、M&T、JTG 的成员关系和顺序一致；兼容商品作为受控尾部扩展。
- 在生成阶段让每个 section 有稳定的标识注释或 manifest，便于结构断言和后续 diff。

### 阶段三：解决 F_good 的作用域问题

推荐实现两层商品界面：

1. **通用商品 tooltip**：保留原版价格/产量/需求和静态替代组成员；不读取不存在的 country/market。
2. **市场上下文扩展**：在 `SpecificGoodsMarket_tooltip` 或 `market_tooltips.gui` 的 `good_details_extra_info` 接口注入 market scope，显示 F 的七档价格倍率、阈值和“本市场价格是基础价的多少倍”。

若当前引擎入口无法可靠提供 market scope，则必须把 F_good 标记为“原型未完全落地”，并把价格档位放到地点 tooltip 的 market-scoped 商品悬停中；不能用静态或玩家国家数据伪造市场档位。

### 阶段四：建立自动化验收门槛

新增 `scripts/test_sol_ui_f_route.py` 或等价检查，至少断言：

- location/country 各有且仅有两条 F 分布图；
- F route 中不存在意外的 `sol_ring`、`sol_ledger_header`、`sol_ledger_row` 和旧消费 KV；
- section 顺序是 dashboard → estate dials → distribution bars → goods；
- F 的本地/国家商品组顺序与 `data/goods_weights.csv` 一致，67 条商品组 membership entries 不丢失（其中 unique goods 数量仍应单独按生成器的 56 条校验）；
- F_good 的 market extension 有明确 scope，通用 tooltip 不读取 market/country；
- renderer unknown expression 为 0，且没有横向溢出；
- 目标尺寸在允许误差内：location 420×1241、country 500×1178、goods 442×333；若嵌入原生 situation 外框，另记录“内容尺寸”和“宿主尺寸”，不能混称。

把以下检查串入 `gen_sol_chain.py` 或 CI：

```text
gen_sol_chain.py --check
test_sol_ui_f_route.py
validate.py --changed
renderer snapshots (stable/standalone/PP/M&T/JTG)
git diff --check
```

### 阶段五：实机部署和回归矩阵

每次 UI 变更都记录 `commit × target × locale × UI scale × save state`，并按以下矩阵验收：

- stable、standalone、PP、M&T、JTG 的新游戏和旧存档；
- English 和 Simplified Chinese；
- 100% 及更高 UI 缩放；
- location tooltip、country situation、generic goods tooltip、market-context goods tooltip；
- 替代开关开启、关闭、pending、无缓存、无供应和零消费阶层；
- `error.log` 中无新增 GUI FetchData、未知 script value、未知 modifier、tooltip scope 或 localization 错误。

renderer 只负责结构和像素预检；最终标准必须是部署后实机截图和日志。部署前要确认目标 mod 目录、加载顺序和旧生成文件已清理，避免把旧 target 或混合 commit 当成当前结果。

## 建议的实施顺序

1. 先只恢复 F 的结构和尺寸，暂时关闭替代商品的动态 marker/summary；确认两条分布图和 F_good market extension 的 scope。
2. 通过 renderer 与结构断言后，再接入替代组成员、供应变暗和 +/- 标记；这些内容放在 F 的 goods section 或上下文 tooltip 中，不改变 F 的主层级。
3. 逐个生成并验收五个 target，再做实机新旧存档回归。
4. 最后更新 handoff、BRIEF 和项目说明，把“F 基线”“兼容扩展”“实机证据”分开记录。

在完成第 1 步之前，不应继续对当前 ring/ledger 混合布局做局部美化；那只会增加迁移成本，并让后续 F 对齐更难审计。

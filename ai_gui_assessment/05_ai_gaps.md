# 05 · AI 在 EU5 GUI 上的欠缺：诊断报告

> **注意**：本文写于 2026-10-11 实机截图之前。已验证的规则以 [`docs/guides/EU5_GUI_Modding_Guide.md`](../docs/guides/EU5_GUI_Modding_Guide.md) 为准；与之冲突的推断（如 hbox 对齐、`|+N` 格式、`spriteborder` 单位、商品图标）已被实机推翻。

> 本任务的目的，是让你看清 AI 在 EU5 GUI 上哪里会出错、为什么出错。下面按“根因”分组，每条都给出本项目中的实际证据。
> 判断三张图时请注意：图中**黄色**标记表示我能从代码直接读出的部分，**橙色**表示结构确定但外观靠猜，**红色**表示引擎行为无法验证。

## A. 先天限制：AI 看不到也跑不了

| # | 欠缺 | 本项目证据 | 后果 |
|---|---|---|---|
| A1 | **没有视觉真值。** 参考文件同步时剪掉了全部 `gfx/` 和 `.dds/.png`，仓库里也没有任何游戏 UI 截图。 | `scripts/sync_reference.py:11,59`；仓库中唯一的 UI 相关图片是 SOL 图标 | 我只能从 `textformatting.gui` 得到文字颜色。背景、边框、纸张质感、按钮外形、插画内容全部是猜的（三张图里所有底色都是推测）。“好不好看、像不像原版”这类判断，AI 基本做不了。 |
| A2 | **没有运行时反馈。** GUI 写得对不对，只有进游戏才知道；error.log 是事后的、片段式的。 | `validate.py` 只对 .gui 做正则反模式和 BOM 检查，**没有任何结构校验** | 布局类错误（溢出、重叠、宽度、0 高度卡头）在静态阶段完全不可见。 |
| A3 | **关键语义没有文档。** 数字格式后缀、同名 type/template 的覆盖优先级、`|+N` 的含义、决议如何进入情势 ActionGroup 等，官方 defines 里都没有。 | 见 02 文档 §4；`zoom_to_button` 被三个 mod 重复定义 | AI 只能“统计原版用法再推断”，置信度不高，而且容易把推断写成事实。 |
| A4 | **文件规模超出注意力范围。** 地点窗口有 9197 行，嵌套深度超过 20 层；AI 只能 grep 片段。 | 我必须靠缩进 awk 脚本才定位到 SOL 按钮所在的页签 | “这个元素在哪个页签 / 哪个容器 / 受哪个 visible 控制”这类**结构性问题**最容易答错。 |

## B. 概念性陷阱（项目里已经发生过的错误）

| # | 陷阱 | 证据（anti_patterns / git 历史） | 正确心智模型 |
|---|---|---|---|
| B1 | 把 `blockoverride` 当成“改一个属性” | anti_patterns：`text_single` 写进了 `common_header_text` | blockoverride **整体替换**插槽内容；必须先读 type 定义，看 block 包住的是属性还是元素。 |
| B2 | 不知道 block 的**位置**决定插入点 | `navigational_button_alt` 的 `icon_texture` 位于内部 icon 里面；error.log 中 `property origin is at ...` | 插入的内容按落点处的父容器规则校验（hbox 子级禁止 `parentanchor` 和百分比 `size`）。 |
| B3 | 生命周期：`_show` 与 `trigger_on_create` 混淆；以为 `on_start` 能继承 datacontext | anti_patterns 三条 + 提交 `134ebd17`、`9a87666d`（地图模式自动切换的两次返工） | `_show` 只在 hidden→shown 转换时触发；state 动作表达式要自己取对象。 |
| B4 | **版本漂移**：从旧快照复制已被删除的 API | 1.4 删除了 `header_action_button_left`、`ShowRoadbuilder`、`use_global_input_instance`；Glorp 最新快照里**仍然**有 `use_global_input_instance` | 第三方文件不是真值。官方 `changes_data_types.md` 才是删除和新增 API 的依据。 |
| B5 | 把 GUI 当成可合并对象，或为了“自洽”删掉可选引用 | anti_patterns：删除 `cm_*` 引用；Glorp 兼容检查文档 | `.gui` 按路径整文件覆盖，必须选定最终拥有者做合并基底；缺失可选依赖时的报错可能是预期内的。 |
| B6 | 臆造字符串到对象的 API（`GetGoods('wheat')`），在 tooltip 上下文里用面板专属的 datamodel | anti_patterns 两条 | 对象只能从访问链 / datamodel 拿到；每个 View 只在自己的面板作用域内有效。 |
| B7 | GUI 与脚本的“使用”判定不对称 | anti_patterns：GUI-only 变量刷 `set but never used` | 变量的 GUI 读取不算使用，必须有一条实际运行的脚本读取。 |
| B8 | 1.4 模板变化没有对应的 blockoverride 可用 | Outcome 外层卡（anti_patterns，提交 `a3fb6cfb`） | 有时唯一办法是复制整份模板，并接受后续维护成本。 |

## C. 本次调研新发现、尚未进入知识库的问题

1. **商品文本图标不在 `font_icons.gui` 中。** 原版本地化在用 `@amber!` 之类的写法，由引擎自动注册。CLAUDE.md 的“先查 font_icons.gui”规则和 `data/index/icons.txt` 都会对商品给出**假阴性**。SOL 对骆驼改用 icon 贴图，可能就是这种假阴性导致的（未证实）。
2. **文档与代码不一致**：`SOL_Glorp_UI_Compatibility_Check.md` 说生成器把 `zoom_to_button` 改名为 `sol_zoom_to_button`，但 `SOL_glorp_location_support.gui:3` 仍然定义 `type zoom_to_button`，与 Glorp、CM 同名。AI 若信文档而不读代码，就会得出错误结论；同名 type 的覆盖规则本身也没人验证过。
3. **循环佐证**：`reference_mods/3698931463` 是 SOL 自己的旧版本，没有列入索引。AI 用“社区 mod 也这样写”作为 Step 3 验证时，可能引用的是自己过去的代码。
4. **格式后缀可疑**：SOL 对税率、控制力等非增量数值使用 `|+=1%`。按原版用法推断，这会显示正号并按正负着色。另外，原版和 SOL 都在 `|+N` 前手写 `+`，说明 `|+N` 的含义与直觉不符。以上都未经实机确认。
5. **SOL 地点按钮没有情报门控**：旁边的满意度按钮有 `visible = HasPopBreakdownIntelOn(...)`，SOL 按钮没有，所以对外国地点也会显示完整数据。这可能是有意为之，但值得确认。
6. **硬编码网格**：56、57、82 格商品网格靠生成器展开成数百个长 `visible` 表达式，宽度（130/68、150/72）靠手算，没有任何检查确保“新增商品后网格和列宽仍然一致”之外的布局正确性。
7. **情势行动卡（用户反馈后修正）**：初版图 1 推测 SOL 的「刷新生活水平缓存」会以行动卡出现，这是错的。`SituationView.GetActionGroups` 列出的是 `generic_actions` 中 `type = situation` 的**通用动作**（原版有 22 个文件，例如 `columbian_exchange.txt` 的 `move_nw_good_to_new_location`），而 SOL 的刷新功能是一个**决议**（`common/resolutions/`）。决议走另一条链路：要么由情势定义中的 `resolution =` / `voters =` 引用，要么由面板自定义按钮通过 `scripted_action_tooltip { action_name = ... }` 调用（fall_of_delhi 面板的做法）。SOL 两者都没有，所以底部什么也不显示。我的错误在于看到 `select_trigger { looking_for_a = situation }` 就把它等同于“情势动作”，没有去核对 ActionGroup 的数据来源。
8. **`ui_library.gui` 被完全忽视**：原版自带一个组件目录（约 19k 行，含“Common situation card”），是“选哪个 type”最好的索引，但知识库、CLAUDE.md、BRIEF 都没有提到它。

## C2. 用户反馈后确认的错误：商品网格右侧空白

初版图把每行 10 个 34×30 格子靠左排列，右侧留出约 100px 空白。实际游戏中格子首尾贴边、均匀分布。

错误来源：我按 **CSS flexbox 的默认行为**（`justify-content: flex-start`）理解 hbox，算出一行宽 10×34 + 9×4 = 376，小于约 470 的可用宽，于是认定右侧留空。但 Jomini 的 `expanding` hbox 会把剩余空间分配到子元素之间，只有显式写 `expand = {}` 才会靠左。代码里其实有三条线索，我都没用上：
1. 每行 hbox 都是 `layoutpolicy_horizontal = expanding`，末尾却**没有** `expand = {}`。原版 `card_common` 的默认内容、Glorp 的人口页签顶栏都是靠显式 `expand` 来控制对齐的。
2. 最后一行补了 4 个**空的 34×30 widget**。如果是左对齐，这些占位毫无意义；它们的存在恰恰是为了让最后一行与上面各行的分布间距一致。
3. 提交 `9e2f86ca`（“Remove redundant final-row spacers”）说明作者在维护这些占位，它们承担布局功能。

这一类错误属于 B 类（概念陷阱）：**用 Web 布局直觉套 Jomini 布局**。我在 01 文档里写过“expand 是吸收剩余空间的弹簧”，却没有推出它的反面：“没有 expand 时，剩余空间去了哪里？”

## C3. 拿到游戏素材后的变化

A1（看不到外观）在获得游戏目录后基本消除：贴图、字体、本地化都能直接用，外观精度主要取决于渲染器对引擎规则的模拟程度。剩下的误差来自 A3（引擎规则没有文档），渲染过程中暴露的具体推断点如下：
- `expand` 的定义是 `layoutpolicy = growing`，不是 `expanding`（`loading_screen/gui/custom_loading_screen.gui:660`）。Glorp 在人口页签的图表下方放了一个 `expand`，它与 expanding 的图表区如何分配高度，决定了三个图表的实际高度。最初我按 Qt 规则让两者均分，图表下方留出大片空白；经用户实机确认，实际是图表撑满，即多余空间先分给 expanding，growing 只拿剩余部分。渲染器已按此修正。
- 不写 `blend_mode` 的 modify_texture：`bg_gradient_mask.dds` 的 RGB 全黑、只有 alpha，而它被用来叠加棕色，因此默认模式只能是 normal（用修饰颜色替换、保留底图 alpha），不可能是 multiply。
- 文本的 `min_width`：漏掉这个属性时，SOL tooltip 的表格被压缩到标准 420 宽；补上后宽度变为 550，与此前读代码得出的结论一致。
- 数字格式：渲染器采用“只有 `+=` / `=+` 才显示正号并着色，单独的 `+` 不显示正号”的规则（依据是原版写法 `"+[X|+0]"`）。

## D. 我对三张图的自评

| 区域 | 置信度 | 说明 |
|---|---|---|
| 元素种类、层级顺序、所在页签、显示哪些行和列、绑定的数据 key | 高 | 直接从 .gui 读出 |
| 尺寸（570 宽、45 / 73 / 220 高、表格列宽、34×30 格子） | 高到中 | 读自代码；文字实际宽度和 `autoresize` 可能撑大 |
| 文字颜色 | 中到高 | 来自 textformatting 的 RGB；字体是近似的 |
| 背景、纹理、边框、按钮形状、插画、3D 场景 | 低 | 纹理不在仓库 |
| 数字格式（符号、着色、千分位） | 低到中 | 后缀语义未文档化 |
| 地点卡、场景条件栏的细节排布 | 中 | Glorp 有约 70 个 blockoverride，我没有逐一展开 |
| 情势底部行动卡 | 低 | 引擎链接未知 |

## E. 能显著改善 AI 表现的输入（按收益排序）

1. **带控件标注的游戏截图**：每个关键界面一张截图，并标出对应的 type 或 block 名。这能直接补上 A1。
2. **关键纹理的小尺寸 PNG**：卡片、按钮框、tooltip 底、页签。几十张就足以让 AI 不再凭空猜外观。
3. **“实机已验证”标记**：给知识条目区分“代码可读 / 实机确认 / 推断”，避免推断被当成事实传播（C2、C4 都属于这一类）。
4. **结构化 GUI 校验**：在 validate.py 中加入 hbox/vbox 子级 `parentanchor`/百分比 `size`、重复属性、1.4 已删除 API 清单、已知可选依赖白名单等检查，补上 A2 的一部分。
5. **大文件骨架**：为 9k 行窗口生成“页签 → 容器 → 命名元素 → visible 条件”的大纲，补上 A4。
6. **一组格式后缀实验**：在一个测试 widget 中把同一个数值用 `|0 |+0 |+=0 |=+0 |0% |+=1% |Y |V |W ...` 各渲染一遍并截图，一次性解决 A3 中最常见的一类疑问。

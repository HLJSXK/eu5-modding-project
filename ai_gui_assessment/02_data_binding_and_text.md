# 02 · 数据绑定、脚本桥与文本

## 1. 表达式 `[A.B.C(args)]`

- 方括号里是 C++ 暴露的数据类型调用链，字符串化后放在 `text` / `raw_text` / `visible` / `enabled` / `down` / `datacontext` / `datamodel` / `on_action` 等属性中。[源]
- 官方文档 `DT/data_types_*.txt` 每个条目有 `Definition type`：
  - **Promote / Global promote**：返回一个对象，可以继续 `.` 链式调用（`Location.GetMarket` → `Market`）。
  - **Function / Global function**：返回终值（`bool`、`CFixedPoint`、`CString`…），或者是 `void` 动作。链条在此结束。
  - 同名条目可能同时有 Promote 和 Function 两个版本（`Location.GetMarket` 在 `:90877` 是 Promote，在 `:92119` 是返回 `[unregistered]` 的 Function）。[源] 链式调用时以 Promote 为准 [推]。
- 字面量参数要带类型：`'(CFixedPoint)0'`、`'(int32)3'`、`'(bool)yes'`、`'(float)1.0'`；字符串直接用 `'abc'`。[源]
- 逻辑和比较是函数而不是运算符：`Not`、`And`、`And3`、`Or`、`EqualTo_string`、`GreaterThan_CFixedPoint`、`BetweenInclusiveOfMax_CFixedPoint`、`Add_float`、`Subtract_float`、`FixedPointToFloat`。比较函数**带类型后缀**，类型不匹配会让整条表达式失败。[源]
- **类型错误会连锁。** error.log 中 `Failed to convert statement for argument '0' for call 'GetGoodsIcon'` 之后紧跟多条 `Malformed token: [ImportExportMarker.GetPossibleItem....]` 和 `failed reading callback`：一次绑定失败会让该 widget 后续属性全部解析失败。[源]
- 不存在“用字符串构造游戏对象”的函数（如 `GetGoods('wheat')`），goods 对象只能从 datamodel 或访问链拿到。tooltip 上下文里也没有全体商品的 datamodel。[源] anti_patterns 两条

## 2. datacontext 与 datamodel

- `datacontext = "[LocationView.GetLocation]"` 之后，子树中可以直接写 `Location.X`，类型名就是上下文名。同一 widget 可以连写多个 datacontext 叠加不同类型。[源] 地点窗口
- tooltip 继承触发它的 widget 的上下文：SOL tooltip 里直接用 `Location.MakeScope`，因为按钮位于 `datacontext = "[LocationView.GetLocation]"` 的子树里。[源]/[推]
- `datamodel = "[...]"` + `item = { ... }`：每个 item 的上下文是元素类型（`LocationPopItem`、`ScriptedOutcome`、`ActionGroup`）。行号用 `PdxGuiWidget.GetIndexInDataModel`。[源]
- 脚本列表也能迭代：`datamodel = "[Player.MakeScope.GetList('name')]"`、`GetGlobalList('name')`，item 内用 `Scope.GetLocation` / `Scope.GetFlagName` 等取值。[源] reference_mods（IV2、CM、CMM）
- `datamodel_reuse_widgets = yes` 会复用行 widget，行的创建期缓存可能过期（CMM 用重开窗口来刷新）。[源] CMM 注释

## 3. GUI ↔ 脚本桥

| 方向 | 写法 | 返回 | 注意 |
|---|---|---|---|
| 读 script_value | `[Location.MakeScope.ScriptValue('name')]` | `CFixedPoint` | 每帧求值；SOL 的大部分显示都走这条。复杂 value 放进 GUI 有性能代价 [推]。 |
| 带多个作用域读 value | `GuiScope.SetRoot(x.MakeScope).AddScope('k', y.MakeScope).ScriptValue('v')` | 同上 | 社区 mod 常用。 |
| 读变量 | `Scope.GetVariable('x').GetValue` / `.IsSet` | `Scope` → `CFixedPoint` / `bool` | 官方还有 `Scope.GetValueWithDefault(Arg0)`，项目和所有参考 mod 都**从未使用**。 |
| 读全局变量 map | `GetVariableFromGlobalVariableMap('name', Market.MakeScope).GetValue` | 同上 | 市场不能存变量，所以 SOL 用 market scope 作为 map 的 key。[源] anti_patterns |
| 执行脚本 | `GetScriptedGui('x').Execute(GuiScope.SetRoot(...).End)` | void | `scripted_guis/*.txt` 中需要 `scope`、`effect`、`is_shown`、`is_valid`、`saved_scopes` 等字段。 |
| 判断 | `.IsShown(...)` / `.IsValid(...)` | bool | 读 scripted_gui 的 `is_shown` / `is_valid` trigger。 |
| 原始值包成 scope | `MakeScopeBool(x)`、`MakeScopeValue(x)`、`MakeScopeFlag('f')` | Scope | 用于把 GUI 才能拿到的数据传给脚本（CM 用法）。 |
| 宏 | `<阶段>/data_binding/*.txt`：`macro = { definition = "Foo(Arg)" replace_with = "..." }` | — | 社区 mod（CMM、CM、M&T）使用，本项目没有。 |

**未使用变量校验陷阱**：Jomini 判断变量是否被使用时，只统计脚本侧读取；GUI / 本地化中的 `GetVariable...` 读取不算。只为 GUI 显示而写的变量会在 error.log 刷 `set but never used`，必须在实际运行的脚本路径里也读一次。[源] anti_patterns

## 4. 文本

- `text = "KEY"` 走本地化（也可以直接写表达式）；`raw_text = "..."` 是字面量，但其中的 `[...]`、`#X…#!`、`@icon!` 仍会被解析。[源]/[推]
- `default_format = "#name"` 设置整段默认样式；行内样式写成 `#R 文本#!`。所有样式定义在 `LS/textformatting.gui`：

| 代码 | 定义 | 实际外观（RGB 来自源码） |
|---|---|---|
| `#T` | tooltip_label | HeadersFont、粗体、白 (240,235,217) |
| `#E` | explanation_link | 粗体、概念蓝 (125,199,227) |
| `#L` | game_link + color_link | 浅金 (250,224,166) |
| `#R` / `#G` / `#Y` | negative / positive / zero_value | 红 (227,97,102) / 绿 (89,212,105) / — |
| `#V` / `#H` / `#S` | value / highlight / 斜体副标题 | 白 / 黄 (204,204,0) / 灰斜体 |
| `#header_titles`、`#yellow_titles`、`#subtle_name` | 标题类 | 白头部字体 / 黄头部字体 / 浅蓝斜体 FlavorFont |

- 色盲模式会覆盖 `color_green` / `color_red`（`textformatting.gui:1-41`）。[源]
- **数字格式后缀 `|xxx`**：观察到的组合包括 `|0 |2 |% |2% |%0 |+= |+=2 |2+= |+=1% |-=2% |=+2 |Y |L |V |W |E |e |U |<1%`。**仓库内没有任何文档。** 推断：数字 = 小数位，`%` = 百分比，`+=` = 带符号并按正负着色，`-=` = 反向着色，字母 = 套用同名样式，`E/e` = 概念链接。[推]
  - 反例：原版写 `raw_text = "+[X|+0]"`，SOL 也写 `"+[...|+2]"`，即在 `|+N` 前手动加 `+` 号。这说明 `|+N` **本身可能不显示正号**，那么 `+` 单独出现时的含义未知。[疑]
  - SOL 对税率、控制力这类非增量数值使用 `|+=1%`。如果上面的推断成立，它们会显示为绿色的“+64.0%”。[疑] 需实机确认。

## 5. 文本图标 `@name!`

- 定义在 `MM/shared/font_icons.gui` 的 `texticon = { icon = name iconsize = { texture size offset fontsize } }`，共约 380 个。[源]
- **商品图标不在 font_icons.gui 里**，但原版本地化大量使用 `@amber!`、`@sand!`、`@wine!`，SOL 也用。结论：引擎会按 goods key 自动注册商品文本图标。[源]/[推] 因此 CLAUDE.md 的规则“使用前先确认 font_icons.gui 中存在”会对商品给出**假阴性**；`data/index/icons.txt` 同样缺少商品图标。
- SOL 的骆驼（1.4 新商品）没有用 `@camels!`，而是用 icon 贴图 `icon_goods_camels.dds`。按上面的推断，`@camels!` 很可能也可用。[疑]
- 文本图标名可以动态拼接：`"@[expr]!"`。[源] `IG/build_location_lateralview.gui:819`

## 6. 本地化在 GUI 中的作用

- YAML 必须是 UTF-8 BOM、直引号。[源] CLAUDE.md
- 本地化字符串里可以写数据表达式（SOL 的 `LOCATION_SOL_GUI_SUMMARY` 直接调用 `Location.MakeScope.ScriptValue`），上下文来自引用它的 widget。[源]
- 社区 mod 把本地化当成数据表使用：`Localize(Concatenate(...))`。[源] reference_mods

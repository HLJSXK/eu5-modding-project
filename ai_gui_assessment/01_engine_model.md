# 01 · EU5 GUI 引擎模型（Jomini GUI）

> **注意**：本文写于 2026-10-11 实机截图之前。已验证的规则以 [`docs/guides/EU5_GUI_Modding_Guide.md`](../docs/guides/EU5_GUI_Modding_Guide.md) 为准；与之冲突的推断（如 hbox 对齐、`|+N` 格式、`spriteborder` 单位、商品图标）已被实机推翻。

> 本文是 AI 在阅读本项目全部 GUI 相关资源后整理的**理解**，不是权威规范。
> 每条结论标注证据等级：**[源]** = 直接引用游戏/模组源码或官方文档；**[推]** = 由多处用法推断，未见文档；**[疑]** = 有矛盾或无法验证。
> 路径缩写：`IG` = `reference_game_files/game/in_game/gui/`，`MM` = `reference_game_files/game/main_menu/gui/`，`LS` = `reference_game_files/game/loading_screen/gui/`，`DT` = `reference_official_defines/docs/`。

## 1. 文件与加载

| 主题 | 理解 | 证据 |
|---|---|---|
| 三个加载阶段 | GUI 分布在 `loading_screen/gui`、`main_menu/gui`、`in_game/gui`。前两阶段定义的 type/template 在 in_game 可用（tooltip 基础类型在 `MM/shared/main_menu_cooltip_types.gui`）。 | [源] |
| 整文件覆盖 | `.gui` 是**按相对路径整文件替换**，没有 INJECT/REPLACE 这种对象级合并。SOL 想改 `location_window.gui` 的一个按钮，必须拥有整份 9000+ 行文件。这是 SOL 用生成器（`sync_location_window.py`、`generate_sol_location_window.py`）维护窗口的根本原因。 | [源] `docs/technical/SOL_Glorp_UI_Compatibility_Check.md` |
| 情势面板与情势绑定 | `panels/situation/<situation_key>.gui`，顶层直接写 `situation_panel = { ... }`；靠文件名对应情势 key。 | [源] `IG/panels/situation/readme.txt`；[推] 绑定靠文件名 |
| scripted widget | 在 `gui/scripted_widgets/*.txt` 写 `gui/文件.gui = widget_name`，引擎会全局实例化该 widget（无窗口、0×0），SOL 借此在进入游戏后跑脚本。 | [源] `src/stable/in_game/gui/scripted_widgets/SOL_migration_scripted_widgets.txt` |
| type 重名 | 多个 mod 定义同名 `type`（如 `zoom_to_button` 在 SOL、Glorp UI、Construction Manager 中各有一份）。哪份生效、是否报错，**项目内没有证据**。 | [疑] 见 06 文档 |

## 2. 复用机制：type / template / block

```
types SomeGroup {
    type situation_card_common = card_common {        # 继承：在 card_common 基础上再覆盖
        blockoverride "header_decor_templates" { ... }
    }
}
template bg_paper_card { background = { ... } }       # 纯属性包，using = 粘贴
```

- **type** = 可实例化的“新元素名”，可以继承另一个 type，并在继承时写 `blockoverride`。[源] `IG/shared/cards.gui:1650`
- **template** + `using = name` = 把一组属性/子元素原样粘贴到当前位置。[源] `MM/shared/backgrounds.gui:749`
- **block "x" { 默认内容 }** = type 内的插槽；使用处用 `blockoverride "x" { 新内容 }` **替换整个插槽**；`blockoverride "x" {}` = 删除默认内容。[源]
- blockoverride 可以穿透多层嵌套类型命中内部的 block。例如 SOL 在 `situation_panel` 实例上覆盖 `situation_panel_main_content`，再在其中的 `situation_card_common` 上覆盖 `common_bottom_content`。[源]
- **block 在什么位置，内容就插到什么位置。** 这是最容易被忽略的一点。`navigational_button_alt` 的 `block "icon_texture"` 位于内部 `icon = {}` 的**内部**，所以 SOL / Glorp 在 `icon_texture` 里写的 `piechart = {...}` 会成为该 icon 的子元素，而不是按钮的直接子元素。[源] `MM/shared/main_menu_buttons.gui:2359-2414`
- **校验也发生在插入点。** error.log 中的 `Error at gui/glorp.gui:515 (property origin is at gui/map_markers.gui:986) - Unsupported property: parentanchor on widgets that are a child of a hbox/vbox` 说明：带 `parentanchor` / 百分比 `size` 的内容一旦落进 hbox/vbox 的直接子级，就会报错，即使它写在别处。[源] `docs/error_log/error.log`
- blockoverride 只能替换 block **原有的全部内容**，不能“改其中一个属性”。反模式记录：在只承载 `text` 属性的 block 里塞 widget 是错的。[源] `docs/knowledge/anti_patterns.yaml`（common_header_text 条目）
- `@name = 值` 与 `@[a - b * 2]` 是编译期常量和算术。[源] `MM/shared/main_menu_cooltip_types.gui:1-4`

## 3. 布局

| 元素 | 作用 |
|---|---|
| `widget` | 自由定位容器：子元素靠 `position` / `parentanchor` / `widgetanchor` 放置，可以重叠。SOL 用它把“商品图标 + 红叉”叠在同一格。 |
| `hbox` / `vbox` | 自动排布行和列。子元素**不能**用 `parentanchor` 和百分比 `size`（引擎校验报错），宽度靠 `layoutpolicy_*`、`minimumsize`、`maximumsize`、`expand = {}`。 |
| `expand = {}` | 吸收剩余空间的弹簧。Glorp 人口页签顶部用 `expand` 把满意度按钮和 SOL 按钮夹在中间。**反过来同样成立**：`layoutpolicy_horizontal = expanding` 的 hbox 里如果全是固定尺寸子元素且没有 `expand`，多余空间会**均匀分配到子元素之间**，首尾贴边（用户实机确认，SOL 商品网格）。要左对齐必须在末尾写 `expand = {}`（`card_common` 默认内容就是这样）。 |
| `fixedgridbox` / `dynamicgridbox` | datamodel 驱动的网格。`addrow` / `addcolumn` 固定格子尺寸，`datamodel_wrap` 控制换行。 |
| `scrollarea` + `scrollwidget` + `scrollbar_vertical` | 滚动视口。 |
| `layoutpolicy_horizontal/vertical` | 主要值：`expanding`、`fixed`、`preferred`、`growing`、`shrinking`。模板 `layoutpolicy_expanding` 同时设两轴。 |
| `size = { -1 45 }` | -1 = 该轴交给布局/内容决定 [推]。 |
| `ignoreinvisible = yes` | 不可见子元素不占位 [推]。ContextualTooltipType 用它折叠隐藏的概念链接行。 |
| `set_parent_size_to_minimum` | 让父级收缩到最小尺寸，tooltip 用它自适应。 |

**SOL 的尺寸是精确算出来的。** 情势表格 130 + 5×68 = 470 = 文本 `max_width 470`；内宽 570 − 15×2 = 540，减去滚动区 10×2 和卡片 15×2 后约 480–490。地点 tooltip 是 150 + 5×72 = 510，比标准 tooltip（`@tooltip_title_wide = 420`）宽。AI 改这些表格时如果不重算，会撑破或截断。

## 4. 状态与生命周期

```
state = { name = _show            on_start = "[...]" }   # 可见性 hidden->shown 时触发
state = { name = x  trigger_on_create = yes  on_start = "[...]" }  # 创建时触发
```

- `_show` 只在**已存在的 widget 从隐藏变为可见**时触发。动态创建时就已可见的 widget（例如情势面板的子 widget）不会触发 `_show`，必须用 `trigger_on_create`。[源] `anti_patterns.yaml` 地图模式相关三条
- `state.on_start` 中的表达式**不继承** widget 的 datacontext，调用方法时要在表达式里自己取对象：`"[GetMapMode('tag').SetMapMode]"`。[源] anti_patterns
- `PdxGuiWidget.PushMapModeOverride('tag')` 的生命周期绑定在 widget 上，widget 销毁时自动弹出。[源] `DT/data_types_gui.txt:5964`，SOL 情势面板第 4-13 行
- 动画：`duration`、`bezier`、`next`、`on_finish`、`PdxGuiWidget.TriggerAnimation('name')`。[源] `IG/alertmanager.gui:233-245`、`IG/economy_lateralview.gui:430-440`

## 5. 交互

| 机制 | 理解 |
|---|---|
| `tooltip = "KEY"` | 简单文本 tooltip，值是本地化 key。SOL 商品格的 `tooltip = "amber"` 用商品 key 本身当本地化 key。 |
| `tooltipwidget = { SomeType {...} }` / `{ using = some_template }` | 富 tooltip。SOL 地点按钮用 `using = StandardofLiving_tooltip`，模板里是一个 `ContextualTooltipType`。 |
| `action_tooltip = { title on_action click_type click_mode }` | 点击动作与悬停提示二合一。页签按钮用它执行 `LocationView.Vars.Set('tab', ...)`。 |
| 1.4 脚本动作按钮 | `header_action_button_left_uber` + `visible = "[PdxGuiWidget.IsUberButtonVisible]"` + `enabled = "[PdxGuiWidget.IsUberButtonEnabled]"` + `scripted_action_tooltip = { action_name actor parameter... }`。旧的 `header_action_button_left` 与 `actor/left_action` 字段在 1.4 被移除。[源] `reference_official_defines/types/resolutions.txt:87-101`、`EU5_1.4_Beta_Compatibility_Audit.md` |
| 按钮必须有 tooltip | error.log 中有 `Button is missing tooltip!`（`tooltip_validation.cpp`）。[源] |
| 重复属性 | 同一 widget 写两次 `visible` 会报 `Duplicate property 'visible'`，并导致后续 token 解析混乱（`Malformed token`）。[源] error.log |

## 6. 视图状态：Vars

- `LocationView.Vars`、`SituationView.Vars`、`LateralView.Vars` 都返回 `Context` 对象，可用方法有 `Set`、`Toggle`、`Exists`、`HasValue`、`NotExistOrHasValue`、`Clear`。[源] `DT/data_types_uncategorized.txt:57181-57252`
- 页签惯用法：页签按钮的 `down` 与面板的 `visible` 都读同一个 key。默认页签用 `NotExistOrHasValue`，其余用 `HasValue`。[源] 地点窗口第 2390-2440 行
- 全局 UI 状态用 `GetVariableSystem.Set/Exists/HasValue`。[源] `IG/game_rules.gui:39`

## 7. ui_library.gui

`IG/ui_library.gui`（约 19k 行）是一个游戏内组件目录窗口，分 Windows / Buttons / Text Format / Cards / Portraits / Animations / Building blocks 等页，其中 Cards 页包含 “Common situation card”（约第 17165 行）。它是查找“某种外观该用哪个 type”的最佳入口，但本项目的知识库从未提到它。[源]

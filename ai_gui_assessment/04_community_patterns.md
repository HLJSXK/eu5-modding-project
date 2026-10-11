# 04 · 社区 mod 的 GUI 技法目录（reference_mods 调研摘要）

> **注意**：本文写于 2026-10-11 实机截图之前。已验证的规则以 [`docs/guides/EU5_GUI_Modding_Guide.md`](../docs/guides/EU5_GUI_Modding_Guide.md) 为准；与之冲突的推断（如 hbox 对齐、`|+N` 格式、`spriteborder` 单位、商品图标）已被实机推翻。

> 来源：对 `reference_mods/*` 中 GUI 文件的检索。主要样本：Glorp UI 3812518640、Construction Manager 3736668860、CMF/CMM 3692202776、M&T 3735059838、IV2 3599735023、Country Events 3681899116。
> 注意：`reference_mods/3698931463` 是 **SOL 自己的旧发布版**，未列入 `MOD_INDEX.md`。用它做“社区佐证”属于循环论证。

## 新窗口的两种做法

1. **控制台命令创建 / 销毁**：`ExecuteConsoleCommand('gui.createwidget gui/x.gui name')` / `'gui.ClearWidgets name'`，配合 `GetVariableSystem.Toggle` 记录开关状态（Glorp `glorpUI_ingame_menu.gui:178`）。据 CMM 注释，控制台命令在多人游戏中不可用。
2. **常驻 widget，用 visible 门控**：在 `scripted_widgets` 注册后，用 `visible = "[GetVariableSystem.Exists('x_open')]"` 控制，热键 `input_action` + `on_input_action_shortcut` 切换（CMM `cmm_window.gui:2-18`）。层级用 `layer = top/bottom`。

## “驱动器” widget（只为跑逻辑）

- 0×0 或放在 `position = { -10000 1 }` 的隐藏 widget，在 `trigger_on_create` / `_show` / `trigger_when` 时 `Execute` scripted GUI。SOL 的 after-lobby 调用器、CMF、CM 都用这种做法。
- `visible_at_creation = no` + `_show`：确保创建后一定经历一次 hidden→shown，从而把 `_show` 当作“条件满足”事件来用（CM 注释）。
- GUI 可以直接执行引擎动作，例如 `BuildOrExpandBuildingDefault(...)`（CM），也可以通过 scripted GUI 触发 on_action（CMF 用 `trigger_event_silently`）。

## 覆盖原版的手段

| 手段 | 例子 | 风险 |
|---|---|---|
| 同路径整文件替换 | 6 个 mod 都替换了 `location_window.gui` | 互斥，只能有一个生效；需要统一合并 |
| 新文件中重定义原版 type / template 名 | Glorp 重定义 `button_mapmode`、`cabinet_card` 等 40+ 个 | 生效规则未文档化 [疑] |
| 抽取原版类型副本 `vanilla/*_vanilla_types.gui` | CMF、Glorp（SOL 继承了这种做法） | 其他 mod 整文件替换后，原文件中的 type 仍有定义 [推] |
| 劫持原版 type 作为“mod 存在”标记 | CMF 重定义 `steam_logo_button` 并设置 `GetVariableSystem.Set('cmf_active')` | 依赖重名覆盖的行为 |

## 其它

- 脚本列表 → GUI：`GetList` / `GetGlobalList` + `Scope.GetX`。
- 数据绑定宏：`data_binding/*.txt`。
- 不加引号的 `text = [estate_tax_base|E]` 也能用（原版即有）。
- 作者注释中承认的未解问题：某些 datacontext “Doesn't work.. Why?”（Glorp `outliner_entries.gui:3067`）；`max_update_rate` 的性能阈值不明（CMM）。社区本身对引擎也有未知区。

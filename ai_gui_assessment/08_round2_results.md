# 08 · 第二轮比对结果（UI Library 26 页 + 5 个原版界面）

截图：`screenshots/ui_library/`（26 页，对应关系见 `INDEX.txt`）、`screenshots/round2/`（事件、市场、地点 tooltip、政府、战斗）。
渲染：`images/ui_library/`，用 `python renderer/lib_batch.py [tag ...]` 一次性渲染全部或部分页面。

## 本轮确认并已写入渲染器的规则

| 规则 | 实机证据 | 修正前 |
|---|---|---|
| `##` 是转义，显示一个字面量 `#` | Text Format 各页的说明“default_format = #high”，源码写的是 `##high` | 把 `#high` 当成格式代码吞掉，只剩下 `#` 或空白 |
| 非文本元素上的 `min_width` 等同于 `minimumsize` 的宽度 | 每个条目左栏都是 800px 宽（`vbox_component_entry` 的 `min_width = 800`） | 忽略，左栏被压缩，示例和说明挤在一起 |
| 文本的 `max_width` 同时限制元素宽度，expanding 的 text_multi 不会超过它，由父盒居中 | 说明文字是 600px 宽的块，居中在右侧卡片内 | 文本块撑满整行 |
| `framesize` 的单位是界面单位（贴图像素 = framesize × texture_density），与 spriteborder 相同 | 复选框 `checkbox.dds` 160×80、density 2、framesize {40 40}，实机显示为菱形框 | 只截出贴图的四分之一（一条斜线） |
| 嵌套实例自己写的 blockoverride 优先于从外层继承的同名覆盖 | UI Library 在 `scrollbox_content` 里又嵌了一个 scrollbox；按“外层优先”会无限递归 | 渲染崩溃 |
| 按钮上的 `text` / `raw_text` 由按钮内部的 `buttonText = { textbox }` 显示 | 所有页签按钮都有文字 | 二级页签全部为空 |

当前复核中，SOL 局势面板两张输出与既有基线一致；SOL tooltip 的 550px 宽度恢复后也与既有输出一致。地点窗口相对既有输出仅在 `(263,48)-(305,77)` 范围内有变化，尚未据此宣称整图像素一致。

## 逐页结论

| 页面 | 结论 |
|---|---|
| Text Format 四页（字号、常规、tooltip、数字） | 字体、字号、颜色、斜体与实机一致；本轮修正后布局也一致 |
| Windows → Panels / Containers | 暂停横幅、顶栏、各文化风格的窗口头与实机几乎相同 |
| Buttons → Action / Round / Control / Tabs / Main groups / Animated | 圆形框、导航按钮、页签按钮、动画按钮的静态外观一致 |
| Cards → 2D Situations / Disasters / Overviews | 各类卡片头部、边框一致 |
| Portraits | 画框和缎带一致；人物肖像是 3D 渲染，无法复现 |
| Buttons → Flags | 框体一致；国旗和家族纹章是程序生成，无法复现 |

## 第二轮遗留项的处理

更新（2026-10-12）：以下为静态渲染器的当前状态。数据仍来自示例，实际存档与交互状态须在游戏内验证。

| 页面 | 当前状态 |
|---|---|
| Buttons → Selectors | `dropdown` 和 `ranged_slider` 的静态状态已渲染；滑条轨道的模板 `background` 边框已补齐 |
| Windows → Tooltips | `TooltipBlockList` 表格已用 mock 数据渲染，不解析任意 `textcontext` |
| Cards → Cards 1 | DLC 卡片宽度和文字换行已按实机截图调整 |
| Cards → Situations / IOs | 人物字段与成员列表已补 mock 数据；IOs 的成员列表按 `flipdirection = yes`、`datamodel_wrap = 1` 分成三行；3D 肖像和程序化旗帜仍无法复现 |
| Cards → Disasters | 空动作列表已补 mock 数据；静态卡片可渲染，实际动作仍需存档数据 |
| Building blocks → Test | 圆角按钮及两侧装饰已按实机截图调整 |

Selectors 底轨和 IOs 三行成员列表已分别与 `screenshots/ui_library/lib_buttons_selectors.png`、`lib_cards_ios.png` 对照。Selectors、IOs、Situations、Situationsios、Disasters 五页重渲染后均无普通未知表达式。SOL 局势面板两张基线图完全一致；tooltip 的外框恢复为实机截图中的约 550px，且未改变 UI Library 的 450px 紧凑 tooltip。

## 5 个原版界面

事件、市场、地点 tooltip、政府、战斗这五张截图已收好。渲染器使用对应的静态 mock 场景比对布局；真实存档数据和交互状态仍需游戏内验证。

| 原版截图 | 当前渲染状态与边界 |
|---|---|
| 事件 `screenshots/round2/event.png` | 已选中普通事件窗口根节点，正文换行、插画和固定宽度选项可静态渲染；选项悬停 tooltip 与实际交互状态未复现。 |
| 市场 `screenshots/round2/market.png` | 商品页搜索栏、筛选条件和排序控件可见，商品行使用 mock 数据；排序图标是示例，市场的 10 个 `datacontext` 仍缺少可解析的存档对象。截图中的两列表格 tooltip（最大盈余 / 最大短缺）数字右对齐，其红绿色遵循 `|+` 格式规则。 |
| 地点 tooltip `screenshots/round2/location.png` | 这张是**原版地点 tooltip**，不是 SOL 的 `images/r3_location_sol_tooltip.png`。顶部紫色 DEBUG INFO 区域来自截图的 debug 模式；正式版没有此区。`run.py tooltip` 仅渲染 SOL tooltip，其 550px 外框宽度已对照 `screenshots/C_sol_tooltip.png` 复核。 |
| 政府 `screenshots/round2/gov.png` | 阶层页签和三张阶层卡片已对位；阶层数据仍是 mock，16 个 `datacontext` 未解析，3D 人物场景和真实存档状态无法复现。 |
| 战斗 `screenshots/round2/battle.png` | 攻守双方显示不同兵力，左右中侧翼分别绑定 mock 数值；3D 场景、地图背景和真实存档状态无法复现。 |

四个已实现的原版窗口（事件、市场、政府、战斗）当前普通未知表达式均为 0；这不等于市场和政府的上下文已完整解析。地点窗口另有 20 个未解析 `datacontext`，其 mock 图像只能用于静态布局检查。

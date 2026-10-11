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

全部修正后复核了第一轮的三张图，结果不变。

## 逐页结论

| 页面 | 结论 |
|---|---|
| Text Format 四页（字号、常规、tooltip、数字） | 字体、字号、颜色、斜体与实机一致；本轮修正后布局也一致 |
| Windows → Panels / Containers | 暂停横幅、顶栏、各文化风格的窗口头与实机几乎相同 |
| Buttons → Action / Round / Control / Tabs / Main groups / Animated | 圆形框、导航按钮、页签按钮、动画按钮的静态外观一致 |
| Cards → 2D Situations / Disasters / Overviews | 各类卡片头部、边框一致 |
| Portraits | 画框和缎带一致；人物肖像是 3D 渲染，无法复现 |
| Buttons → Flags | 框体一致；国旗和家族纹章是程序生成，无法复现 |

## 仍有差异、尚未修正

| 页面 | 差异 | 原因判断 |
|---|---|---|
| Buttons → Selectors | 下拉框和滑条不显示 | `dropdown`、`slider` 是引擎特殊控件，渲染器尚未实现 |
| Windows → Tooltips | 实机的 tooltip 内是一张表格（`textcontext = "TOOLTIP_TABLE_TEST"`），渲染器显示空列表 | 表格内容由引擎从本地化生成（`TooltipBlockList`），需要实现这套表格格式 |
| Cards → Cards 1 | DLC 卡片在实机中更窄、更高，文字自动换行；渲染器中的卡片过宽 | 很可能是 `max_width` / 多行文本的最小宽度规则，还要再查 |
| Cards → Situations / IOs | 人物卡、成员列表里的数据为空 | 依赖存档里的人物和国家数据，需要另外编示例数据 |
| Building blocks → Test | 实机按钮是圆角，渲染器是直角，两侧多出装饰 | 尚未分析 |

## 5 个原版界面

事件、市场、地点 tooltip、政府、战斗这五张截图已经收好。它们依赖大量存档数据（人物、市场、战斗），每一个都要像地点窗口那样单独编写示例数据才能渲染，所以本轮还没有渲染。从截图中已经可以直接确认的规则：

- **地点 tooltip**：顶部是一块紫色的 DEBUG INFO 区域，因为你的游戏开着 debug 模式；正式版不会显示。渲染时需要区分这两种情况。
- **事件窗口**：正文是自动换行的多行文本，选项按钮宽度固定，选项 tooltip 出现在按钮右下方。
- **市场 tooltip**：两列表格（最大盈余 / 最大短缺）宽度相等，数字右对齐，红绿色与 `|+` 格式规则一致。

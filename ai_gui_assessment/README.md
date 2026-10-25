# ai_gui_assessment — EU5 GUI 渲染器与研究资料

**做 GUI 工作请先读 [`docs/guides/EU5_GUI_Modding_Guide.md`](../docs/guides/EU5_GUI_Modding_Guide.md)。**
那份指南汇总了已验证的规则（每条都标了证据等级）；本目录存放支撑这些规则的工具和证据。
`CLAUDE.md` 的 Session Start 会把所有 GUI 任务路由到那份指南，再由指南路由到这里。

## 目录

| 路径 | 内容 |
|---|---|
| `renderer/` | Jomini GUI 渲染器（Python，PIL + numpy） |
| `screenshots/` | 1080p 实机截图（比对的真值）：`A_/B_/C_*.png` 为 SOL 三个界面；`ui_library/` 为 UI Library 全部 26 页（对应关系见 `INDEX.txt`）；`round2/` 为事件、市场、地点 tooltip、政府、战斗 |
| `images/` | 渲染结果：`r1` 局势面板、`r2` 地点窗口人口页签、`r3` 地点 SOL tooltip（各带 `*_tree.txt` 元素树）；`ui_library/` 为 UI Library 26 页 |
| `01`–`05_*.md` | **截图之前**写的研究笔记（引擎模型、数据绑定、SOL 界面结构、社区技法、AI 欠缺分析）。与指南冲突时以指南为准 |
| `06_screenshot_requests.md` | 第一轮实机比对结果（SOL 三个界面） |
| `07_next_screenshots.md` | 第二轮截图需求（已完成） |
| `08_round2_results.md` | 第二轮比对结果，以及尚未解决的差异清单 |

## 运行

前提：`eu5` conda 环境（`$env:EU5_PYTHON`），游戏安装在
`C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V`（贴图和字体从游戏目录读取，`reference_game_files/` 里没有二进制文件）。
按 1080p、UI 缩放 100% 渲染，1 个 GUI 单位 = 1 个屏幕像素；设置 `RENDER_SCALE=2` 可输出 2 倍图。

```powershell
$env:PYTHONUTF8='1'
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py situation      # images/r1_*
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py location       # images/r2_*
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py tooltip        # images/r3_*
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py market         # images/market.png
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py event          # images/event.png
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py government     # images/government.png
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py battle         # images/battle.png
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py ui_library cards ui_library_text_tabs=cards1
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py ui_library windows windows=tooltips
& $env:EU5_PYTHON ai_gui_assessment/renderer/lib_batch.py          # UI Library 全部 26 页（约 2–3 分钟）
& $env:EU5_PYTHON ai_gui_assessment/renderer/guidef.py situation_card_common   # 打印 type/template 的完整定义
& $env:EU5_PYTHON ai_gui_assessment/renderer/compare.py SHOT RENDER sx sy w h [rx ry] [zoom] OUT
```

每次运行会输出 `unknown expressions`，即没有示例数据的普通绑定表达式；`unresolved datacontexts`
单列无法由静态 mock 还原的上下文绑定，前者为 0 不代表后者全部解析。新界面的示例数据写在
`renderer/scenarios.py`（局势、UI Library）或 `renderer/scen_location.py`（地点窗口、tooltip）。
`lib_batch.py` 会把 UI Library 各页的 `*_tree.txt` 元素树保存在 `images/ui_library/`。

| 模块 | 作用 |
|---|---|
| `pdx.py` | Paradox 脚本 / GUI 解析器（`@常量`、`@[表达式]`、block/type/template） |
| `gui.py` | type/template 数据库（原版 + SOL 按相对路径覆盖），元素展开（block/blockoverride、`buttonText`） |
| `engine.py` | 盒布局、自由定位、滚动区、网格、绘制、饼图、滚动条 |
| `textures.py` | DDS 加载、九宫格（`spriteborder` 按界面单位）、帧、`modify_texture` 混合、纯色图层 |
| `text.py` | 富文本（`#格式#!`、`##`、`@图标!`）、字体与中文回退、行高 |
| `data.py` | 本地化、文本格式、表达式求值、数字格式后缀、概念图标 |
| `scenarios.py` / `scen_location.py` | 示例数据 |
| `guidef.py` | 打印 type / template 的完整定义 |
| `compare.py` | 截图与渲染图的并排 / 放大比对 |
| `lib_batch.py` | 一次性渲染 UI Library 的全部或指定页 |

## 精度与局限

已用实机截图对照 SOL 局势面板、地点窗口和地点 tooltip，以及 UI Library 的文字格式、窗口、按钮和卡片。
局势面板与地点窗口的既有基线局部可达到像素一致；SOL 地点 tooltip 的外框宽度与实机截图同为约 550px，但不能把三个界面的整体误差概括为约 1 像素。
无法复现：3D 场景、无可用贴图的插画、程序生成的国旗和纹章、人物肖像、动画与悬停状态、真实存档数据。已有贴图的事件插画可静态渲染。
`dropdown`、`ranged_slider`、UI Library 的 `TooltipBlockList` 表格以及人物/成员卡片可用 mock 数据静态渲染；不解析任意 `textcontext`，也不模拟控件交互。
已知差异见 `08_round2_results.md`。

## 后续工作方法

1. 准备目标界面的 1080p、UI 缩放 100% 全屏截图，放入 `screenshots/`。
2. 渲染并用 `compare.py` 比对，找到第一处结构性差异，借助元素树和 `guidef.py` 追溯到具体的引擎规则。
3. 修正渲染器，重新渲染三个基线界面确认没有回退，再把规则及证据等级写进指南。

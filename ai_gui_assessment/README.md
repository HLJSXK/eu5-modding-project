# AI 对 EU5 GUI 的理解评估

本目录是诊断用的交付物，目的是暴露 AI 在 EU5 GUI 上的欠缺，**不是**后续开发的指导文件（因此没有放进 `docs/knowledge/`，也没有更新 BRIEF）。

## 渲染器 `renderer/`

这是一个最小的 Jomini GUI 渲染器，直接读取游戏目录（`C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game`）和 SOL 的 `src/stable` 文件：
- 解析原版加 SOL 覆盖后的全部 `.gui` 文件，展开 type / template / block / blockoverride；
- 盒布局：fixed / expanding / growing、min/max；多余空间先分给 expanding，再分给 growing（`expand = {}` 属于 growing）；没有弹性元素时，剩余空间均分到间隙；
- 从游戏目录解码 DDS 贴图，实现九宫格拉伸和平铺、texture_density、modify_texture 混合；
- 使用游戏自带的 Noto 字体（按 simp_chinese 的回退顺序选字），文字格式取自 `textformatting.gui`，本地化取自游戏和 SOL；
- 数据表达式由 mock 数据求值（`scenarios.py`、`scen_location.py`）。

| 文件 | 作用 |
|---|---|
| `run.py` | 入口：`python renderer/run.py situation\|location\|tooltip` |
| `pdx.py` | Paradox 脚本 / GUI 解析器 |
| `gui.py` | type / template / block 数据库与展开 |
| `engine.py` | 布局与绘制 |
| `textures.py` | DDS 加载、九宫格、混合模式 |
| `text.py` | 富文本、字体、文本图标 |
| `data.py` | 本地化、文本格式、表达式求值、数字格式 |
| `scenarios.py` / `scen_location.py` | 示例数据 |
| `guidef.py` | 调试工具：`guidef.py NAME...` 打印某个 type 或 template 的完整定义 |
| `compare.py` | 截图与渲染图的并排 / 放大比对 |

## 输出 `images/`

按 1080p、UI 缩放 100% 渲染：1 个 GUI 单位 = 1 个屏幕像素，与游戏截图逐像素对应。左侧面板为 570×950（1080 减去顶栏 40 和面板栏 90，见 `ingame_topbar.gui`）。如需放大查看细节，设置环境变量 `RENDER_SCALE=2`。

| 文件 | 内容 |
|---|---|
| `r1_situation_panel.png` / `r1_situation_panel_full.png` | 局势面板：1080p 实际效果（滚动区被裁切）/ 加高后完整展开 |
| `r2_location_window.png` | 地点窗口「人口」页签 |
| `r3_location_sol_tooltip.png` | 地点 SOL 按钮 tooltip |
| `r*_tree.txt` | 展开后的元素树和每个元素的布局结果，用于和实机截图比对 |

## 实机比对

截图在 `screenshots/`，比对结果和已确认的规则见 **`06_screenshot_requests.md`**。比对命令：

```
python renderer/compare.py SHOT RENDER sx sy w h [rx ry] [zoom] OUT
```

修正后，tooltip 高度与实机完全一致，各文字行的纵向位置误差在 0–1px 以内。3D 场景、插画、国旗以及具体数值无法复现（示例数据）。

## 文档

| 文件 | 内容 |
|---|---|
| `01_engine_model.md` | 文件加载、type/template/block、布局、状态与生命周期、交互、Vars、ui_library |
| `02_data_binding_and_text.md` | 表达式与类型、datacontext/datamodel、GUI↔脚本桥、文本格式、文本图标 |
| `03_sol_screens_anatomy.md` | 三个界面的结构树与设计决定 |
| `04_community_patterns.md` | reference_mods 中的社区 GUI 技法 |
| `05_ai_gaps.md` | AI 欠缺的根因、项目内证据、新发现的问题、自评与改进建议 |
| `06_screenshot_requests.md` | **实机比对结果**：已确认的引擎规则、修正前后的差异、仍未确认的项 |

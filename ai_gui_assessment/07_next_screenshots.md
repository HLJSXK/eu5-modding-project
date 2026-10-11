# 07 · 第二轮截图需求（扩展渲染器覆盖面）

第一轮的三个界面已经基本对齐。下一步的目标是让渲染器覆盖**更多引擎特性**，所以这一轮挑选的界面，都集中使用了渲染器尚未实现、或尚未经过实机验证的功能。

截图要求不变：1080p、UI 缩放 100%、全屏截图、不裁切。放到 `tmp/screenshots/` 即可。

---

## 第一优先：UI Library（原版内置的组件目录）

`in_game/gui/ui_library.gui` 是 Paradox 自己的组件展示窗口，**不依赖任何游戏数据**：渲染器和实机看到的内容完全相同，因此每一处差异都只可能是引擎规则的问题。这是最理想的校准素材。渲染器已经可以渲染它，输出在 `images/ui_library/`。

**打开方式**：游戏可执行文件中存在控制台命令 `GUI.CreateWidget 'file' 'widget'`（参数说明取自 eu5.exe 的字符串表）。在控制台输入：

```
GUI.CreateWidget gui/ui_library.gui ui_library_window
```

关闭：`GUI.ClearWidgets ui_library_window`（你的控制台历史里用过这个命令）。

> 我没有在游戏里实际执行过这条命令，如果不生效请告诉我报错，我再换方法。

请依次点开下列页签并各截一张（顶部大页签 → 二级页签）：

| # | 页签 | 要验证的引擎特性 |
|---|---|---|
| L1 | Text Format → Fonts & Sizes | 四种字号、Flavor 字体（斜体衬线）、字体基线 |
| L2 | Text Format → Regular Texts | 各种 `#格式` 的颜色、粗体/斜体、发光 |
| L3 | Text Format → Numbers | 数字格式的颜色（正、负、零） |
| L4 | Text Format → Tooltip texts | tooltip 文本块的样式 |
| L5 | Buttons → Main groups | 主页签按钮（4 帧贴图的选中/未选中态） |
| L6 | Buttons → Tabs buttons | 二级页签按钮 |
| L7 | Buttons → Action buttons | 动作按钮、按钮帧、禁用态 |
| L8 | Buttons → Control buttons | 复选框、滑条、加减号 |
| L9 | Cards → Cards 1 | 各种卡片（纸张卡、卷轴卡）的九宫格边框 |
| L10 | Cards → Situations | 局势卡片 |
| L11 | Windows → Panels / Containers / Tooltips | 窗口框、容器、tooltip 外框 |

## 第二优先：带有特殊布局的原版界面

| # | 界面 | 怎么打开 | 要验证的引擎特性 |
|---|---|---|---|
| G1 | **事件窗口**（任意事件） | 等事件弹出，或控制台 `event <id>` | `text_multi` 自动换行、`bottomtotop`（选项从下往上排列）、`fittype`（插画缩放）、动画状态 |
| G2 | **顶栏资源 tooltip**（悬停金钱数字） | 悬停屏幕左上角的金钱 | 顶栏的进度条、`flowcontainer`，以及 tooltip 的屏幕定位 |
| G3 | **政府面板**（左侧第一个按钮） | 点击顶部左侧的政府按钮 | `mirror`（左右镜像的装饰）、`flowcontainer`、`dynamicgridbox` |
| G4 | **市场总览** | 经济 → 市场 | `overlappingitembox`（重叠排列的图标）、`layoutstretchfactor`（按比例分列宽） |
| G5 | **地点 tooltip**（悬停地图上的地点） | 鼠标停在任意地点上 | 原版使用 `\|W2` `\|R` `\|G` 等格式（第一轮清单中的 D 项） |
| G6 | 战斗界面 | 进入一场战斗后打开 | `progressbar`（士气、兵力条）、`layoutstretchfactor`、`bottomtotop`、`mirror` |

G1 最重要（多行文本换行是目前完全没校准过的部分），其次是 G4（重叠布局和比例列宽目前完全没实现）。

## 补充第一轮未确认的项

| # | 界面 | 要看什么 |
|---|---|---|
| B3 | 一个某阶层占比低于 1% 的地点的人口页签 | `\|<1%` 显示为“(<1%)”还是“(0.4%)” |

# 生活水平行 · 左面板按钮下方（兼容 GlorpUI）—— 新版设计

2026-10-18。**设计已进入正式生成链并写入 stable/standalone；离线渲染通过，实机验收待完成。**
本版替换常驻入口的位置（topbar 悬挂徽章 → 左侧 9 个按钮下方的一整行）；tooltip 复用已实现的
`SOL_LSHUD_tooltip`（`src/stable/in_game/gui/SOL_lshud.gui`），变量契约不变。

2026-10-18 宽度修正：等待首次计算的 tooltip 外框为 570px，与生活水平行等宽；正文最小宽度 550px，
两侧各留 10px，标题背景横向扩展。已有收入的 tooltip 维持 460px。正式生成器拥有此修正，
`scripts/test_sol_lshud_ui.py` 检查两目标、中英文的外框、标题和正文边界；离线预览见
`ai_gui_assessment/images/living_standard_pending_width/`，实际游戏悬停定位仍需实机验收。

同日数据可用性修正：首次计算即显示当前收入并取得排名资格；仅同比等待去年同月样本。
缺少基线时，行、标题与阶层同比区域显示“暂无去年数据”，隐藏箭头、百分比及变化条；排名独立显示。
正式生成器与测试已覆盖“收入和排行可用、同比未出”及“收入可用、排行和同比未出”，新预览在
`ai_gui_assessment/images/living_standard_immediate_income/`。下面的原型脚本保留布局研究用 fixtures，正式实现以生成器为准。

```powershell
$env:PYTHONUTF8='1'
& C:/Users/Hades/anaconda3/envs/eu5/python.exe ai_gui_assessment/prototypes/living_standard_leftrow/build.py
```

生成物（不要手改）：`sol_lshud_leftrow.gui`、`sol_lshud_glorp_compat.gui`、`sol_lshud_leftrow_l_simp_chinese.yml`。
示例数据复用 `../living_standard_hud/build.py` 的虚构 fixtures（只读导入；那份文件也被 `scripts/test_sol_lshud_ui.py` 引用，勿删）。

## 1. 行的规格

| 项 | 值 | 依据 |
|---|---|---|
| 位置 / 尺寸 | 屏幕 `{0 130}`，`570 × 36` | 左面板 `position = { @panel_x @topbar_height }` = `{0 40}`，面板条 90 高（`ingame_topbar.gui:9-17,216-219`）；宽 = `@left_panel_width` 570 |
| 背景 | `bg_panel_bar` + 底部 1px 金线（alpha 0.55） | 与 GlorpUI 统计栏同一底纹（`glorp.gui:39`），两者叠放时是一个家族 |
| 内容（左→右） | 30px 小徽章（底盘 + 文化金环 + 等级图标）· `生活水平` · `低/中/高` ┃ `人均收入` **1.86** @gold! ┃ `同比` 箭头 `+4.5%` ┃ `世界 12 / 87` | 等级图标与箭头沿用 B（`sol_proto/tier_*`、`@arrow_bonus/malus_tier_1/2!`） |
| 首次计算前 | SOL 徽记（0.6 alpha）+ `生活水平 ┃ 等待首次计算` | `sol_ls_pci` 未设置分支 |
| 同比未出 | 收入和排行照常显示，同比区域为 `暂无去年数据` | `sol_ls_pci_yoy` 未设置分支 |
| 排行未出 | 等级位显示 `—`，排名位显示 `排行待更新` | 同 B 的 rank/tier `.IsSet` 守卫 |
| 悬停 | 整行一个热区，`tooltipwidget = { using = SOL_LSHUD_tooltip }` | 已实现的 tooltip；首次计算前宽 570，有收入后宽 460 |
| 显示条件 | 玩家有效、`sol_ls_hud_enabled > 0`、左侧面板**未打开**（`Not(Or(LeftView.IsShown, LeftView.IsSideAttached))`） | 面板打开时侧栏从 y=130 起覆盖这一区域 |
| 隐藏 UI | `using = Animation_Show_Hide_UI`，`on_hide_ui` 左移 570 + 透明，与原版左面板同参数 | `ingame_topbar.gui:221-228` |
| 层 | `layer = bottom`（与 `left_panel` 相同），侧栏 / tooltip / 顶栏自然压在上面 | GlorpUI `left_panel` 的 `layer = bottom` |

挂载方式与 B 相同：单独的 scripted widget 根 `sol_lshud_leftrow_root`，不拥有 `ingame_topbar.gui` /
`left_panel.gui` / GlorpUI 任何文件。实现时用它替换 B 的 `sol_lshud_root` 注册即可。

## 2. GlorpUI 兼容：统计栏顺延到本行下方

GlorpUI（`3601047146`，`glorp.gui`）在同一位置放了一个 450×90 统计栏 `left_panel_info_bar`（局部 `{0 90}`
= 屏幕 y 130）和一个显隐切换小签 `left_panel_info_toggle`（局部 `{20 123}` / `{20 213}`，由 GlorpUI
`left_panel` 实例的 `blockoverride` 设定）。

做法：`sol_lshud_glorp_compat.gui` **重定义这两个类型**，每个都是
```text
type left_panel_info_bar = widget {      # 同名重定义，后加载者生效
    allow_outside = yes
    position = { 0 36 }                  # = 行高，SOL 唯一新增的数值
    widget = { ...GlorpUI 原类型体逐字复制... }
}
```
- 原类型体逐字放进内层 widget：GlorpUI 自己的坐标、`_show/_hide` 动画、`toggleLeftPanelStatsBar` /
  `disableLeftPanelStatsBar` 开关、实例上的 `toggle_pos` / `toggle_state` 覆盖全部照常生效，只是整体下移 36。
- 外层是无尺寸 + `allow_outside` 的 widget——正是 GlorpUI 自己在 `left_panel` 里承载这两个元素的写法
  （`glorpUI_left_panel.gui:894-923`），切换小签在 GlorpUI 中本就位于其父的矩形外且可点击。
- 原类型体由生成器从 GlorpUI 源码按名提取，不手抄；GlorpUI 更新后重跑即可（与 `sync_location_window.py`
  从 GlorpUI 同步地点窗口同一思路）。
- 没装 GlorpUI 时这两个类型无人引用，重定义无副作用。

**前提：SOL 必须在 GlorpUI 之后加载。** GlorpUI 自己就是靠“同名类型后加载生效”替换原版 `left_panel`
（原版 `left_panel.gui` 仍在）；渲染器同样后注册者生效。加载顺序反了，GlorpUI 的统计栏会回到 y=130、
被本行压住第一排（见 `glorp_wrong_load_order_left.png`）。

## 3. 渲染结果（`ai_gui_assessment/images/living_standard_leftrow_20261017/`）

| 文件 | 场景 |
|---|---|
| `vanilla_left.png` / `vanilla_hud.png` / `vanilla_hover.png` | 无 GlorpUI：行在按钮下方，悬停展开已实现的 tooltip |
| `glorp_before_left.png` | 参照：只有 GlorpUI，统计栏在 y 130 |
| `glorp_after_left.png` / `glorp_after_hud.png` / `glorp_after_hover.png` | GlorpUI + 本行 + 兼容补丁：统计栏与切换签整体顺延到 y 166 |
| `glorp_after_bar_hidden_left.png` | GlorpUI 统计栏关闭：只剩切换签，紧贴本行下方 |
| `glorp_wrong_load_order_left.png` | 失败形态：SOL 先于 GlorpUI 加载，补丁不生效 |
| `row_states.png` | 六种数据状态（中/增长、高/大增长、低/大降低、第 2 名、排行未出、待结算），均在 GlorpUI 场景下 |
| `*_tree.txt` | 布局坐标树 |

渲染器报告：所有场景 0 个未解析的原型绑定、0 张缺失贴图。

## 4. 待实机确认

1. scripted widget 的 `layer = bottom` 与 GlorpUI `left_panel`（同层）之间的绘制顺序；GlorpUI 统计栏收起的
   0.2 秒动画会从本行下方滑过。
2. `hide_ui` / `show_ui` 状态是否广播到 scripted widget（原版左面板通过同一模板响应）。
3. 加载顺序：类型重定义“后加载者生效”在 GUI 系统中的实际规则（证据级别：推，基于 GlorpUI 自身做法）；
   发布说明需要写明 SOL 排在 GlorpUI 之后。
4. GlorpUI 自身的统计栏只有 450 宽，第 5 列在原版 GlorpUI 中就被截断（`glorp_before_left.png` 同样如此），不是本补丁造成的。
5. 高 UI 缩放下行内文字宽度（当前固定列宽，最长的“排行待更新”占 120）。

# 游戏内 HUD 离线预览

2026-10-16；1920×1080；UI 100%；简体中文；src/stable 覆盖安装游戏的原版 GUI。

`hud.png` 是完整画布，`hud_top_detail.png` 是顶部 300 像素裁切。采用虚构的匈牙利示例数据、暂停状态、关闭左右详情面板、折叠地图菜单和两支示例军队。不是存档还原或游戏截图。

组装原版 `ingame_topbar`、`outliner`、`message_log` 三个根。右侧总览原本由引擎代码注入，预览使用原版 `unit_army_category_entry` 和 `army_unit_entry` 填入示例条目。警报及消息为空。

HUD 场景与大写 Types 解析修复已迁入 eu5-modding-base。本项目只保留预览产物；共享入口输出 hud_report.json 诊断报告。

限制：中央 3D 地图以纯色背景代替；动态国旗、人物肖像不支持；部分资源绑定仍未解析，详见 `hud_report.json`。日期字号、人物框和原生组件布局尚无对应实机截图校准，本图不能作为像素级一致性或真实数据正确性的证明。`hud_tree.txt` 保留布局坐标。

复现（PowerShell，项目根目录）：

```powershell
$env:PYTHONUTF8='1'
& C:/Users/Hades/anaconda3/envs/eu5/python.exe .eu5-base/ai_gui_assessment/renderer/run.py --workspace . --mod-root src/stable --scenario hud --output-root ai_gui_assessment/images/player_hud_20261016 --output hud.png
```

已复核 PROJECT_OVERVIEW；本次仅新增离线预览工具及产物，没有游戏功能变更，不更新概览。

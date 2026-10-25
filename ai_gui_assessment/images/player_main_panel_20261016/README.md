# 玩家主面板离线预览

日期：2026-10-16。目标：`src/stable` 的 SOL 生活水平国家情势面板。

- `r1_situation_panel.png`：1920×1080、UI 100% 对应的 570×950 侧栏视口，滚动位置为顶部。
- `r1_situation_panel_full.png`：570×1215 展开图，仅供完整内容审阅，不是玩家实际视口高度。
- `r1_tree.txt`：首屏元素树，包含布局坐标。

GUI 来自当前源文件，字体、贴图和中文本地化来自安装的游戏及模组。数值、商品供货和替代状态使用 `renderer/scenarios.py` 的示例数据，不读取存档。

渲染成功；唯一未解析表达式为 `GetSituationIllustration(SituationView.GetActiveSituation.GetSituation)`（首屏和展开图各出现一次）。顶部插画留空，不能据此认定游戏内也会缺图。

可见检查：余额文字和商品卡片可读；完整商品区需要滚动，首屏滚动区为 540×585。部族示例为 0/0，显示“无消费”，但其游标落在轨道左端，与 GUI 说明中“无消费应为中性条”的约定不一致，尚未修改。离线结果不验证真实存档计算、交互或游戏引擎表现。

复现命令（PowerShell）：

```powershell
$env:EU5_PYTHON='C:/Users/Hades/anaconda3/envs/eu5/python.exe'
$env:PYTHONUTF8='1'
$env:EU5_RENDER_LANGUAGE='simp_chinese'
$env:EU5_RENDER_OUTPUT_ROOT=(Join-Path (Get-Location) 'ai_gui_assessment/images/player_main_panel_20261016')
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py situation
```

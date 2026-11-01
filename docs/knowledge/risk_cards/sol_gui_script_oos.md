# SOL GUI 执行脚本与联机 OOS

证据日期：2026-11-01。适用范围：SOL 的 GUI → scripted GUI → 游戏状态写入链，以及从旧 CMF 复制的启动／读档回调。

## 已确认的风险

**用户已通过实机排查明确确认：GUI 执行 script 是本次 SOL 联机 OOS 的原因。该结论不是待验证的猜测。**

禁止继续通过 `GetScriptedGui(...).Execute(...)` 从 GUI 生命周期回调发起初始化、迁移、经济求解或其他游戏状态写入。`trigger_on_create`、`_show`、零尺寸 widget、`visible`、主机判断和脚本幂等性都不能作为该路径已安全的证明；改用 CMF 同源的 GUI 桥接也不构成替代。现有显示读取、原生游戏动作和纯界面操作不等于这条已确认的问题链，不要据此删除显示功能。

确认来源是本次用户的实机结论；没有为此记录编造复现步骤、调用次数或宿主／客户端日志。OOS 日志格式是否正确与 GUI 执行脚本的因果结论分开记录。

## 三个旧回调的分工

| 旧入口 | 真正职责与状态写入 | 原生替代评估 |
| --- | --- | --- |
| `sol_after_lobby_caller` | 在首次 GUI 调用时设置 `sol_game_started_after_lobby`；用 `current_year <= 1337` 猜新局，设置 `sol_is_new_game` 和 `SOL_migration_v3_seen`。它不是经济初始化器，也不是可靠的每次读档检测器。 | 新局直接由原生 `on_game_start` 写入迁移版本标记，无需选国或年份猜测。旧档缺少新标记时由同步脉冲检查。 |
| `sol_load_after_lobby_caller` | 检查上述标记，调用 `SOL_migration_fire_event` 向所有人类国家发提示，并移除 `sol_is_new_game`。全局 `SOL_migration_v3_seen` 防止重复；原实现还有回调先后导致晚一次读档提示的分支。 | 原生 `monthly_country_pulse` 可对未标记的人类国家执行一次迁移检查，再复用全局通知职责。必须先设置全局去重标记，再向所有人类国家派发；延迟到脉冲，不是读档即时通知。 |
| `sol_gls_init_caller` | 新局／读档时调用 `gls_init_after_lobby` → `gls_recalculate_global_living_standard`，刷新市场、国家求解、地点修正、面板和世界排名。 | 新局重算放在原生 `on_game_started_after_lobby`；读档沿用存档缓存及原生月度／年度更新，缺失或版本过期的缓存可在同步脉冲中补齐。没有已核实的原生每次读档即时入口。 |

两个迁移回调只在 stable 中；经济回调原来同时存在于 stable 和 standalone。三者不应继续作为一个笼统的“after-lobby”机制处理。

## 原生钩子的证据与边界

- `.eu5-base/reference_official_defines/docs/on_actions.log:653`、`:743` 将 `on_game_start` 和 `on_game_started_after_lobby` 列为 `From Code: Yes`，作用域均为 `none/any`。
- 原版 `.eu5-base/reference_game_files/game/in_game/common/on_action/_hardcoded.txt:1,316` 声明这两个钩子；2026-11-01 也读取了本机安装目录下同一文件，确认存在。
- CMF 参考 `3692202776/in_game/common/on_action/cmf_on_actions.txt:53,175-177` 说明前者在大厅展示前执行，后者在新局选国完成后执行一次。这是生命周期说明的来源，不是对每次读档的原生保证。
- 官方钩子清单中没有 `on_game_load` 或 `on_game_load_after_lobby`；CMF 的同名扩展由 `common/scripted_guis/cmf_after_lobby_caller_scripted_gui.txt:18,38` 显式派发。不能把它们误认作引擎读档钩子，或用它们绕回已禁止的 GUI 执行路径。
- 原生 `monthly_country_pulse` 在官方清单 `on_actions.log:857` 标记为 `From Code: Yes`、country 作用域。它是运行中的同步更新入口，不是在暂停状态下的读档通知。

因此，可以替代所需的初始化、一次性迁移与周期更新职责，不能声称完整保留“每次读档后立即重算”的原语义。若未来引擎新增读档钩子，必须重新核验当前版本的 `From Code`、作用域与触发时机。

## 已实现的职责分配（2026-11-02）

1. `on_game_start`：stable 通过 `sol_migration_stamp_new_game` 为新存档直接写入 `SOL_migration_<YYMMDD>_seen`；保留已有设置默认值、年龄事件等独立职责。不再按游戏年份识别新局。
2. `on_game_started_after_lobby`：stable 与 standalone 各进行一次新局经济初始化；重算依赖人类／AI 分类和设置，不能用大厅前的 `on_game_start` 假装等价替代。相对 CMF 设置注册的确切执行顺序仍需实机核验。
3. 原生国家月度脉冲：stable 通过 `sol_migration_check_monthly` 检查尚未迁移的旧存档，只有人类国家可启动通知。`SOL_migration_fire_event` 再检查标记、先写标记，再一次性通知所有人类；不依赖 `sol_game_started_after_lobby` 或 `sol_is_new_game`。同一存档中所有人类共用全局去重标记，未来加入的玩家不自动获得第二次提示，这沿用原设计。
4. 普通读档：保留已有缓存；通过原有月度／年度调度及现有缺失缓存兜底更新。没有新增每次读档重算或缓存版本系统。未来若需要版本修复，应在同步脉冲中处理，且持久化版本标记不能检测每次会话重载。
5. 排名与面板：经济求解完成不等于世界排名已更新。现有排名常规入口在一月，已有面板汇总也不是每月重建；若新增缺失／过期缓存修复，必须明确补齐相关汇总和排名，不能假设月度求解自动完成整条全局链。

旧存档可能已有或没有旧标记。不能仅从年份或缺少新变量准确还原它是否刚开局；新标记由真正的新局钩子写入，旧存档在首次安全脉冲迁移即可。

## 当前代码状态与验收

2026-11-02：三个旧回调的 widget、scripted_widgets 注册和 scripted GUI 定义已全部删除；两目标的世界经济重算接入原生 `on_game_started_after_lobby`。stable 新局写入当前发布日期的迁移标记，缺少该日期标记的旧档在首个人类国家月度脉冲通知所有人类，同一发布日期不重复。旧 GUI 标记和 `SOL_migration_v3_seen` 仍可留在存档中，但不再参与判断。

按用户 2026-11-02 的要求，标记与 metadata 共用 `YYMMDD` 日期，例如 `SOL_migration_261102_seen`。`scripts/update_mod_version.py` 在选中 stable 或 all 时，用同一个日期同步更新 metadata 和迁移脚本内全部标记读写；`build.bat` 经 `gen_sol_chain.py` 自动调用该脚本。默认取本机日期，`--date YYYY-MM-DD` 可指定日期，`--check` 检查且不写入。同一日期重复构建不重新通知；日期更新后，旧档会收到该日期版本的一次提示，旧日期或 v3 标记不能跳过它。这里只标记通知，不触发额外的读档经济重算。

`scripts/test_sol_economy_cadence.py` 离线执行真实生命周期入口，覆盖大厅前不重算、选国后重算、SOL 开关、新局无迁移提示、AI 不消费提示、全体人类一次通知、旧标记不干扰、读档保留去重标记和旧 GUI 引用清除。联机新局、暂停读档和继续运行后的脉冲仍需实机验收；离线检查不证明运行时同步。

stable 仍依赖 CMF；若依赖本身继续使用 GUI scripted-GUI 桥接，仅清除 SOL 的三个入口不能证明整个模组组合已无这类路径。需分别审计依赖版本，不能宣称整个组合 OOS 已修复。

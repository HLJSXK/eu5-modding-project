# 动态任务 — 任务目录

每条记录均为规格行，每个字段与代码元素一一对应。
使用方式：将本文档与源文件并排对照，逐行确认实现值与设计值一致。

---

## develop_city

| 字段 | 设计值 | 代码位置 |
|---|---|---|
| 任务变量 | `dm_mission_develop_city` | `scripted_effects` → `dm_start_mission_develop_city` |
| 启动触发器 | `can_start_develop_city_mission` | `scripted_triggers/dynamic_missions_triggers.txt` |
| 触发条件 | 首都为城镇/城市等级；首都繁荣度 < 100；国库 >= 300 | 同上 |
| 时限 | 60 个月 | `dm_start_mission_develop_city` → `dm_time_limit = 60` |
| 目标变量 | `dm_target_location` = 首都 | 事件 `dynamic_missions.1` option_a |
| 完成条件 | `var:dm_target_location prosperity >= 100` | `situations` → `on_monthly` Mission 1 分支 |
| 成功事件 | `dynamic_missions.3` | `events/dynamic_missions_events.txt` |
| 成功效果 | `add_prestige = 5` | 事件 3 option_a |
| 失败事件 | `dynamic_missions.4` | 同上 |
| 失败效果 | 无 | 事件 4 option_a |
| 放弃效果 | 无 | `dynamic_missions.60` 确认选项（无匹配分支） |
| 展示变量 | 仅 `dm_time_limit`（无进度/目标/繁荣度变量） | `dm_start_mission_develop_city` |
| 是否有行动 | 否 | `dm_has_actions` 未设置 |
| 开发状态 | 已实现 | — |

---

## large_research

| 字段 | 设计值 | 代码位置 |
|---|---|---|
| 任务变量 | `dm_mission_large_research` | `scripted_effects` → `dm_start_mission_large_research` |
| 启动触发器 | `can_start_large_research_project` | `scripted_triggers/dynamic_missions_triggers.txt` |
| 触发条件 | 拥有附庸国或邻国 | 同上 |
| 时限 | 60 个月 | `dm_start_mission_large_research` → `dm_time_limit = 60` |
| 目标变量 | 无 | 启动效果中移除 `dm_target_location` |
| 完成条件 | `dm_primary_progress >= 100` | `situations` → `on_monthly` Mission 2 分支 |
| 基础进度速率 | +1 / 月 | `on_monthly` → `change_variable dm_primary_progress add = 1` |
| 增援进度速率 | 额外 +2 / 月 | `on_monthly` → `has_country_modifier dm_increased_funding_modifier` 分支 |
| 成功事件 | `dynamic_missions.23` | `events/dynamic_missions_events.txt` |
| 成功效果 | `add_prestige = 10` | 事件 23 option_a |
| 失败事件 | `dynamic_missions.24` | 同上 |
| 失败效果 | `add_prestige = -5` | 事件 24 option_a |
| 放弃效果 | `add_prestige = -5` | `dynamic_missions.60` → `if has_variable dm_mission_large_research` 分支 |
| 展示变量 | `dm_primary_progress`、`dm_primary_goal = 100`、`dm_time_limit` | `dm_start_mission_large_research` |
| 是否有行动 | 是 — 切换式 | `dm_has_actions`、`dm_has_toggle_action` 已设置 |
| 开发状态 | 已实现 | — |

---

## promote_urbanization

| 字段 | 设计值 | 代码位置 |
|---|---|---|
| 任务变量 | `dm_mission_promote_urbanization` | `scripted_effects` → `dm_start_mission_promote_urbanization` |
| 启动触发器 | `can_start_promote_urbanization_mission` | `scripted_triggers/dynamic_missions_triggers.txt` |
| 触发条件 | 首都尚未达到城市等级；国库 >= 200 | 同上 |
| 时限 | 120 个月 | `dm_start_mission_promote_urbanization` → `dm_time_limit = 120` |
| 目标变量 | `dm_target_location` = 首都 | 事件 `dynamic_missions.1` option_d |
| 完成条件 | `capital prosperity >= 75` | `situations` → `on_monthly` Mission 3 分支 |
| 启动时效果 | 对目标地点施加 `dm_migration_boost` | `dm_start_mission_promote_urbanization` |
| 成功事件 | `dynamic_missions.33` | `events/dynamic_missions_events.txt` |
| 成功效果 | 首都等级晋升（rural→town→city）；`dm_urbanization_legacy` 修正 20 年 | 事件 33 option_a |
| 失败事件 | `dynamic_missions.34` | 同上 |
| 失败效果 | 无 | 事件 34 option_a |
| 放弃效果 | 无 | `dynamic_missions.60` 确认选项（无匹配分支） |
| 展示变量 | `dm_prosperity_target = 75`、`dm_time_limit` | `dm_start_mission_promote_urbanization` |
| 是否有行动 | 是 — 切换式 | `dm_has_actions`、`dm_has_toggle_action` 已设置 |
| 开发状态 | 已实现 | — |

---

## claim_province

| 字段 | 设计值 | 代码位置 |
|---|---|---|
| 任务变量 | `dm_mission_claim_province` | `scripted_effects` → `dm_start_mission_claim_province` |
| 启动触发器 | `can_start_claim_province_mission` | `scripted_triggers/dynamic_missions_triggers.txt` |
| 触发条件 | 拥有邻国；国库 >= 200；威望 >= 10 | 同上 |
| 时限 | 60 个月 | `dm_start_mission_claim_province` → `dm_time_limit = 60` |
| 目标变量 | `dm_target_location` = 随机邻国首都 | 事件 `dynamic_missions.41` immediate 块 |
| 启动流程 | 事件 1 option_e → 事件 40 → 事件 41 → `dm_start_mission_claim_province` | `events/dynamic_missions_events.txt` |
| 完成条件 | `var:dm_target_location owner = prev` | `situations` → `on_monthly` Mission 4 分支 |
| 启动时修正 | `dm_claim_province_active` 国家修正（无限期） | 事件 41 option_province |
| 成功事件 | `dynamic_missions.50` | `events/dynamic_missions_events.txt` |
| 成功效果 | `add_prestige = 10` | 事件 50 option_a |
| 失败事件 | `dynamic_missions.51` | 同上 |
| 失败效果 | `add_prestige = -10` | 事件 51 option_a |
| 放弃效果 | `add_prestige = -10` | `dynamic_missions.60` → `else_if has_variable dm_mission_claim_province` 分支 |
| 展示变量 | 仅 `dm_time_limit` | `dm_start_mission_claim_province` |
| 是否有行动 | 是 — 单次触发（带冷却） | `dm_has_actions`、`dm_has_oneshot_action` 已设置 |
| 开发状态 | 已实现 | — |

---

## 新增任务检查清单

- [ ] `can_start_{id}_mission` 触发器 → `scripted_triggers/dynamic_missions_triggers.txt`
- [ ] `dm_start_mission_{id}` 效果 → `scripted_effects/dynamic_missions_scripted_effects.txt`
  - [ ] 设置 `dm_active_mission`、`dm_mission_{id}`、`dm_months_elapsed = 0`、`dm_time_limit`
  - [ ] 按需设置展示变量：`dm_primary_progress/goal`、`dm_prosperity_target`
  - [ ] 按需设置 `dm_has_actions` / `dm_has_toggle_action` / `dm_has_oneshot_action`
- [ ] 成功事件 + 失败事件 → `events/dynamic_missions_events.txt`
  - [ ] 两者均调用 `dm_clear_all_mission_state`，并在 30 天后重新触发 `dynamic_missions.1`
- [ ] 放弃分支 → `dynamic_missions.60` 确认选项（若有惩罚）
- [ ] `else_if` 分支 → `situations/dynamic_missions_situations.txt` `on_monthly`
- [ ] 面板标题副标题行 → `dynamic_missions_situation.gui` header 块
- [ ] 每个卡片（A/B/C）各添加一条 `text_multi` → `dynamic_missions_situation.gui`
- [ ] 本地化键：`DM_{ID}_NAME`、`DM_{ID}_OVERVIEW`、`DM_{ID}_OBJECTIVES`、`DM_{ID}_REWARDS` → `_l_english.yml` 与 `_l_simp_chinese.yml`
- [ ] 本目录新增对应任务条目，所有字段填写完整

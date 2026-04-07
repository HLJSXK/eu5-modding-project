# 动态任务 — 行动目录

每条记录均为规格行，每个字段与代码元素一一对应。
使用方式：将本文档与源文件并排对照，逐行确认实现值与设计值一致。

行动形式说明：
- **切换式** — 开/关状态，激活时施加修正，关闭时移除
- **单次触发（带冷却）** — 可重复使用，但受冷却修正限制
- **单次触发（无冷却）** — 可自由重复使用
- **一次性** — 仅触发一次，不可重复

---

## dm_increase_research_funding_decision

| 字段 | 设计值 | 代码位置 |
|---|---|---|
| 所属任务 | `dm_mission_large_research` | `dynamic_missions_situation.gui` Card 4 可见性条件 |
| 行动形式 | 切换式 | `dm_start_mission_large_research` 中设置 `dm_has_toggle_action` |
| SGUI 处理器 | `dm_toggle_action_sgui` | `scripted_guis/dynamic_missions_sgui.txt` |
| 显示条件 | `dm_has_toggle_action` 已设置 | `dm_toggle_action_sgui` → `is_shown` |
| 开启时 — 国家修正 | `dm_increased_funding_modifier`（无限期，extend-mode） | `dm_toggle_action_sgui` 开启分支 |
| 关闭时 — 移除 | `dm_increased_funding_modifier` | `dm_toggle_action_sgui` 关闭分支 |
| 每月效果 | `dm_primary_progress +2`（当 `has_country_modifier dm_increased_funding_modifier` 时） | `situations` `on_monthly` Mission 2 经费分支 |
| 国家修正效果 | `court_spending_cost +0.05`、`monthly_innovativeness +0.10` | `static_modifiers/dynamic_missions_modifiers.txt` |
| 任务结束时清理 | 有条件移除，在 `dm_clear_mission_modifiers` 中 | `scripted_effects/dynamic_missions_scripted_effects.txt` |
| 开发状态 | 已实现 | — |

---

## dm_invest_urbanization_decision

| 字段 | 设计值 | 代码位置 |
|---|---|---|
| 所属任务 | `dm_mission_promote_urbanization` | `dynamic_missions_situation.gui` Card 4 可见性条件 |
| 行动形式 | 切换式 | `dm_start_mission_promote_urbanization` 中设置 `dm_has_toggle_action` |
| SGUI 处理器 | `dm_toggle_action_sgui` | `scripted_guis/dynamic_missions_sgui.txt` |
| 显示条件 | `dm_has_toggle_action` 已设置 | `dm_toggle_action_sgui` → `is_shown` |
| 开启时 — 国家修正 | `dm_urbanization_investment_active`（无限期，extend-mode） | `dm_toggle_action_sgui` 开启分支 |
| 开启时 — 地点修正 | `dm_urbanization_investment_bonus` 施加于 `dm_target_location`（无限期，extend-mode） | 同上，需 `has_variable dm_target_location` |
| 关闭时 — 移除 | 以上两个修正均移除 | `dm_toggle_action_sgui` 关闭分支 |
| 国家修正效果 | `court_spending_cost -0.08` | `static_modifiers/dynamic_missions_modifiers.txt` |
| 地点修正效果 | `prosperity_change +0.006 / 月`、`development_growth +0.003 / 月` | 同上 |
| 任务结束时清理 | 有条件移除，在 `dm_clear_mission_modifiers` 中 | `scripted_effects/dynamic_missions_scripted_effects.txt` |
| 开发状态 | 已实现 | — |

---

## dm_claim_border_reconnaissance_decision

| 字段 | 设计值 | 代码位置 |
|---|---|---|
| 所属任务 | `dm_mission_claim_province` | `dynamic_missions_situation.gui` Card 4 可见性条件 |
| 行动形式 | 单次触发（带冷却） | `dm_start_mission_claim_province` 中设置 `dm_has_oneshot_action` |
| SGUI 处理器 | `dm_oneshot_action_sgui` | `scripted_guis/dynamic_missions_sgui.txt` |
| 显示条件 | `dm_has_oneshot_action` 已设置 | `dm_oneshot_action_sgui` → `is_shown` |
| 启用条件 | `NOT has_country_modifier dm_border_reconnaissance_cooldown` 且 `manpower >= 200` | `dm_oneshot_action_sgui` → `is_valid` |
| GUI 启用表达式 | `Not(Player.HasModifier('dm_border_reconnaissance_cooldown'))` | Card 4 `blockoverride "button_enabled"` |
| 消耗 | `add_manpower = -200` | `dm_oneshot_action_sgui` effect 块 |
| 奖励 | `add_army_tradition = 5` | 同上 |
| 冷却修正 | `dm_border_reconnaissance_cooldown` — 1 年，extend-mode | 同上 |
| 冷却修正效果 | 仅作展示，无实际数值效果 | `static_modifiers/dynamic_missions_modifiers.txt` |
| 开发状态 | 已实现 | — |

---

## 新增切换式行动检查清单

- [ ] `dm_has_actions = 1` 及 `set_variable = dm_has_toggle_action` → `dm_start_mission_{id}`
- [ ] 开启 `else_if` 分支（施加修正）→ `dm_toggle_action_sgui`
- [ ] 关闭 `else_if` 分支（移除修正）→ `dm_toggle_action_sgui`
- [ ] `dm_toggle_off_button` + `dm_toggle_on_button` 对 → `dynamic_missions_situation.gui` Card 4，可见性条件绑定 `dm_mission_{key}` + `dm_action_toggle_on`
- [ ] 有条件的 `remove_country_modifier`（或 `remove_location_modifier`）→ `dm_clear_mission_modifiers`
- [ ] 静态修正 → `static_modifiers/dynamic_missions_modifiers.txt`
- [ ] 本地化键：决议名称 + 描述 → `_l_english.yml` 与 `_l_simp_chinese.yml`
- [ ] 本目录新增对应行动条目，所有字段填写完整

## 新增单次触发（带冷却）行动检查清单

- [ ] `dm_has_actions = 1` 及 `set_variable = dm_has_oneshot_action` → `dm_start_mission_{id}`
- [ ] 效果 `else_if` 分支（消耗、奖励、冷却修正）→ `dm_oneshot_action_sgui`
- [ ] 扩展 `is_valid` → `dm_oneshot_action_sgui`（若存在多个单次触发任务，使用 `OR { AND { ... } AND { ... } }` 模式）
- [ ] `dm_oneshot_action_button` → `dynamic_missions_situation.gui` Card 4，可见性条件绑定 `dm_mission_{key}`；`blockoverride "button_enabled"` 检查 `Not(Player.HasModifier(冷却键))`
- [ ] 冷却静态修正 → `static_modifiers/dynamic_missions_modifiers.txt`
- [ ] 本地化键：按钮文本键 + tooltip 键（消耗/奖励用纯文本）→ `_l_english.yml` 与 `_l_simp_chinese.yml`
- [ ] 本目录新增对应行动条目，所有字段填写完整

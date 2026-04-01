# Dynamic Missions GUI Architecture: Scalable Panel Design

**Author:** Claude
**Date:** 2026-03-30
**Branch:** dynamic-missions

---

## 1. Problem Statement

The current GUI panel (`dynamic_missions_situation.gui`) uses **one full card group per mission**: each mission has its own description card, progress card, and actions card written as separate `situation_card_common` blocks gated by `visible = "[dm_mission_X.IsSet]"`.

With 4 current missions this is manageable. But:

- 10–20 generic missions + an open-ended set of special (tag-specific) missions = O(N) GUI code growth
- Each new mission requires writing 3 full card blocks (~50 lines each) in the GUI file
- Any layout change must be replicated N times

**Goal:** Redesign the panel so that adding a new mission requires only:
1. Standard variable assignments in scripted effects
2. 2–3 localization keys
3. 3 single-line text selectors in the GUI

---

## 2. Jomini GUI Constraints

These constraints are non-negotiable and shape the entire architecture:

| Constraint | Implication |
|---|---|
| No loops or iteration | Cannot auto-generate cards from a list |
| Text keys are literal strings | Cannot select a localization key dynamically based on a variable value |
| Visibility only via `.IsSet` or scripted conditions | Each text block needs its own `visible = "[...]"` guard |
| Variable reads via `.GetValue\|default` | Numeric variables can be displayed inline |
| `Player.MakeScope` required | All state reads must be scoped to the current player (MP-safe) |

The core technique that makes the design work: **a shared fixed card structure with per-mission single-line text selectors inside**. Instead of one full card block per mission, we have one card block with N short `visible`-gated text lines inside it.

---

## 3. Proposed Architecture

### 3.1 Standard Mission Variable Schema

Every mission **MUST** set the following variables at start (in its `dm_start_mission_X` scripted effect):

| Variable | Type | Description | Always set? |
|---|---|---|---|
| `dm_active_mission` | boolean | Any mission currently active | Yes |
| `dm_mission_{key}` | boolean | This specific mission is active | Yes |
| `dm_months_elapsed` | int (start: 0) | Elapsed months counter | Yes |
| `dm_time_limit` | int | Mission time limit in months | Yes |
| `dm_primary_progress` | int (optional) | Tracked progress value (e.g. research) | Missions with a numeric goal |
| `dm_primary_goal` | int (optional) | Target value for primary_progress | When primary_progress is set |
| `dm_prosperity_target` | int (optional) | Prosperity threshold for display | Prosperity-based missions |

`dm_time_limit` is the key addition. Currently the GUI hardcodes `"60"` or `"120"` per mission block. By reading `[Player.MakeScope.GetVariable('dm_time_limit').GetValue|0]`, the progress card becomes **universal** — it reads the correct limit for whatever mission is active, with no per-mission branching in the GUI.

### 3.2 GUI Template Structure

The panel has three fixed sections. Only the text selectors inside each section grow with new missions.

#### Section A: Header subtitle (`situation_header_left`)

```
# One text_single per mission — shows mission name in header
text_single { text = "DM_DEVELOP_NAME"   visible = "[...dm_mission_develop_city.IsSet]" }
text_single { text = "DM_RESEARCH_NAME"  visible = "[...dm_mission_large_research.IsSet]" }
text_single { text = "DM_URBANIZE_NAME"  visible = "[...dm_mission_promote_urbanization.IsSet]" }
text_single { text = "DM_CLAIM_NAME"     visible = "[...dm_mission_claim_province.IsSet]" }
# + 1 line per new mission
```

#### Section B: Description card (`situation_panel_main_content`)

**ONE** `situation_card_common` block, visible when `dm_active_mission.IsSet`:

```
situation_card_common {
    visible = "[dm_active_mission.IsSet]"
    blockoverride "common_header_text" {
        # mission name — same selectors as header
    }
    blockoverride "common_bottom_content" {
        # One text_multi per mission
        text_multi { text = "DM_DEVELOP_HINT"   visible = "[...dm_mission_develop_city.IsSet]" }
        text_multi { text = "DM_RESEARCH_HINT"  visible = "[...dm_mission_large_research.IsSet]" }
        # + 1 line per new mission
    }
}
```

#### Section C: Universal progress card

**ONE** `situation_card_common` block that reads standard variables. No per-mission branching:

```
situation_card_common {
    visible = "[dm_active_mission.IsSet]"
    blockoverride "common_header_text" { text = "DM_PANEL_PROGRESS_TITLE" }
    blockoverride "common_bottom_content" {
        hbox {
            # Slot 1: Months elapsed — always shown
            widget { text = "[GetVariable('dm_months_elapsed').GetValue|0]" label = "DM_PANEL_MONTHS_ELAPSED" }
            # Slot 2: Time limit — always shown (reads dm_time_limit variable)
            widget { text = "[GetVariable('dm_time_limit').GetValue|0]" label = "DM_PANEL_TIME_LIMIT" }
            # Slot 3: Primary progress — shown only when dm_primary_progress is set
            widget {
                visible = "[GetVariable('dm_primary_progress').IsSet]"
                text = "[GetVariable('dm_primary_progress').GetValue|0]" label = "DM_PANEL_PROGRESS_LABEL"
            }
            # Slot 4: Primary goal — shown only when dm_primary_goal is set
            widget {
                visible = "[GetVariable('dm_primary_goal').IsSet]"
                text = "[GetVariable('dm_primary_goal').GetValue|0]" label = "DM_PANEL_GOAL_LABEL"
            }
            # Slot 5: Prosperity target — shown only when dm_prosperity_target is set
            widget {
                visible = "[GetVariable('dm_prosperity_target').IsSet]"
                text = "[GetVariable('dm_prosperity_target').GetValue|0]" label = "DM_PANEL_PROSPERITY_TARGET"
            }
        }
    }
}
```

#### Section D: Actions card

**ONE** `situation_card_common` block, visible only when the active mission has actions:

```
situation_card_common {
    visible = "[dm_active_mission.IsSet]"   # or gated per mission if some have no actions
    blockoverride "common_header_text" { text = "DM_PANEL_ACTIONS_TITLE" }
    blockoverride "common_bottom_content" {
        # One text_multi per mission that has decisions
        text_multi { text = "DM_DEVELOP_ACTION_HINT"   visible = "[...dm_mission_develop_city.IsSet]" }
        text_multi { text = "DM_RESEARCH_ACTION_HINT"  visible = "[...dm_mission_large_research.IsSet]" }
        # Missions with no decisions: no line needed (card shows nothing → can hide with condition)
        # + 1 line per new mission that has decisions
    }
}
```

---

## 4. Localization Key Naming Convention

### Generic Missions

Short uppercase identifier derived from the mission variable key:

| Mission variable | Short ID | Example keys |
|---|---|---|
| `dm_mission_develop_city` | `DEVELOP` | `DM_DEVELOP_NAME`, `DM_DEVELOP_HINT`, `DM_DEVELOP_ACTION_HINT` |
| `dm_mission_large_research` | `RESEARCH` | `DM_RESEARCH_NAME`, `DM_RESEARCH_HINT`, `DM_RESEARCH_ACTION_HINT` |
| `dm_mission_promote_urbanization` | `URBANIZE` | `DM_URBANIZE_NAME`, `DM_URBANIZE_HINT`, `DM_URBANIZE_ACTION_HINT` |
| `dm_mission_claim_province` | `CLAIM` | `DM_CLAIM_NAME`, `DM_CLAIM_HINT`, `DM_CLAIM_ACTION_HINT` |

### Special / Tag-Specific Missions

Prefix with `DM_S_` to separate them from generics:

```
DM_S_{TAG}_{KEY}   →   e.g.  DM_S_OTT_NAME  (Ottoman-specific mission)
                              DM_S_ENG_HINT
```

### Required Key Set Per Mission

| Key | Required | Description |
|---|---|---|
| `DM_{ID}_NAME` | Yes | Short mission name (panel header + subtitle) |
| `DM_{ID}_HINT` | Yes | Player-facing mission description for the panel |
| `DM_{ID}_ACTION_HINT` | If decisions exist | Formatted hint listing available decisions |

---

## 5. Migration Plan (Current → New Architecture)

The current 4 missions use `DM_PANEL_MX_NAME` / `DM_PANEL_MISSION_HINT_*` key names. These must be renamed to the new convention when the GUI is rewritten.

| Old key | New key |
|---|---|
| `DM_PANEL_M1_NAME` | `DM_DEVELOP_NAME` |
| `DM_PANEL_M2_NAME` | `DM_RESEARCH_NAME` |
| `DM_PANEL_M3_NAME` | `DM_URBANIZE_NAME` |
| `DM_PANEL_M4_NAME` | `DM_CLAIM_NAME` |
| `DM_PANEL_MISSION_HINT_DEVELOP` | `DM_DEVELOP_HINT` |
| `DM_PANEL_MISSION_HINT_RESEARCH` | `DM_RESEARCH_HINT` |
| `DM_PANEL_MISSION_HINT_ESTABLISH` | `DM_URBANIZE_HINT` |
| `DM_PANEL_MISSION_HINT_CLAIM` | `DM_CLAIM_HINT` |
| `DM_PANEL_ACTION_FUNDING_HINT` | `DM_RESEARCH_ACTION_HINT` |
| `DM_PANEL_ACTION_URBANIZATION_HINT` | `DM_URBANIZE_ACTION_HINT` |
| `DM_PANEL_ACTION_CLAIM_HINT` | `DM_CLAIM_ACTION_HINT` |

**New universal keys to add:**

| Key | Value |
|---|---|
| `DM_PANEL_PROGRESS_LABEL` | "Progress" / "进度" |
| `DM_PANEL_GOAL_LABEL` | "Goal" / "目标" |

(All existing `DM_PANEL_*` utility keys remain unchanged.)

Additionally, `dm_start_mission_X` effects must set `dm_time_limit` and (where applicable) `dm_primary_goal` and `dm_prosperity_target`.

---

## 6. Adding a New Mission: Checklist

Following this architecture, the GUI cost of a new mission is **3 lines** in the GUI file.

### Script files (same as always)
- [ ] Add `can_start_{mission}` in `scripted_triggers`
- [ ] Add `dm_start_mission_{key}` in `scripted_effects` — **must set `dm_time_limit`**; optionally set `dm_primary_goal`, `dm_prosperity_target`
- [ ] Update `dm_clear_mission_flags` and `dm_clear_mission_modifiers`
- [ ] Add situation tick block (success/failure conditions)
- [ ] Add events (success, failure, optional intro)
- [ ] Add decisions if needed
- [ ] Add option to `dynamic_missions.1` picker event

### Localization (2–3 keys per language)
- [ ] `DM_{ID}_NAME`
- [ ] `DM_{ID}_HINT`
- [ ] `DM_{ID}_ACTION_HINT` (if decisions exist)

### GUI (3 lines total in `dynamic_missions_situation.gui`)
- [ ] One `text_single` in the header subtitle selector
- [ ] One `text_multi` in the description card's body selector
- [ ] One `text_multi` in the actions card's body selector (if decisions exist)

---

## 7. Design Rationale: What We Are NOT Doing

| Rejected approach | Reason |
|---|---|
| Per-mission full card blocks (current) | O(N) GUI growth; each new mission ≈ 50 GUI lines |
| `dm_gui_mission_type` integer switching | Integer comparison in GUI is unreliable; `.IsSet` is the confirmed safe pattern |
| Generating action cards from `SituationView.GetActionGroups` | Only works for `generic_actions/` entries; DM uses `decisions/` which don't appear there |
| Separate GUI file per mission | No GUI file composition/include system in Jomini |

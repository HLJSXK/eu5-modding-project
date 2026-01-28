# Dynamic Mission Design: Large Research Project

**Author:** Manus AI
**Date:** Jan 28, 2026

## 1. Overview

This document outlines the design for the "Large Research Project" dynamic mission. This mission simulates a focused, long-term research endeavor, providing players with a new way to invest in and accelerate their technological progress.

## 2. Core Mechanics

- **Type:** Dynamic Situation
- **Name:** `large_research_project_situation`
- **Trigger:** Player is advancing in research and has neighboring or subject countries to collaborate with or compete against.
- **Participants:** Player, all subjects, and all neighboring countries.
- **Duration:** 5 years (60 months).
- **Goal:** Achieve 100% research progress.
- **Reward:** +20 research progress in a chosen technology category.

## 3. Situation Definition (`dynamic_missions_situations.txt`)

The `large_research_project_situation` will track the progress of the research project.

```pdx
large_research_project_situation = {
    monthly_spawn_chance = 0

    visible = {
        OR = {
            this = root.owner
            is_subject_of = root.owner
            is_neighbor_of = root.owner
        }
    }

    can_start = { always = no } # Manually triggered by event

    can_end = {
        OR = {
            # Success Condition
            AND = {
                has_variable = research_progress
                var:research_progress >= 100
                set_variable = { name = mission_success value = yes }
            },
            # Failure Condition
            AND = {
                has_variable = situation_start_date
                months_since_variable = { variable = situation_start_date months >= 60 }
                set_variable = { name = mission_failed value = yes }
            }
        }
    }

    on_start = {
        set_variable = { name = situation_start_date value = current_date }
        set_variable = { name = research_progress value = 0 }
        owner = {
            every_subject = { add_to_list = situation_participants }
            every_neighbor_country = { add_to_list = situation_participants }
        }
    }

    on_monthly = {
        # Base progress (can be 0)
        # Progress from 'Increase Research Funding'
        if = {
            limit = { has_country_modifier = dm_increased_funding_modifier }
            change_variable = { name = research_progress value = 1 }
        }
        # Progress from 'Conscript University'
        if = {
            limit = { has_variable = conscripted_universities_count }
            change_variable = { name = research_progress value = var:conscripted_universities_count }
        }
    }

    on_ending = {
        owner = {
            if = {
                limit = { situation:large_research_project_situation = { has_variable = mission_success } }
                trigger_event = { id = dynamic_missions.23 } # Success Event
            }
            else_if = {
                limit = { situation:large_research_project_situation = { has_variable = mission_failed } }
                trigger_event = { id = dynamic_missions.24 } # Failure Event
            }
        }
    }

    on_ended = {
        remove_variable = situation_start_date
        remove_variable = research_progress
        remove_variable = mission_success
        remove_variable = mission_failed
        remove_variable = conscripted_universities_count
        clear_list = situation_participants
        # Remove character modifiers
    }
}
```

## 4. Player Actions (`dynamic_missions_actions.txt`)

### 4.1. Increase Research Funding

This is a toggleable action, managed by a decision.

### 4.2. Conscript University

```pdx
dm_conscript_university = {
    potential = { has_active_situation = large_research_project_situation }
    allow = {
        NOT = { has_country_modifier = dm_conscript_university_cooldown }
        any_owned_location = { has_building = university }
    }
    effect = {
        # Event to select location
        trigger_event = { id = dynamic_missions.21 }
        add_country_modifier = { name = dm_conscript_university_cooldown duration = 365 hidden = yes }
    }
    ai_will_do = { base = 0 }
}
```

### 4.3. Appoint Lead Scientist

```pdx
dm_appoint_lead_scientist = {
    potential = { has_active_situation = large_research_project_situation }
    allow = { NOT = { has_variable = lead_scientist_appointed } }
    effect = {
        # Event to select character
        trigger_event = { id = dynamic_missions.22 }
    }
    ai_will_do = { base = 0 }
}
```

## 5. Modifiers (`dynamic_missions_modifiers.txt`)

```pdx
# Increase Research Funding
dm_increased_funding_modifier = {
    court_expenses_add = 5
    innovativeness_gain = 0.10
}

# Conscript University
dm_conscripted_university_debuff = {
    local_control = -0.05
    local_max_literacy = -0.05
    local_satisfaction = -0.10
}

# Appoint Lead Scientist
dm_lead_scientist_debuff = {
    unsuitable_for_council = yes
    unsuitable_as_general = yes
    unsuitable_as_admiral = yes
    life_expectancy = -10
}
```

## 6. Events (`dynamic_missions_events.txt`)

- **`dynamic_missions.20`**: Starts the "Large Research Project" situation.
- **`dynamic_missions.21`**: Player selects a university to conscript.
- **`dynamic_missions.22`**: Player selects a character to be the lead scientist.
- **`dynamic_missions.23`**: Success event, grants reward.
- **`dynamic_missions.24`**: Failure event.

## 7. Trigger (`dynamic_missions_triggers.txt`)

```pdx
can_start_large_research_project = {
    num_of_technologies > 10
    OR = {
        any_subject = { exists = yes }
        any_neighbor_country = { exists = yes }
    }
}
```

## 8. Localization (`dynamic_missions_l_english.yml`)

- Situation name and description.
- Action names, descriptions, and tooltips.
- Modifier names and descriptions.
- Event titles, descriptions, and option texts.

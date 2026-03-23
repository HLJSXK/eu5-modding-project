# Dynamic Missions Feature Design

**Author:** Manus AI
**Date:** Jan 22, 2026

## 1. Overview

This document outlines the design and architecture for the "Dynamic Missions" feature in the EU5 modding project. This feature introduces a system of player-driven goals, implemented as situations, to provide focused gameplay objectives and rewards.

## 2. File Structure

The feature will be implemented across several files, organized as follows:

```
/src/develop/
├── in_game/
│   ├── common/
│   │   ├── situations/`
│   │   │   └── dynamic_missions_situations.txt
│   │   └── generic_actions/
│   │       └── dynamic_missions_actions.txt
│   └── events/
│       └── dynamic_missions_start_event.txt
└── main_menu/
    └── localization/
        └── dynamic_missions_l_english.yml
```

## 3. Core Components

### 3.1. Start Event (`dynamic_missions_start_event.txt`)

This file will contain the initial event that allows the player to choose a goal. It will only be triggerable by a human player when no other dynamic mission is active.

**`dynamic_missions_start.1` (Choose a Goal):**
-   **Type:** Country Event
-   **Trigger:**
    -   Is human player
    -   Does not have any active dynamic mission situation
-   **Options:**
    -   **Option A: Develop a City:**
        -   Triggers the `develop_city_situation`
        -   Allows player to select a target city
    -   *(Future options for other goals will be added here)*

### 3.2. Situations (`dynamic_missions_situations.txt`)

This file will define the situations for each goal. The first situation will be for city development.

**`develop_city_situation`:**
-   **Participants:** Player and all subjects
-   **Duration:** 5 years (can end sooner if goal is met)
-   **End Conditions:**
    -   Target city reaches 100% prosperity
    -   At least 10 new buildings are constructed in the target city
    -   5 years have passed
-   **Progress Bars:**
    -   Left: Situation completion progress (based on prosperity and buildings)
    -   Right: Time remaining
-   **On Start:**
    -   Set the target city
    -   Add all subjects to the situation
-   **On Monthly:**
    -   Update progress bars
    -   Check for end conditions
-   **On End:**
    -   Grant reward: +1 development to the target city
    -   Trigger the `dynamic_missions_start.1` event again

### 3.3. Generic Actions (`dynamic_missions_actions.txt`)

This file will define the actions available to the player and other participants within the situations.

**Player Actions (for `develop_city_situation`):**
-   **`convene_builders`:**
    -   **Cooldown:** 1 year
    -   **Effect:** -50% global construction speed, +100% construction speed in target city for 1 year
-   **`public_works`:**
    -   **Cooldown:** 1 year
    -   **Effect:** Spend money to increase prosperity growth in target city by 1% for 1 year
-   **`demand_contributions`:**
    -   **Cooldown:** 1 year
    -   **Effect:** -10% control in all other cities, +100% control cap in target city for 1 year

**Participant Actions (for `develop_city_situation` - Subjects):**
-   **`steal_progress`:**
    -   **Cooldown:** 1 year
    -   **AI Trigger:** Disloyal subjects
    -   **Effect:** -1% prosperity in target city, +1% prosperity in subject's capital
-   **`contribute_to_development`:**
    -   **Cooldown:** 1 year
    -   **AI Trigger:** Loyal subjects
    -   **Effect:** +1% prosperity in target city, -1% prosperity in subject's capital

### 3.4. Localization (`dynamic_missions_l_english.yml`)

This file will contain all the English text for the feature, including event titles, descriptions, option names, situation names, action names, and tooltips.

## 4. GUI (Future Phase)

The progress bars and other custom UI elements will be implemented in a later phase using `.gui` files. The initial implementation will focus on the core logic and functionality.


## 5. New Dynamic Mission: Large Research Project

This document outlines the design for the "Large Research Project" dynamic mission. This mission simulates a focused, long-term research endeavor, providing players with a new way to invest in and accelerate their technological progress.

### 5.1. Core Mechanics

- **Type:** Dynamic Situation
- **Name:** `large_research_project_situation`
- **Trigger:** Player is advancing in research and has neighboring or subject countries to collaborate with or compete against.
- **Participants:** Player, all subjects, and all neighboring countries.
- **Duration:** 5 years (60 months).
- **Goal:** Achieve 100% research progress.
- **Reward:** +20 research progress in a chosen technology category.

### 5.2. Situation Definition (`dynamic_missions_situations.txt`)

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

### 5.3. Player Actions (`dynamic_missions_actions.txt`)

#### 5.3.1. Increase Research Funding

This is a toggleable action, managed by a decision.

#### 5.3.2. Conscript University

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

#### 5.3.3. Appoint Lead Scientist

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

### 5.4. Modifiers (`dynamic_missions_modifiers.txt`)

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

### 5.5. Events (`dynamic_missions_events.txt`)

- **`dynamic_missions.20`**: Starts the "Large Research Project" situation.
- **`dynamic_missions.21`**: Player selects a university to conscript.
- **`dynamic_missions.22`**: Player selects a character to be the lead scientist.
- **`dynamic_missions.23`**: Success event, grants reward.
- **`dynamic_missions.24`**: Failure event.

### 5.6. Trigger (`dynamic_missions_triggers.txt`)

```pdx
can_start_large_research_project = {
    num_of_technologies > 10
    OR = {
        any_subject = { exists = yes }
        any_neighbor_country = { exists = yes }
    }
}
```

### 5.7. Localization (`dynamic_missions_l_english.yml`)

- Situation name and description.
- Action names, descriptions, and tooltips.
- Modifier names and descriptions.
- Event titles, descriptions, and option texts.


## 6. New Dynamic Mission: Establish New City

This document outlines the design for the "Establish New City" dynamic mission. This mission simulates the long-term project of elevating a town to a city, offering a unique set of challenges and rewards focused on internal development.

### 6.1. Core Mechanics

- **Type:** Dynamic Situation
- **Name:** `establish_new_city_situation`
- **Trigger:** Player choice from the main dynamic mission event. Can only be started if the player owns at least one 'town' and has not successfully completed this mission before.
- **Participants:** Player only.
- **Duration:** 10 years (120 months).
- **Goal:** The target location's rank becomes 'city'.
- **Reward:** The target location receives a permanent modifier, **"[Country Name]'s Pearl"**, granting `+0.5%` monthly prosperity, `+0.005` monthly development, and `+1` migration attraction.

### 6.2. Player Actions

This mission introduces several strategic options, allowing the player to guide the city's development.

| Action | Type | Cost | Effects |
| :--- | :--- | :--- | :--- |
| **Encourage Migration** | Toggleable | +5% Court Expenses | +0.10 Freemen Value, +1 Migration Attraction, +50% Migration Speed in target location. |
| **Encourage Proselytization** | Toggleable | +5% Court Expenses | +0.10 Spiritual Value, +20 Monthly Conversion, +50% Conversion Speed in target location. |
| **Encourage Folk Culture** | Toggleable | +5% Court Expenses | +0.10 Humanist Value, +20 Monthly Assimilation, +50% Assimilation Speed in target location. |
| **Requisition Materials** | Toggleable | -5% All Estates' Satisfaction | +5% Taxation Cap. |
| **Appoint Regional Governor** | One-Time | -5 Legitimacy | Select a character to govern. Target location gains Control and Max Control equal to `(Character Skills / 10)%`. The character becomes unsuitable for other high-level positions and receives a `-10` life expectancy debuff for the mission's duration. |

### 6.3. Technical Implementation

- **Situation (`establish_new_city_situation`):** Manages the 10-year timeline and checks for the success condition (`location_rank = city`). It also handles the monthly application of value changes from the toggleable actions.
- **Decisions:** The five player actions are implemented as decisions, allowing the player to toggle them on or off at will (except for the one-time governor appointment).
- **Events:** A series of events (`dynamic_missions.30` to `dynamic_missions.34`) handle the mission start (town selection), governor appointment, and the final success/failure outcomes.
- **Modifiers:** A comprehensive set of country, location, and character modifiers are used to apply the various effects, costs, and rewards associated with the player's choices.
- **Trigger (`can_start_establish_new_city_mission`):** A new scripted trigger checks if the player is eligible to start the mission, ensuring they have a town and haven't completed the mission before.

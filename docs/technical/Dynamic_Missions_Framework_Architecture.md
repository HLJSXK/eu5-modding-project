# Dynamic Missions Framework Architecture

**Author:** Manus AI  
**Date:** Jan 22, 2026

This document describes the technical architecture of the Dynamic Missions system, specifically focusing on the mission pool management and selection mechanism.

## 1. System Overview

The Dynamic Missions framework operates on a **mission pool** paradigm. Rather than presenting a fixed set of choices to the player, the system maintains a large collection of potential missions, each with its own availability conditions. When the player becomes eligible for a new mission, the system evaluates all missions in the pool, filters them by their trigger conditions, and randomly selects four to present as options.

## 2. Core Components

### 2.1. Mission Pool

The mission pool is a conceptual collection of all possible Dynamic Missions. Each mission in the pool consists of:

*   **Unique Identifier**: A string key used to reference the mission (e.g., `develop_city`, `military_expansion`, `tech_breakthrough`).
*   **Trigger Conditions**: A scripted trigger that determines whether this mission is currently available to the player. These conditions can check for anything from owned territory types to diplomatic situations.
*   **Situation Definition**: The EU5 situation that tracks the mission's progress once activated.
*   **Associated Events**: Events for mission start, success, failure, and any intermediate checkpoints.
*   **Generic Actions**: Player and participant actions specific to this mission.
*   **Localization**: All text strings for the mission's name, description, and related UI elements.

### 2.2. Mission Selection Script

The mission selection process is managed by a central scripted effect, typically called within the main starting event's `immediate` block. The script performs the following steps:

1.  **Eligibility Check**: Verify that the player is eligible for a new mission (e.g., no active mission, is a human player, game has started).
2.  **Condition Evaluation**: Iterate through all missions in the pool and evaluate their trigger conditions.
3.  **Valid Mission List**: Build a list of missions that passed the condition check.
4.  **Random Selection**: If there are four or more valid missions, randomly select four. If there are fewer than four, present all available missions.
5.  **Variable Assignment**: Store the selected missions in temporary variables that the event options will reference.

### 2.3. Dynamic Event Options

The main starting event (`dynamic_missions.1`) uses the variables set by the selection script to dynamically generate its options. Each option:

*   Displays the name and description of one of the four selected missions (retrieved via localization keys stored in the variables).
*   Has a trigger condition that checks if the corresponding variable is set, ensuring the option only appears if that mission was selected.
*   Executes an effect that starts the chosen mission's situation and sets the `active_dynamic_mission` flag.

## 3. Example: Trigger Conditions

Each mission defines a `can_start_<mission_id>` scripted trigger. Here are examples for the three initial missions:

### 3.1. Develop City Mission

```
can_start_develop_city_mission = {
    # Player must own at least one city or town
    any_owned_location = {
        OR = {
            location_rank = town
            location_rank = city
        }
    }
}
```

### 3.2. Military Expansion Mission

```
can_start_military_expansion_mission = {
    # Player must have a rival
    any_rival_country = {
        exists = yes
        
        # Rival must own territory adjacent to the player
        any_owned_location = {
            any_neighbor_location = {
                owner = root
            }
        }
    }
}
```

### 3.3. Technological Breakthrough Mission

```
can_start_tech_breakthrough_mission = {
    # Player must not be the most technologically advanced nation
    NOT = {
        is_most_advanced_nation = yes
    }
    
    # There must be at least one unresearched technology in the next era
    has_unresearched_next_era_tech = yes
}
```

## 4. Scalability and Expansion

This architecture is designed to scale efficiently as more missions are added to the pool. Key advantages include:

*   **Modular Design**: Each mission is self-contained. Adding a new mission requires only creating its files and adding a single entry to the selection script.
*   **No Event Bloat**: The main starting event remains a single, manageable file regardless of the number of missions in the pool.
*   **Conditional Variety**: Players will naturally see different mission options based on their current game state, ensuring that the system remains relevant throughout a campaign.
*   **Easy Balancing**: Mission availability can be fine-tuned by adjusting trigger conditions without modifying the core selection logic.

## 5. Implementation Roadmap

To implement this framework, the following steps are required:

1.  **Create Scripted Triggers**: Define `can_start_<mission_id>` for each mission in `common/scripted_triggers/dynamic_missions_triggers.txt`.
2.  **Build Selection Script**: Create a scripted effect in `common/scripted_effects/dynamic_missions_selection.txt` that evaluates all triggers and populates the selection variables.
3.  **Modify Starting Event**: Update `dynamic_missions.1` to use the selection script in its `immediate` block and dynamically generate options based on the variables.
4.  **Add On-Action Hook**: Integrate the starting event into an appropriate `on_action` (e.g., `on_yearly_pulse` or a custom trigger) to periodically check if the player is eligible for a new mission.
5.  **Test and Iterate**: Ensure that the selection logic works correctly with various combinations of available missions and that the event options display properly.

## 6. Future Considerations

*   **Weighted Selection**: Instead of pure random selection, missions could have weights that influence their likelihood of being chosen, allowing for more common or rare mission types.
*   **Player Preferences**: A future enhancement could allow players to set preferences for certain mission types, adjusting the weights dynamically.
*   **Mission Cooldowns**: Implement a system where recently completed missions have a reduced chance of appearing again for a set period, ensuring greater variety.

# Dynamic Mission Design: Establish New City

**Author:** Manus AI  
**Date:** Jan 28, 2026  
**Task:** Third Dynamic Mission Implementation

## 1. Overview

The "Establish New City" mission is the third dynamic mission in the EU5 modding project. This mission simulates the process of transforming a town (集镇) into a full-fledged city, providing players with a long-term development goal that involves multiple strategic choices regarding migration, religion, culture, and governance.

## 2. Core Mechanics

### 2.1. Basic Information

- **Type:** Dynamic Situation
- **Name:** `establish_new_city_situation`
- **Trigger:** Player-initiated through the main dynamic missions event
- **Participants:** Player only (no subjects or neighbors)
- **Duration:** 10 years (120 months)
- **Goal:** Transform a selected town into a city
- **Success Condition:** Target location achieves city rank (`location_rank = city`)

### 2.2. Eligibility Requirements

The mission can be started if:
- Player owns at least one town (`location_rank = town`)
- Player has NOT completed this mission before (tracked via `has_completed_establish_city_mission` flag)
- Player does not have an active dynamic mission

### 2.3. Reward

Upon successful completion, the target location receives a permanent modifier:

**"[Country Name]'s Pearl" (「[国家名]的明珠」)**
- Monthly prosperity: +0.5%
- Monthly development: +0.005
- Migration attraction: +1

## 3. Player Actions

The mission provides five distinct player actions, each offering strategic choices with trade-offs.

### 3.1. Encourage Migration (鼓励移民)

**Type:** Toggleable action (can be turned on/off)

**Effects when active:**
- Court expenses: +5%
- Value shift towards Freemen: +0.10 per month
- Target location migration attraction: +1
- Target location migration speed: +50%

**Implementation:**
- Managed through a decision that adds/removes a country modifier
- Modifier also applies location-specific effects to the target city

### 3.2. Encourage Proselytization (鼓励宣教)

**Type:** Toggleable action (can be turned on/off)

**Effects when active:**
- Court expenses: +5%
- Value shift towards Spiritual: +0.10 per month
- Target location monthly conversion: +20
- Target location conversion speed: +50%

**Implementation:**
- Managed through a decision that adds/removes a country modifier
- Modifier also applies location-specific effects to the target city

### 3.3. Encourage Folk Culture (鼓励民俗)

**Type:** Toggleable action (can be turned on/off)

**Effects when active:**
- Court expenses: +5%
- Value shift towards Humanist: +0.10 per month
- Target location monthly assimilation: +20
- Target location assimilation speed: +50%

**Implementation:**
- Managed through a decision that adds/removes a country modifier
- Modifier also applies location-specific effects to the target city

### 3.4. Appoint Regional Governor (派遣地方总督)

**Type:** One-time action (can only be used once per mission)

**Requirements:**
- Have at least one character in court
- Not already used during this mission

**Effects:**
- Lose 5 legitimacy (or equivalent for other government types)
- Select a character from court
- Target location gains control and max control bonus equal to (character's total skill / 10)%
- Selected character receives debuffs:
  - Unsuitable for council
  - Unsuitable as general
  - Unsuitable as admiral
  - Life expectancy: -10 years (until mission ends)

**Implementation:**
- Triggered through a generic action
- Opens an event for character selection
- Character modifier is removed when mission ends

### 3.5. Requisition Development Materials (向民间征集发展物资)

**Type:** Toggleable action (can be turned on/off)

**Effects when active:**
- Estate satisfaction: -5% (all estates)
- Taxation cap: +5%

**Implementation:**
- Managed through a decision that adds/removes a country modifier

## 4. Technical Implementation Details

### 4.1. Situation Definition

The situation will be defined in `dynamic_missions_situations.txt` with the following structure:

```
establish_new_city_situation = {
    monthly_spawn_chance = 0
    
    visible = {
        this = root.owner
    }
    
    can_start = { always = no }
    
    can_end = {
        OR = {
            # Success: Target becomes a city
            AND = {
                var:target_location = {
                    location_rank = city
                }
                set_variable = { name = mission_success value = yes }
            }
            # Failure: 10 years elapsed
            AND = {
                has_variable = situation_start_date
                months_since_variable = { 
                    variable = situation_start_date 
                    months >= 120 
                }
                set_variable = { name = mission_failed value = yes }
            }
        }
    }
    
    on_start = {
        set_variable = { name = situation_start_date value = current_date }
        # Target location set by triggering event
    }
    
    on_monthly = {
        # Track progress towards city status
        # Update any dynamic modifiers
    }
    
    on_ending = {
        owner = {
            if = {
                limit = { 
                    situation:establish_new_city_situation = { 
                        has_variable = mission_success 
                    } 
                }
                trigger_event = { id = dynamic_missions.33 }
            }
            else_if = {
                limit = { 
                    situation:establish_new_city_situation = { 
                        has_variable = mission_failed 
                    } 
                }
                trigger_event = { id = dynamic_missions.34 }
            }
        }
    }
    
    on_ended = {
        # Clean up all variables and modifiers
        remove_variable = situation_start_date
        remove_variable = target_location
        remove_variable = mission_success
        remove_variable = mission_failed
        remove_variable = appointed_governor
        
        # Remove character modifiers from governor if appointed
        if = {
            limit = { has_variable = governor_character }
            var:governor_character = {
                remove_character_modifier = dm_regional_governor_debuff
            }
            remove_variable = governor_character
        }
    }
}
```

### 4.2. Events

**Event IDs:**
- `dynamic_missions.30`: Start the Establish New City mission (select target town)
- `dynamic_missions.31`: Select character for Regional Governor
- `dynamic_missions.32`: Confirm governor appointment
- `dynamic_missions.33`: Success event (city established)
- `dynamic_missions.34`: Failure event (time expired)

### 4.3. Modifiers

**Country Modifiers:**
- `dm_encourage_migration_modifier`: Court expenses +5%, value shift to Freemen +0.10
- `dm_encourage_proselytization_modifier`: Court expenses +5%, value shift to Spiritual +0.10
- `dm_encourage_folk_culture_modifier`: Court expenses +5%, value shift to Humanist +0.10
- `dm_requisition_materials_modifier`: Estate satisfaction -5%, taxation cap +5%

**Location Modifiers:**
- `dm_migration_boost`: Migration attraction +1, migration speed +50%
- `dm_conversion_boost`: Monthly conversion +20, conversion speed +50%
- `dm_assimilation_boost`: Monthly assimilation +20, assimilation speed +50%
- `dm_governor_control_bonus`: Dynamic control bonus (calculated per character)
- `dm_country_pearl`: Permanent reward modifier (monthly prosperity +0.5%, development +0.005, migration attraction +1)

**Character Modifiers:**
- `dm_regional_governor_debuff`: Unsuitable for council/general/admiral, life expectancy -10

### 4.4. Scripted Triggers

```
can_start_establish_new_city_mission = {
    any_owned_location = {
        location_rank = town
        is_occupied = no
        is_under_siege = no
    }
    NOT = { has_country_flag = has_completed_establish_city_mission }
    gold >= 300
    administrative_power >= 30
}
```

### 4.5. Generic Actions

The toggleable actions will be implemented as decisions in `common/decisions/` rather than generic actions, as they need to persist across game sessions and provide better player control.

The "Appoint Regional Governor" action will be a generic action that triggers an event for character selection.

## 5. Localization Keys

All text will be added to `dynamic_missions_l_english.yml`:

### Situation
- `establish_new_city_situation`: "Establishing a New City"
- `establish_new_city_situation_desc`: "We are nurturing a town to become a great city..."

### Events
- `dynamic_missions.30.title`: "Establish a New City"
- `dynamic_missions.30.desc`: "Which town shall we develop into a great city?"
- `dynamic_missions.33.title`: "A New City is Born!"
- `dynamic_missions.33.desc`: "Our efforts have borne fruit..."
- `dynamic_missions.34.title`: "City Development Stalled"
- `dynamic_missions.34.desc`: "Despite our efforts, the town has not yet achieved city status..."

### Actions
- `dm_encourage_migration_decision`: "Encourage Migration"
- `dm_encourage_proselytization_decision`: "Encourage Proselytization"
- `dm_encourage_folk_culture_decision`: "Encourage Folk Culture"
- `dm_appoint_regional_governor`: "Appoint Regional Governor"
- `dm_requisition_materials_decision`: "Requisition Development Materials"

### Modifiers
- `dm_country_pearl`: "[Country.GetName]'s Pearl"
- `dm_country_pearl_desc`: "This city stands as a shining jewel in our realm."

## 6. Balance Considerations

### 6.1. Duration
The 10-year duration is longer than the previous two missions (5 years each), reflecting the significant challenge of elevating a town to city status.

### 6.2. Toggleable Actions
All three cultural/religious/migration actions have the same cost (5% court expenses) to provide balanced choices. Players must decide which aspect of development to prioritize based on their strategic goals.

### 6.3. Governor Appointment
The governor system provides a significant boost but comes at a steep cost:
- Immediate legitimacy loss
- Character becomes unavailable for other roles
- Reduced life expectancy creates urgency

The bonus scales with character skill, rewarding players who assign talented individuals.

### 6.4. Material Requisition
This action provides an economic trade-off: increased taxation at the cost of estate happiness. It can accelerate development but risks internal stability.

## 7. Integration with Existing System

This mission integrates seamlessly with the existing dynamic missions framework:

1. Added as Option 3 in `dynamic_missions.1` (Choose Your Goal event)
2. Uses the same `active_dynamic_mission` variable system
3. Follows the same success/failure event pattern
4. Respects the mission cooldown system
5. Uses consistent naming conventions and file organization

## 8. Future Enhancements

Potential improvements for future versions:

1. **AI Participation**: Add neighboring countries or subjects who can help or hinder city development
2. **Random Events**: Special events during the 10-year period (plague, trade boom, etc.)
3. **Multiple Cities**: Allow players to develop multiple towns simultaneously
4. **City Specialization**: Different development paths (trade hub, military fortress, cultural center)
5. **Visual Feedback**: Custom map mode showing city development progress

## 9. Testing Checklist

- [ ] Mission appears in main event when conditions are met
- [ ] Town selection works correctly
- [ ] All toggleable decisions function properly
- [ ] Governor appointment event triggers and applies modifiers
- [ ] Success condition triggers when town becomes city
- [ ] Failure condition triggers after 10 years
- [ ] Reward modifier is applied correctly
- [ ] All modifiers are removed on mission end
- [ ] Character modifiers are cleaned up properly
- [ ] Localization displays correctly
- [ ] No conflicts with other dynamic missions
- [ ] Mission completion flag prevents re-triggering

## 10. File Checklist

Files to be modified or created:

- [x] `/docs/Establish_New_City_Mission_Design.md` (this document)
- [ ] `/src/template_mod/in_game/common/situations/dynamic_missions_situations.txt`
- [ ] `/src/template_mod/in_game/common/static_modifiers/dynamic_missions_modifiers.txt`
- [ ] `/src/template_mod/in_game/common/scripted_triggers/dynamic_missions_triggers.txt`
- [ ] `/src/template_mod/in_game/common/decisions/dynamic_missions_decisions.txt` (new file)
- [ ] `/src/template_mod/in_game/common/generic_actions/dynamic_missions_actions.txt`
- [ ] `/src/template_mod/in_game/events/dynamic_missions_events.txt`
- [ ] `/src/template_mod/main_menu/localization/english/dynamic_missions_l_english.yml`

---

**Implementation Status:** Design Complete - Ready for Implementation

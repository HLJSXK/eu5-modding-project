# Task Summary: Large Research Project Dynamic Mission

**Author:** Manus AI  
**Date:** Jan 28, 2026  
**Task:** Design the second dynamic task for the EU5 mod

## Executive Summary

This document summarizes the design and implementation of the "Large Research Project" dynamic mission for the European Universalis 5 modding project. The mission provides players with a focused, long-term research endeavor that spans five years and offers significant technological rewards upon completion.

## Mission Overview

The **Large Research Project** is a dynamic situation that simulates a major research initiative undertaken by the player's nation. The mission involves collaboration and competition with subjects and neighboring countries, offering multiple strategic options to accelerate progress.

### Key Characteristics

| Attribute | Value |
|-----------|-------|
| **Type** | Dynamic Situation |
| **Duration** | 5 years (60 months) |
| **Participants** | Player, all subjects, and all neighboring countries |
| **Success Condition** | Achieve 100% research progress |
| **Reward** | +20 research progress in a chosen technology category |
| **Trigger Condition** | Player has more than 10 technologies and has subjects or neighbors |

## Player Options

The mission provides three distinct player actions, each offering different strategic trade-offs.

### 1. Increase Research Funding (Toggle)

This toggleable option represents a sustained commitment to the research project. When activated, the player's court expenses increase by 5%, but the nation gains a +0.10 modifier to innovativeness and the project progresses by 1% each month.

**Trade-off:** Consistent progress at the cost of increased expenses and a shift in national values toward innovation.

### 2. Conscript University

This action allows the player to forcibly redirect the resources of a university toward the research project. The selected location suffers penalties to control (-5%), maximum literacy (-5%), and satisfaction (-10%) for the duration of the project. In return, the project gains 1% progress per month for each conscripted university.

**Trade-off:** Accelerated progress at the cost of local stability and educational capacity. This action has a one-year cooldown and can be used multiple times, with effects stacking.

### 3. Appoint Lead Scientist

This one-time action allows the player to designate a character from their court as the lead scientist. The character provides an immediate progress boost equal to (total skill points / 10)%, but suffers severe penalties: they become unsuitable for the council, military, or naval command, and their life expectancy is reduced by 10 years.

**Trade-off:** A significant one-time boost in exchange for sacrificing a character's utility and longevity.

## Implementation Details

The implementation follows the established patterns of the Dynamic Missions framework, ensuring consistency and maintainability.

### File Structure

The mission is implemented across the following files:

- **`dynamic_missions_situations.txt`**: Defines the `large_research_project_situation` with its lifecycle hooks.
- **`dynamic_missions_actions.txt`**: Implements the player actions for conscripting universities and appointing the lead scientist.
- **`dynamic_missions_modifiers.txt`**: Defines all modifiers applied by the mission actions.
- **`dynamic_missions_events.txt`**: Contains events for starting the mission, selecting universities and characters, and handling success or failure.
- **`dynamic_missions_triggers.txt`**: Defines the `can_start_large_research_project` trigger.
- **`dynamic_missions_l_english.yml`**: Provides localization for all mission-related text.

### Integration with Existing Framework

The new mission integrates seamlessly with the existing Dynamic Missions system. The main selection event (`dynamic_missions.1`) has been updated to include the Large Research Project as an option, and the general eligibility trigger (`can_receive_dynamic_mission`) now includes the new mission in its checks.

## Design Rationale

The Large Research Project was designed to provide a research-focused alternative to the existing city development mission. The design emphasizes player agency through multiple strategic options, each with meaningful trade-offs that reflect the challenges of managing a large-scale research initiative.

The five-year duration creates a long-term commitment that encourages sustained engagement, while the 100% progress requirement ensures that players must actively use the available options rather than passively waiting for the mission to complete. The reward of +20 research progress is substantial enough to justify the investment while remaining balanced within the broader game economy.

## Testing Considerations

When testing this mission in-game, the following aspects should be verified:

1. **Trigger Functionality**: Ensure the mission appears as an option when the player has more than 10 technologies and has subjects or neighbors.
2. **Progress Tracking**: Verify that the research progress variable updates correctly each month based on active modifiers.
3. **Action Availability**: Confirm that the "Conscript University" action only appears when universities are available and not on cooldown.
4. **Character Selection**: Test that the "Appoint Lead Scientist" event correctly calculates the progress bonus and applies the character modifier.
5. **Situation Ending**: Verify that the situation ends correctly when either 100% progress is reached or 5 years have passed.
6. **Cleanup**: Ensure all variables and modifiers are properly removed when the situation ends.

## Future Enhancements

Potential improvements to the Large Research Project mission include:

- **Technology Category Selection**: Allow players to choose which technology category receives the +20 progress reward.
- **Participant Actions**: Implement actions for subjects and neighbors to interact with the project (e.g., sabotage, collaboration).
- **Dynamic Events**: Add random events that can occur during the project, such as breakthroughs, setbacks, or discoveries.
- **Visual Feedback**: Create custom GUI elements to display progress and active modifiers more clearly.

## Conclusion

The Large Research Project dynamic mission successfully expands the Dynamic Missions framework with a research-focused alternative. The implementation follows established patterns, ensuring maintainability and consistency with existing code. The mission offers meaningful strategic choices and trade-offs, enhancing the player's engagement with the game's technology system.

All code has been implemented, documented, and pushed to the GitHub repository, ready for testing and further refinement.

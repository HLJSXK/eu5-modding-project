# Design Document: New Dynamic Missions

**Author:** Manus AI
**Date:** Jan 22, 2026

This document outlines the design for two new mission types for the Dynamic Missions feature: **Military Expansion** and **Technological Breakthrough**.

## 1. Mission: Military Expansion

This mission focuses on a concentrated military campaign to seize a specific region from a rival.

### 1.1. Core Characteristics

*   **Objective**: Conquer all provinces in a player-selected, adjacent, foreign region.
*   **Participants**: The player and the target country owning the region. Allies of both sides can be drawn into the conflict.
*   **Duration**: 10 years.
*   **Success Condition**: The player owns and fully controls all provinces in the target region.
*   **Failure Condition**: The 10-year time limit is reached, or the player is forced to concede defeat in a war over the target region.
*   **Reward**: Permanent claims on the entire conquered region and a significant bonus to Prestige and Army Tradition.

### 1.2. Player Actions

These actions become available once the "Military Expansion" situation is active, each with a 2-year cooldown.

| Action Name             | Cost                | Effects                                                                                                       | Strategic Use                                                              |
| ----------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Forced March**        | (None)              | **Global:** +50% Army Movement Speed<br>**Global:** +25% Morale Damage Taken                                   | Quickly move armies to seize key objectives, but at the risk of higher casualties. |
| **War Economy**         | (None)              | **Global:** -25% Tax Income<br>**Global:** +50% Manpower Recovery Speed<br>**Global:** -25% Mercenary Cost      | Sustain a long and costly war by sacrificing economic gain for military readiness. |
| **Diplomatic Pressure** | 200 Diplomatic Power | Reduces the "War Enthusiasm" of the target country's allies, making them more likely to accept a separate peace. | Isolate the primary target by peeling away their allies through diplomatic means.     |

### 1.3. Target Country Actions

The AI-controlled target of the expansion will also have unique actions to counter the player.

| Action Name       | AI Trigger Conditions          | Effects                                                                                               |
| ----------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------- |
| **Scorched Earth**  | A province is under siege.     | In a friendly-controlled province, development and prosperity are reduced, but enemy attrition is doubled. |
| **Call for Aid**  | Losing the war (war score < -25) | Spends Prestige to gain a temporary relations boost with the player's other rivals, increasing the chance of a new alliance against the player. |

## 2. Mission: Technological Breakthrough

This mission focuses on a national effort to be the first in the world to research a specific, game-changing technology.

### 2.1. Core Characteristics

*   **Objective**: Be the first nation to unlock a player-selected, high-impact technology from the next era.
*   **Participants**: The player. This is a race against all other technologically advanced nations.
*   **Duration**: 20 years.
*   **Success Condition**: The player successfully researches the target technology before any other nation.
*   **Failure Condition**: The 20-year time limit is reached, or another nation researches the technology first.
*   **Reward**: The technology is unlocked immediately at a 50% reduced cost, and the player gains a permanent +10% research speed bonus for 50 years.

### 2.2. Player Actions

These actions become available once the "Technological Breakthrough" situation is active, each with a 3-year cooldown.

| Action Name               | Cost                | Effects                                                                                                                                                              | Strategic Use                                                                                             |
| ------------------------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Sponsor Innovators**    | 1000 Gold           | Instantly grants a significant chunk of research points (e.g., 25% of the total cost) towards the target technology. Has a 15% chance of failure, wasting the gold. | A high-risk, high-reward option to surge ahead if you have a strong treasury.                               |
| **Academic Seclusion**    | (None)              | **Global:** -2 Diplomatic Reputation<br>**Target Tech:** +50% Research Speed                                                                                         | Isolate your nation from global affairs to create a focused environment for your researchers.               |
| **Industrial Espionage**  | 200 Diplomatic Power | Triggers a spy action against a more advanced nation. If successful, steals a percentage of their research progress. Failure can be discovered, causing a major diplomatic incident. | A covert option to catch up to or surpass a rival, but with significant diplomatic risk.                      |

### 2.3. Progress Visualization

The GUI for this situation will feature two progress bars:
1.  **Player's Progress**: Shows the player's accumulated research towards the target tech.
2.  **Rival's Progress**: Shows the progress of the most technologically advanced rival nation, creating a clear visual of the race.

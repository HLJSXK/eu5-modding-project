# Dynamic Missions Feature Guide

**Author:** Manus AI
**Date:** Jan 22, 2026

## 1. Introduction

This document provides a comprehensive guide to the **Dynamic Missions** feature, a new gameplay system designed for the EU5 Modding Project. This feature introduces a framework for player-driven, focused objectives that offer significant rewards upon completion, encouraging strategic specialization and providing a more varied gameplay experience.

## 2. Feature Overview

The core concept of Dynamic Missions is to allow the player to temporarily focus the nation's efforts on a single, ambitious goal. Instead of balancing expansion, economic development, and diplomacy simultaneously, the player can choose to prioritize one area for a set period, unlocking powerful bonuses and unique interactions related to that goal.

This system is built upon the native EU5 **Situations** and **Generic Actions** frameworks, ensuring seamless integration with the core game mechanics and UI.

### Key Characteristics

*   **Player-Initiated**: Missions are started via a player-only event, giving full control over when to engage with the system.
*   **Exclusive Focus**: Only one Dynamic Mission can be active at a time, making the choice of which goal to pursue a significant strategic decision.
*   **Time-Limited Objectives**: Each mission has a time limit, creating a sense of urgency and a clear endpoint.
*   **High-Risk, High-Reward**: Successfully completing a mission yields substantial rewards, while failure means the investment of time and resources provides no final payoff.
*   **Interactive Gameplay**: Missions involve unique player actions and reactions from other countries (such as subjects), making them an engaging, multi-faceted experience.
*   **Clear Visualization**: Custom GUI panels with progress bars for completion and time remaining provide clear feedback on the mission's status.

## 3. The "City Development" Mission

The first mission implemented in this framework is **City Development**. It serves as a template and a fully-featured example of the Dynamic Missions system.

### 3.1. Goal and Reward

*   **Objective**: To develop a chosen city or town to its peak potential.
*   **Success Conditions** (must be met within 5 years):
    1.  The target location reaches **100% Prosperity**.
    2.  At least **10 new buildings** are constructed in the location.
*   **Reward**: The target location permanently gains **+1 Development**.

### 3.2. Player Actions

While the City Development situation is active, the player gains access to three powerful, unique actions, each with a one-year cooldown. These actions represent the nation's focused effort on the project.

| Action Name              | Cost        | Cooldown | Effects                                                                                                                               | Strategic Use                                            |
| ------------------------ | ----------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **Convene Builders**     | (None)      | 1 Year   | **Global:** -50% Construction Speed<br>**Target City:** +100% Construction Speed                                                       | Rapidly construct the required buildings in the target city. |
| **Public Works Program** | 500 Gold    | 1 Year   | **Target City:** +1% Monthly Prosperity Growth                                                                                        | Accelerate prosperity gain when you have a strong economy.   |
| **Demand Contributions** | (None)      | 1 Year   | **Other Cities:** -10% Control (instant)<br>**Target City:** +100% Maximum Control Cap                                                   | Quickly boost the target city's control to maximize its output. |

### 3.3. Participant Interactions (Subjects)

Subjects of the player are automatically involved in the situation and can choose to either help or hinder the effort based on their loyalty and opinion. This adds a layer of internal politics to the mission.

| Action Name                    | Who Can Use It      | Cooldown | Effects                                                                                                                             | AI Behavior                                           |
| ------------------------------ | ------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| **Steal Development Resources**  | Disloyal Subjects   | 1 Year   | **Target City:** -1% Monthly Prosperity<br>**Subject's Capital:** +1% Monthly Prosperity                                             | High chance if disloyal and opinion is negative.       |
| **Contribute to Development**    | Loyal Subjects      | 1 Year   | **Target City:** +1% Monthly Prosperity<br>**Subject's Capital:** -1% Monthly Prosperity                                             | High chance if loyal and opinion is 50 or higher.     |

When a subject takes one of these actions, the player receives a notification, allowing them to react to their subjects' behavior.

## 4. Technical Implementation

The Dynamic Missions feature has been integrated into the main project mod (`template_mod`), ensuring a unified structure and easy management.

### 4.1. File Structure

The mod is organized into the following files, adhering to EU5 modding best practices:

```
template_mod/
├── in_game/
│   ├── common/
│   │   ├── generic_actions/dynamic_missions_actions.txt
│   │   ├── situations/dynamic_missions_situations.txt
│   │   └── static_modifiers/dynamic_missions_modifiers.txt
│   ├── events/dynamic_missions_events.txt
│   └── gui/panels/situation/develop_city_situation.gui
└── main_menu/
    └── localization/dynamic_missions_l_english.yml
```

### 4.2. Key Scripting Components

*   **Events (`dynamic_missions_events.txt`)**: Handle the starting, success, and failure of missions. A key trigger, `NOT = { has_variable = active_dynamic_mission }`, ensures only one mission is active at a time.
*   **Situations (`dynamic_missions_situations.txt`)**: The core of the feature. The `develop_city_situation` defines the participants, duration, end conditions, and progress tracking.
*   **Generic Actions (`dynamic_missions_actions.txt`)**: Defines the unique actions available to the player and subjects during the mission, including their costs, cooldowns, and effects.
*   **Static Modifiers (`dynamic_missions_modifiers.txt`)**: Contains the definitions for all temporary modifiers applied by the generic actions, such as `dm_global_construction_penalty` and `dm_prosperity_boost`.
*   **GUI (`develop_city_situation.gui`)**: Creates the custom panel for the situation, including the two progress bars for completion and time remaining. It uses the `SituationView` datacontext to display dynamic information.
*   **Localization (`dynamic_missions_l_english.yml`)**: Provides all English text for events, actions, tooltips, and modifiers, ensuring a polished user experience.

## 5. Future Development

The Dynamic Missions framework is designed for easy expansion. New missions can be added by creating new situations, events, and actions. Potential future missions could include:

*   **Military Campaigns**: Conquer a specific region or defeat a rival within a time limit.
*   **Economic Dominance**: Achieve a monopoly on a key trade good or reach a certain income level.
*   **Colonial Expansion**: Colonize a target region before a rival does.
*   **Religious Conversion**: Convert a set number of provinces to your state religion.

By leveraging the existing structure, new and diverse gameplay scenarios can be rapidly developed and integrated into the game.

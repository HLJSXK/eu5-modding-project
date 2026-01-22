# Dynamic Missions Feature Design

**Author:** Manus AI
**Date:** Jan 22, 2026

## 1. Overview

This document outlines the design and architecture for the "Dynamic Missions" feature in the EU5 modding project. This feature introduces a system of player-driven goals, implemented as situations, to provide focused gameplay objectives and rewards.

## 2. File Structure

The feature will be implemented across several files, organized as follows:

```
/src/dynamic_missions/
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

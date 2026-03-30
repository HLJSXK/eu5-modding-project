# Dynamic Missions Mod for EU5

## Overview

This mod implements a dynamic mission system for Europa Universalis V, allowing players to engage with procedurally-generated, context-aware missions that adapt to their gameplay situation.

## Status

- **Development state:** Active (resumed on 2026-03-31)
- **Current focus:** Stabilize core mission loop with unified mission state and debug-friendly GUI
- **Validation state:** Not fully validated in-game yet. Prioritize simple, traceable logic for debugging.

## Features

### Core Missions

### Develop City Mission
- Select a target city/town and push prosperity to completion
- Time-limited objective with simple success/fail flow

### Large Research Project Mission
- Long-term research objective tracked by mission progress
- Optional funding decision to accelerate progress

### Establish New City Mission
- Develop underdeveloped provinces into thriving cities
- 10-year timeline with mission-specific support decisions
- Permanent reward on success

### Claim Province Mission (Core Path)
- Auto-select a neighboring foreign location as target
- Win condition: own target location before timeout
- Simplified implementation for reliable debugging

## Structure

```
develop/
├── .metadata/
│   └── metadata.json              # Mod metadata
├── in_game/
│   ├── common/
│   │   ├── decisions/             # Mission-related decisions
│   │   ├── generic_actions/       # Player actions for missions
│   │   ├── scripted_triggers/     # Conditional logic
│   │   ├── situations/            # Mission situation definitions
│   │   └── static_modifiers/      # Mission effects and bonuses
│   ├── events/
│   │   └── dynamic_missions_events.txt
│   └── gui/
│       └── panels/situation/      # Custom UI for missions
└── main_menu/
    └── localization/
        ├── dynamic_missions_l_english.yml
        └── dynamic_missions_l_simp_chinese.yml
```

## Installation

1. Copy the entire `develop` folder to:
   ```
   Documents/Paradox Interactive/Europa Universalis V/mod/
   ```

2. Launch EU5 and enable the mod in the launcher

3. Start or load a game to access dynamic missions

## How to Use

### Starting a Mission

1. Wait for yearly pulse mission prompt (or mission follow-up prompt)
2. Pick one mission from the event menu
3. If target selection is required, select a valid target
4. Track progress in the Dynamic Missions situation panel

### Managing Missions

- One always-active `dynamic_missions_situation` panel is used as mission manager UI
- Actual mission state is stored on **country scope** variables
- Use mission decisions when available (research funding, city support toggles)
- Debug panel shows intermediate variables for diagnosis

### Mission Completion

- Successfully completing missions grants rewards
- Failed missions clear mission state and allow re-selection
- Failed missions may have consequences

## Technical Details

### Multiplayer Compatibility

- Fully synchronized for multiplayer games
- All players must have the mod installed
- Mission UI routing variables are country-scoped so each player can see their own mission panel state

### Performance

- Mission manager checks run monthly inside one situation
- Selection prompt runs on yearly pulse
- Logic is intentionally kept simple during debugging phase

## Documentation

For detailed design documentation, see:
- [Dynamic Missions Design](../../docs/design/Dynamic_Missions_Design.md) - Complete system design for all missions
- [Framework Architecture](../../docs/technical/Dynamic_Missions_Framework_Architecture.md) - Technical implementation details

## Version History

- **1.1.0** (Mar 2026): Unified mission manager migration
  - Per-country mission state model
  - Multiplayer-safe panel routing
  - Debug-oriented GUI variable output
- **1.0.0** (Jan 2026): Initial dynamic missions baseline

## Credits

**Created by:** EU5 Modding Project Team
**Last Updated:** March 31, 2026

## License

This mod is part of the EU5 Multiplayer Project.

---

For questions, issues, or contributions, please refer to the main project documentation.

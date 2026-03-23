# Dynamic Missions Mod for EU5

## Overview

This mod implements a dynamic mission system for Europa Universalis V, allowing players to engage with procedurally-generated, context-aware missions that adapt to their gameplay situation.

## Features

### 🏙️ Establish New City Mission
- Develop underdeveloped provinces into thriving cities
- Multi-stage progression system with meaningful choices
- Economic and infrastructure development focus
- Rewards scale with investment and choices

### 🔬 Large Research Project Mission
- Conduct ambitious research initiatives
- Resource allocation and risk management
- Multiple research paths and outcomes
- Technology and innovation bonuses

## Structure

```
dynamic_missions/
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

1. Copy the entire `dynamic_missions` folder to:
   ```
   Documents/Paradox Interactive/Europa Universalis V/mod/
   ```

2. Launch EU5 and enable the mod in the launcher

3. Start or load a game to access dynamic missions

## How to Use

### Starting a Mission

1. Open the Decisions menu (default hotkey: `D`)
2. Look for available dynamic missions
3. Check if you meet the requirements
4. Click to start the mission

### Managing Missions

- Missions appear as **Situations** in your country panel
- Track progress through the situation interface
- Make choices when prompted by events
- Complete objectives to advance through stages

### Mission Completion

- Successfully completing missions grants rewards
- Rewards include modifiers, bonuses, and unique benefits
- Failed missions may have consequences

## Technical Details

### Multiplayer Compatibility

- Fully synchronized for multiplayer games
- All players must have the mod installed
- Tested for desync prevention

### Performance

- Optimized trigger checks
- Minimal performance impact
- Scales well with game progression

## Documentation

For detailed design documentation, see:
- [Dynamic Missions Design](../../docs/design/Dynamic_Missions_Design.md) - Complete system design for all missions
- [Framework Architecture](../../docs/technical/Dynamic_Missions_Framework_Architecture.md) - Technical implementation details

## Version History

- **1.0.0** (Jan 2026): Initial release with three missions
  - Develop City Mission
  - Large Research Project Mission
  - Establish New City Mission

## Credits

**Created by:** EU5 Modding Project Team
**Last Updated:** January 28, 2026

## License

This mod is part of the EU5 Multiplayer Project.

---

For questions, issues, or contributions, please refer to the main project documentation.

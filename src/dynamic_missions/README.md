# Dynamic Missions Mod

**Version:** 1.0.0  
**Compatible with:** EU5 1.x.x  
**Author:** EU5 Modding Project

## Overview

The Dynamic Missions mod introduces a new gameplay system that allows players to focus their efforts on specific, ambitious goals rather than pursuing everything simultaneously. This creates more strategic depth and differentiation in playstyles.

## Features

### Core System
- **Focus Event System**: Choose from multiple mission types (currently: City Development)
- **Situation-Based Tracking**: Missions are implemented as EU5 situations with custom GUI
- **Progress Visualization**: Two progress bars show completion status and time remaining
- **Exclusive Focus**: Only one mission can be active at a time, forcing strategic choices

### City Development Mission

The first implemented mission allows players to focus on developing a single city to maximum prosperity.

**Goal Requirements:**
- Achieve 100% prosperity in the target city
- Construct at least 10 new buildings
- Complete within 5 years (60 months)

**Reward:**
- +1 Development to the target city upon completion

**Player Actions:**

1. **Convene Builders** (Cooldown: 1 year)
   - Effect: -50% global construction speed, +100% construction speed in target city for 1 year
   - Use when: You want to rapidly construct buildings in the target city

2. **Public Works Program** (Cooldown: 1 year, Cost: 500 Gold)
   - Effect: +1% monthly prosperity in target city for 1 year
   - Use when: You have excess gold and want to boost prosperity growth

3. **Demand Contributions** (Cooldown: 1 year)
   - Effect: -10% control in all other cities, +100% max control cap in target city for 1 year
   - Use when: You need to maximize control in the target city

**Subject Interactions:**

Subjects of the player can choose to help or hinder the mission:

1. **Steal Progress** (Disloyal subjects only, Cooldown: 1 year)
   - Effect: -1% monthly prosperity in target city, +1% monthly prosperity in subject's capital for 1 year
   - AI will use: When disloyal and has negative opinion of overlord

2. **Contribute to Development** (Loyal subjects only, Cooldown: 1 year)
   - Effect: +1% monthly prosperity in target city, -1% monthly prosperity in subject's capital for 1 year
   - AI will use: When loyal and has positive opinion of overlord (50+)

## Installation

1. Copy the `dynamic_missions` folder to your EU5 mods directory:
   - Windows: `Documents/Paradox Interactive/Europa Universalis V/mod/`
   - Linux: `~/.local/share/Paradox Interactive/Europa Universalis V/mod/`
   - macOS: `~/Documents/Paradox Interactive/Europa Universalis V/mod/`

2. Launch EU5 and enable the mod in the launcher

3. Start a new game or load an existing save

## Usage

1. The "Dynamic Missions: Choose Your Focus" event will appear for human players
2. Select "Develop a great city" to start the City Development mission
3. Choose your target city from the available towns and cities
4. Use the available actions strategically to achieve your goal within 5 years
5. Upon completion (or failure), you can choose a new mission

## Compatibility

- **Multiplayer**: Fully synchronized for multiplayer games
- **Save Games**: Can be added to existing saves
- **Other Mods**: Should be compatible with most mods unless they heavily modify situations or generic actions

## Future Expansion

The Dynamic Missions system is designed to be expandable. Future missions could include:

- **Military Expansion**: Conquer a specific region within a time limit
- **Economic Dominance**: Control a certain percentage of a trade good
- **Diplomatic Achievement**: Form a specific alliance network
- **Religious Conversion**: Convert a region to your religion
- **Technological Advancement**: Reach a specific technology level

## Technical Details

### File Structure
```
dynamic_missions/
├── .metadata/
│   └── metadata.json
├── in_game/
│   ├── common/
│   │   ├── situations/
│   │   │   └── dynamic_missions_situations.txt
│   │   ├── generic_actions/
│   │   │   └── dynamic_missions_actions.txt
│   │   └── static_modifiers/
│   │       └── dynamic_missions_modifiers.txt
│   ├── events/
│   │   └── dynamic_missions_events.txt
│   └── gui/
│       └── panels/
│           └── situation/
│               └── develop_city_situation.gui
└── main_menu/
    └── localization/
        └── dynamic_missions_l_english.yml
```

### Key Systems Used
- **Situations**: Core tracking mechanism with custom mapmode
- **Generic Actions**: Player and subject-initiated actions
- **Static Modifiers**: Temporary effects applied by actions
- **Events**: Trigger mission start, completion, and failure
- **GUI**: Custom situation panel with progress bars

## Known Issues

- GUI progress bars may not display correctly in some resolutions (vanilla EU5 GUI limitation)
- Subject AI may not always make optimal decisions regarding mission actions
- Prosperity calculation in situations may have rounding errors

## Credits

- **Design**: Based on the concept of focused gameplay objectives
- **Implementation**: EU5 Modding Project Team
- **Testing**: Community contributors

## License

This mod is released under the MIT License for educational and modding purposes.

## Support

For bug reports, suggestions, or contributions, please visit:
https://github.com/HLJSXK/eu5-modding-project

---

**Last Updated:** January 2026  
**Mod Version:** 1.0.0

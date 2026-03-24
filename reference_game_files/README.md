# EU5 Reference Game Files

## Overview

This directory contains extracted game files from **Europa Universalis 5** (released November 2025) for modding reference purposes. These files are essential for understanding game mechanics, modifier types, and scripting patterns.

## Contents

```
reference_game_files/
└── game/
    ├── in_game/           # Core gameplay files
    │   ├── common/        # Game definitions (modifiers, traits, events, etc.)
    │   ├── events/        # Event scripts
    │   ├── gui/           # User interface definitions
    │   ├── map_data/      # Map-related data
    │   └── setup/         # Game setup files
    ├── loading_screen/    # Loading screen assets
    └── main_menu/         # Main menu and global definitions
        ├── common/
        │   ├── modifier_type_definitions/  # All valid modifier types
        │   └── static_modifiers/           # Predefined modifiers
        └── localization/  # Text localization
```

## Key Files for Modding

### Modifier Definitions
- **`main_menu/common/modifier_type_definitions/00_modifier_types.txt`**
  - Contains all 13,903 lines of modifier type definitions
  - Essential reference for creating valid modifiers in mods

### Static Modifiers
- **`main_menu/common/static_modifiers/`**
  - `country.txt` - Country-level modifiers
  - `location.txt` - Location-level modifiers
  - `character.txt` - Character-level modifiers
  - `estates.txt` - Estate-related modifiers
  - `societal_values.txt` - Value shift modifiers

### Traits
- **`in_game/common/traits/`**
  - `00_ruler.txt` - Ruler personality and government traits
  - `01_general.txt` - Military leader traits
  - `02_admiral.txt` - Naval leader traits

### Situations (Game Mechanics)
- **`in_game/common/situations/`**
  - `black_death.txt` - Black Death pandemic situation
  - Examples of how to implement complex game situations

### Generic Actions
- **`in_game/common/generic_actions/`**
  - Player-triggered actions within situations
  - Examples: `black_death.txt`, `estates.txt`

## Usage Guidelines

### For Mod Development

1. **Finding Valid Modifiers**
   ```bash
   grep "modifier_name" reference_game_files/game/main_menu/common/modifier_type_definitions/00_modifier_types.txt
   ```

2. **Understanding Syntax**
   - Study similar features in vanilla files
   - Copy structure and adapt to your needs

3. **Localization Patterns**
   - Check `main_menu/localization/` for text formatting examples

### Important Notes

- **Encoding**: All `.txt` and `.yml` files MUST use **UTF-8 with BOM** encoding
- **Modifier Categories**: 
  - `country` - Applies to nations
  - `location` - Applies to provinces/cities
  - `character` - Applies to individuals
  - `unit` - Applies to military units
  - `estate` - Applies to estate groups

## Common Modifier Patterns

### Control Modifiers
```
local_monthly_control = 0.10      # +10% monthly control (location)
global_monthly_control = 0.05     # +5% monthly control (country)
local_max_control = 0.20          # +20% max control cap (location)
```

### Economic Modifiers
```
court_spending_cost = 0.05        # +5% court spending (country)
tax_income_efficiency = 0.10      # +10% tax efficiency (country)
global_estate_max_tax = 0.05      # +5% estate tax cap (country)
```

### Value Shifts (Societal Values)
```
monthly_towards_innovative = 0.10        # Shift towards innovative
monthly_towards_centralization = 0.05    # Shift towards centralization
monthly_towards_free_subjects = 0.10     # Shift towards free subjects
```

### Population Modifiers
```
local_pop_conversion_speed_modifier = 0.50    # +50% conversion speed
local_pop_assimilation_speed_modifier = 0.50  # +50% assimilation speed
```

### Character Modifiers
```
global_life_expectancy = -10      # -10 years life expectancy (country)
adm = 2                           # +2 administrative skill (character)
```

## File Exclusions

The following large file types have been excluded to reduce size:
- Music files (`.mp3`, `.ogg`)
- Large graphics (`.dds`, `.tga` over 10MB)
- Video files (`.bik`)

Core text files (`.txt`, `.yml`, `.gui`) and small graphics are included.

## Version Information

- **Game Version**: Europa Universalis 5 1.1.10
- **Baseline Update Date**: March 25, 2026
- **Purpose**: Modding reference and documentation

## Related Documentation

- [EU5 Modding Knowledge Base](../docs/technical/EU5_Modding_Knowledge_Base.md)
- [Dynamic Missions Design](../docs/design/Dynamic_Missions_Design.md)
- [Modifier Fixes Documentation](../docs/task_summaries/Task_Summary_Fix_Dynamic_Missions_Errors.md)

## License

These files are extracted from Europa Universalis 5 for educational and modding purposes only. Europa Universalis 5 is a trademark of Paradox Interactive AB.

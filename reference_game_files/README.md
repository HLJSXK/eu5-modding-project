# EU5 Reference Game Files

## Overview

This directory contains extracted game files from **Europa Universalis 5** (released November 2025) for modding reference purposes. These files are essential for understanding game mechanics, modifier types, and scripting patterns.

The contents are produced automatically by [`scripts/sync_reference.py`](../scripts/sync_reference.py) — see *Updating* below. Do not edit `game/` by hand; it will be wiped on the next sync.

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
    ├── main_menu/         # Main menu and global definitions
    │   ├── common/
    │   │   ├── modifier_type_definitions/  # All valid modifier types
    │   │   └── static_modifiers/           # Predefined modifiers
    │   ├── gui/           # Shared GUI (font_icons.gui, etc.)
    │   ├── setup/         # Initial game state (countries, pops, characters)
    │   └── localization/  # Text localization (english + simp_chinese only)
    ├── loading_screen/    # Engine defines, shared GUI, settings and other text
    └── dlc/               # Official DLC scripts, metadata and localization
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

## Filter Policy

`sync_reference.py` mirrors every top-level directory found directly under `<EU5>/game/` (`in_game/`, `main_menu/`, `loading_screen/`, `dlc/`, and any other directory the installed game ships), except `mod/` (installed Steam Workshop mods — other authors' mods plus this project's own deployed build output — not vanilla/official content, so it's excluded by name; see `EXCLUDED_TOP_LEVEL_DIRS` in `sync_reference.py`). On top of that:

**Directory prunes (before walking):**
- Any directory named `gfx/` is skipped (asset descriptors, not modding scripts).
- Inside any `localization/` directory, other known language directories are pruned. `english/`, `simp_chinese/`, and non-language containers such as `jomini/`, `music_player_gui/`, and `dlc/` are kept.

**File-level filters:**
1. Binary/media extension blocklist — `.png`, `.dat`, `.mp3`, and similar asset/binary extensions (see `BINARY_EXTENSIONS` in `sync_reference.py`) are dropped without opening the file.
2. Binary content sniff — any remaining file is read and dropped if a NUL byte appears in its first 8 KB. Everything else is treated as text and kept **regardless of extension**, so small unrecognized text-format files (e.g. `.font`, `.map`, `.csv`, `.settings`, `.guistateset`, `.guianimset`) are not silently dropped just because they weren't anticipated.
3. Flat locale-suffixed files (`*_l_<language>.yml`) are kept only for English and Simplified Chinese, regardless of their directory.
4. Per-directory size cap — default **30 MB** (`--max-dir-mb`); a directory whose own filtered files exceed this total is skipped. Subdirectories are evaluated independently. This cap is checked before the per-file cap, matching `eu5-towards-victory`.
5. Per-file size cap — default **10 MB** (`--max-file-mb`).

The filter policy and synchronization behavior match `eu5-towards-victory/scripts/sync_reference.py`. Sync stats are appended to [`data/sync_reference.log`](../data/sync_reference.log), including on dry runs. A dry run reports paths to add/remove and paths present in both trees; it does not compare file contents.

Files are copied byte-for-byte from the install. This repository pins reference text checkouts to LF in `.gitattributes`, matching the installed files and avoiding CRLF checkout/sync churn; UTF-8 BOMs are preserved.

## Updating to a new EU5 version

```powershell
$env:EU5_PYTHON = 'C:\Users\Hades\anaconda3\envs\eu5\python.exe'
$env:PYTHONUTF8 = '1'

# Preview what would change
& $env:EU5_PYTHON scripts/sync_reference.py --dry-run --verbose

# Wipe game/ and re-mirror with the current filter policy
& $env:EU5_PYTHON scripts/sync_reference.py --verbose

# Refresh derived indexes and BRIEF.md (required after sync)
& $env:EU5_PYTHON scripts/gen_brief.py  # Also runs gen_index.py
```

If the EU5 install lives at a non-default path, set `EU5_GAME_PATH` or pass `--source <path>`. Both now take the **install root containing `game/`**, for example `C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V`. The old script took the `game/` directory itself. The destination is fixed at this repository's `reference_game_files/game/`, matching the target project; `--dest` is no longer supported.

## Version Information

- **Reference Baseline**: Europa Universalis 5 1.3.11 (commit `e2800c57`)
- **Last Verified Against Local Install**: October 3, 2026 — all 4,200 reference files match the installed game
- **Purpose**: Modding reference and documentation

## Related Documentation

- [EU5 Modding Knowledge Base](../docs/technical/EU5_Modding_Knowledge_Base.md)
- [Dynamic Missions Design](../docs/archive/dynamic_missions/Dynamic_Missions_Design.md) (archived — development paused)
- [Modifier Fixes Documentation](../docs/archive/task_summaries/Task_Summary_Fix_Dynamic_Missions_Errors.md)

## License

These files are extracted from Europa Universalis 5 for educational and modding purposes only. Europa Universalis 5 is a trademark of Paradox Interactive AB.

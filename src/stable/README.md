# EU5 MP Stable Balance Mod

## Overview

This mod is the **stable branch** of the EU5 MP modding project. It is directly based on reference mod **3644897537** (Amalgamation Synergy), providing a well-tested, stable set of gameplay balance tweaks for multiplayer sessions.

This mod is maintained in parallel with the `develop` branch (formerly `dynamic_missions`), which contains experimental features under active development.

## Source

- **Reference Mod ID:** 3644897537
- **Origin:** Steam Workshop — Amalgamation Synergy (community mod)
- **Copied to src/stable:** 2026-03-23

## Features

### War Mechanics (from Harsher Wars)
- War exhaustion has greater impact on morale, levy size, stability, and legitimacy
- Capital occupation generates more war exhaustion (0.3/month vs vanilla 0.1/month)
- Total occupation gives 4x war exhaustion gain (2/month vs vanilla 0.5/month)
- Harsher combat defines: sea landing penalty increased, war exhaustion from losses increased

### Anti-Snowballing Measures (from Snowballing Cost)
- Building and RGO expansion costs increase with each age (up to +200% by Age 6)
- Base RGO size halved (local_max_rgo_size = 1 vs vanilla 2)
- Buildings are more expensive in low-control locations
- Road construction costs significantly increased (gravel 2x, paved 3x, modern 4x, railroad 10x)

### Tax Efficiency Tweaks (from Tax Efficiency Tweak)
- Base -15% tax efficiency for all countries
- Tax efficiency bonuses are lower across the board (but still worth pursuing)

### Little Ice Age Adjustments
- Ice Age events are slightly more forgiving (food penalties reduced)
- Livestock, winery, and harvest modifiers reduced to avoid excessive food crises

### Colonial Restrictions (from Restricted Colonization)
- AI requires tax base of 1000 (vs vanilla 100) to colonize
- Colonial nations can only colonize in their capital's region
- Historical colonizers (Portugal, Spain, England, etc.) are exempt from restrictions

### Price Rebalancing (from Reasonable Prices)
- Gold transfer amounts scaled to income (capped at 1000x scale vs vanilla 10,000x)
- Various diplomatic action costs adjusted for better balance
- General/Admiral training now costs gold (25g each)

### Prosperity System
- Monthly prosperity decay added to all ages
- Decay decreases with each age (representing world becoming more prosperous over time)

## File Structure

```
stable/
├── .metadata/
│   └── metadata.json          # Mod metadata for EU5 launcher
├── in_game/
│   └── common/
│       ├── age/
│       │   └── AS_default.txt              # Age modifiers (prosperity decay, build costs)
│       ├── auto_modifiers/
│       │   ├── AS_harsher_wars.txt         # War exhaustion auto-modifiers
│       │   └── AS_tax_efficiency.txt       # Base tax efficiency penalty
│       ├── cabinet_actions/
│       │   ├── AS_reduce_war_exhaustion.txt # Can't reduce war exhaustion while at war
│       │   └── study_institutions.txt      # Balanced institution spread cabinet action
│       ├── diplomatic_costs/
│       │   └── z_01_from_script.txt        # Diplomatic action costs
│       ├── generic_actions/
│       │   └── AS_colonial_charters.txt    # Restricted colonization rules
│       ├── goods/
│       │   └── AS_fish_food.txt            # Fish as food good
│       ├── prices/
│       │   ├── AS_00_hardcoded.txt         # Road and general price adjustments
│       │   ├── AS_03_diplomacy.txt         # Diplomatic action prices
│       │   └── readme.txt                  # Price system documentation
│       └── scripted_effects/
│           └── AS_country_gold_effects.txt # Scaled gold transfer effects
├── loading_screen/
│   └── common/
│       └── defines/
│           └── AS_00_defines.txt           # Combat and war defines
└── main_menu/
    └── common/
    │   ├── script_values/
    │   │   └── z_AO_default_values.txt     # Tax efficiency bonus values
    │   └── static_modifiers/
    │       ├── AS_country.txt              # Country-level modifiers (occupation, ice age)
    │       ├── AS_difficulty.txt           # Difficulty modifiers
    │       ├── AS_location.txt             # Location modifiers (siege, occupation, prosperity)
    │       └── AS_province.txt             # Province modifiers (ice age events)
    └── localization/
        └── english/
            ├── replace/
            │   └── AS_government_replace_l_english.yml  # Government text replacements
            └── taxefftweak_l_english.yml   # Tax efficiency localization
```

## Usage

1. Copy the `stable/` directory to your EU5 mod folder:
   ```
   Documents/Paradox Interactive/Europa Universalis V/mod/
   ```
2. Rename the folder if desired (e.g., `eu5mp_stable`)
3. Enable in the EU5 launcher
4. Ensure all MP players have the same mod enabled for synchronization

## Relationship to `develop` Branch

| Aspect | `stable` | `develop` |
|--------|----------|-----------|
| Source | Reference mod 3644897537 | Original dynamic_missions mod |
| Focus | Game balance tweaks | Dynamic mission system |
| Status | Active, stable | Development paused |
| Features | War, economy, anti-snowball | City building, research missions |

## Changelog

- **v1.0.0** (2026-03-23): Initial creation from reference mod 3644897537

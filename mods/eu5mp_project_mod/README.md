# EU5 MP Project Mod

## Overview

This is a template mod for the **EU5 Multiplayer Project**, designed to demonstrate best practices and common patterns for EU5 modding. It serves as both a learning resource and a starting point for creating custom mods.

## Purpose

This mod provides:
- **Reference Implementation**: Examples of properly structured events, modifiers, and localization
- **Best Practices**: Demonstrates naming conventions, file organization, and multiplayer compatibility
- **Template Structure**: A clean foundation for building custom mods

## Structure

```
eu5mp_project_mod/
├── .metadata/
│   └── metadata.json              # Mod metadata (required)
├── in_game/
│   ├── common/
│   │   └── eu5mp_sample_modifiers.txt  # Sample modifiers
│   └── events/
│       └── eu5mp_sample_events.txt     # Sample events
├── main_menu/
│   └── localization/
│       └── eu5mp_sample_l_english.yml  # English localization (UTF-8 BOM)
├── thumbnail.png                  # Mod preview image (optional)
└── README.md                      # This file
```

## Features

### Sample Events
- **eu5mp_sample.1**: Welcome event demonstrating basic event structure
- **eu5mp_sample.2**: Conditional event showing complex trigger logic

### Sample Modifiers
- **eu5mp_multiplayer_bonus**: Country modifier with economic and military bonuses
- **eu5mp_project_development**: Technology and development bonuses
- **eu5mp_enhanced_infrastructure**: Province-level infrastructure improvements
- **eu5mp_temporary_prosperity**: Timed modifier for short-term boosts

## Installation

1. Copy the entire `eu5mp_project_mod` folder to:
   ```
   Documents/Paradox Interactive/Europa Universalis V/mod/
   ```

2. Launch EU5 and enable the mod in the launcher

3. Start a new game to see the sample content

## Multiplayer Compatibility

This mod is configured for multiplayer synchronization:
- `multiplayer_synchronized: true` in metadata.json
- All players must have the same version installed
- Tested for desync prevention

## Customization Guide

### Adding New Events

1. Create a new `.txt` file in `in_game/events/`
2. Define a namespace at the top
3. Structure events following the examples in `eu5mp_sample_events.txt`
4. Add localization keys to `main_menu/localization/`

### Adding New Modifiers

1. Add modifier definitions to `in_game/common/`
2. Use descriptive names with your mod prefix
3. Reference modifiers in events or other scripts

### Localization

- All localization files must be UTF-8 BOM encoded
- Follow the naming convention: `*_l_<language>.yml`
- Organize keys by category with comments

## Best Practices Demonstrated

1. **Naming Conventions**: All files and keys use the `eu5mp_` prefix to avoid conflicts
2. **File Organization**: Content is logically separated into appropriate folders
3. **Documentation**: Inline comments explain the purpose of each section
4. **Multiplayer Ready**: Configured for synchronized multiplayer gameplay
5. **Version Control**: Clean structure suitable for Git tracking

## Extending This Mod

This template can be extended with:
- Additional events and event chains
- Custom GUI elements
- New government reforms
- Custom missions and decisions
- Graphics and interface modifications

## References

- [EU5 Modding Knowledge Base](../../docs/EU5_Modding_Knowledge_Base.md)
- [EU5 Wiki - Mod Structure](https://eu5.paradoxwikis.com/Mod_structure)
- [Project Documentation](../../docs/)

## Version History

- **1.0.0** (Jan 2026): Initial template release

## License

This mod is part of the EU5 Multiplayer Project and is provided as a learning resource.

---

**Created by:** Manus AI for the EU5 Multiplayer Project
**Last Updated:** January 22, 2026

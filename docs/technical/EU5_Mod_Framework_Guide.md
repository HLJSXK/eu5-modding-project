# EU5 Mod Framework Guide

**Author:** Manus AI
**Date:** Jan 22, 2026

## 1. Introduction

This guide provides a practical framework for creating mods in European Universalis 5, based on an analysis of 16 community mods from the Steam Workshop and official documentation. It serves as a companion to the **EU5 Modding Knowledge Base**, offering concrete examples and actionable patterns for mod development.

## 2. Mod Anatomy: Essential Components

Every EU5 mod consists of several key components that work together to extend or modify the game. Understanding the purpose and structure of each component is fundamental to successful mod development.

### 2.1. The Metadata System

The `.metadata` directory and its `metadata.json` file form the foundation of every mod. This file serves as the mod's identity card, providing the game launcher with essential information about the mod's compatibility, dependencies, and presentation.

The metadata file follows a strict JSON format with both required and optional fields. The **name** field defines how the mod appears in the launcher, while the **id** field provides a unique identifier that prevents conflicts with other mods. The **supported_game_version** field is particularly important, as it determines which game versions can load the mod. Using wildcard patterns like `1.*.*` allows the mod to remain compatible across minor patches, while specific versions like `1.0.7` restrict compatibility to exact builds.

For multiplayer mods, the `game_custom_data` object must include `"multiplayer_synchronized": true` to ensure all players in a multiplayer session have identical mod states. This prevents desynchronization issues that can corrupt multiplayer games.

### 2.2. Content Organization

EU5 mods organize their content into distinct top-level directories, each serving a specific purpose in the mod's architecture. This separation allows the game engine to efficiently load and process different types of content.

The **in_game** directory contains all gameplay-affecting content, including scripts, events, and GUI modifications. This is where the core logic of the mod resides. The **main_menu** directory houses localization files and graphics that appear in menus and interfaces. The **loading_screen** directory, while less commonly used, allows mods to customize the loading experience.

## 3. The Common Directory: Heart of Game Logic

The `in_game/common/` directory is the most frequently modified location in EU5 mods. It mirrors the game's own internal structure and contains subdirectories for nearly every moddable game system.

### 3.1. Common Subdirectories and Their Purposes

The following table summarizes the most important subdirectories within `common/`, based on frequency of use in community mods:

| Directory                  | Purpose                                      | Complexity | Usage Frequency |
| -------------------------- | -------------------------------------------- | ---------- | --------------- |
| `generic_actions/`         | Missions, decisions, and player actions      | Medium     | Very High       |
| `on_action/`               | Event triggers and game state hooks          | Medium     | Very High       |
| `auto_modifiers/`          | Automatic country and province modifiers     | Low        | High            |
| `unit_types/`              | Military unit definitions                    | Medium     | High            |
| `government_reforms/`      | Government system modifications              | High       | Medium          |
| `laws/`                    | Country laws and policies                    | Medium     | Medium          |
| `disasters/`               | Crisis and disaster events                   | High       | Medium          |
| `formable_countries/`      | Nations that can be formed through decisions | Medium     | Medium          |
| `scripted_triggers/`       | Reusable condition blocks                    | Low        | Medium          |
| `traits/`                  | Character traits and attributes              | Low        | Low             |

### 3.2. Script File Structure

Scripts in the `common/` directory follow a consistent pattern. Each file typically contains multiple definitions, each with a unique identifier. These definitions use a key-value syntax with nested blocks enclosed in braces.

The general structure follows this pattern:

```
unique_identifier = {
    property_1 = value
    property_2 = value
    
    nested_block = {
        nested_property = value
    }
}
```

Comments are denoted with the `#` symbol and can appear on their own lines or at the end of statements.

## 4. Event System Architecture

Events in EU5 represent a significant departure from EU4's event system. The removal of `mean_time_to_happen` means that all events must be explicitly triggered through other mechanisms, requiring more deliberate event chain design.

### 4.1. Event File Structure

Event files are stored in `in_game/events/` and use the `.txt` extension. Each file begins with a namespace declaration that groups related events together. This namespace becomes the prefix for all event IDs within the file.

A typical event definition includes several key sections:

**Type Declaration**: Specifies whether the event is a country event, character event, or other type. This determines the scope in which the event operates.

**Metadata**: Includes the title and description keys, which reference localization strings. The `fire_only_once` flag determines whether the event can occur multiple times in a single game.

**Illustration Tags**: Provide hints to the game about which background images to display. These tags are weighted, with higher numbers indicating stronger preferences.

**Trigger Block**: Contains the conditions that must be met for the event to fire. This is crucial for ensuring events only appear in appropriate contexts.

**Options**: Define the choices presented to the player. Each option has a name (localized) and an effects block that executes when the option is selected.

### 4.2. Event Triggering Mechanisms

Since EU5 events cannot trigger themselves, they must be called through one of several mechanisms:

**On Actions**: These are hooks into game state changes, such as the start of a new month, the beginning of a war, or the death of a ruler. Events registered with on_actions fire automatically when the associated game state change occurs.

**Decisions**: Player-initiated decisions can trigger events as part of their effects, creating interactive event chains.

**Other Events**: Events can trigger subsequent events in their effects blocks, creating branching narratives.

**Scripted Effects**: Custom scripted effects can include event triggers, allowing for reusable event-firing logic.

## 5. Localization System

The localization system in EU5 handles all player-facing text, from event descriptions to UI labels. Understanding its structure and requirements is essential for creating polished mods.

### 5.1. File Format and Encoding

Localization files use the `.yml` extension and must be encoded in **UTF-8 with BOM** (Byte Order Mark). This encoding requirement is strict; files without the BOM will not be recognized by the game. The BOM is a special sequence of bytes at the beginning of the file that identifies it as UTF-8.

Each localization file begins with a language declaration line, such as `l_english:` for English or `l_simp_chinese:` for Simplified Chinese. All subsequent lines define key-value pairs, where the key is the localization identifier and the value is the displayed text.

### 5.2. Naming Conventions

Localization files follow a strict naming pattern: `*_l_<language>.yml`, where the asterisk represents the mod or feature name, and the language code specifies which language the file contains. For example:

- `eu5mp_events_l_english.yml` - English localization for events
- `eu5mp_events_l_simp_chinese.yml` - Chinese localization for the same events

### 5.3. Localization Syntax

The basic syntax for localization entries is:

```yaml
l_english:
 key_name: "Display text"
 another_key: "More text with [concept|E]special formatting[/concept]"
```

The system supports several advanced features:

**Dynamic Text**: Variables can be inserted using square brackets, such as `[Country.GetName]` to display a country's name dynamically.

**Color Formatting**: Text can be colored using tags like `§G` for green or `§R` for red, followed by `§!` to reset.

**Icons**: Special icons can be inserted using codes like `£gold` for the gold icon.

**Concept Links**: The `[concept|E]...[/concept]` syntax creates clickable links to the game's concept encyclopedia.

## 6. GUI Modding Patterns

The GUI system in EU5 is highly modular and uses a declarative syntax to define interface elements. GUI files use the `.gui` extension and are located in `in_game/gui/`.

### 6.1. Type System

GUI files begin with a `types` declaration that defines the namespace for the GUI elements. Within this namespace, individual UI components are defined as types. These types can inherit from base types, allowing for reusable UI patterns.

A simple type definition might look like:

```
types my_mod_ui {
    type my_button = button {
        size = { 100 25 }
        text = "Click Me"
        onclick = { /* action code */ }
    }
}
```

### 6.2. Widget Hierarchy

GUI elements are organized hierarchically, with parent widgets containing child widgets. Common widget types include:

- **window**: Top-level containers for UI panels
- **button**: Clickable elements that trigger actions
- **textbox**: Displays text content
- **icon**: Displays images
- **container**: Generic layout containers
- **hbox/vbox**: Horizontal and vertical layout containers

### 6.3. Data Context

GUI elements can bind to game data through the data context system. This allows UI elements to display dynamic information that updates automatically as the game state changes. Data contexts are specified using square brackets, such as `[Country.GetGold]` to display a country's treasury.

## 7. Best Practices from Community Analysis

The analysis of 16 community mods revealed several consistent patterns that contribute to mod quality and compatibility.

### 7.1. Naming Conventions

Successful mods use consistent prefixes for all their files and identifiers. This prevents naming conflicts with other mods and makes it clear which content belongs to which mod. For example, a mod with the prefix `btc_` would name its files:

- `btc_explorers.txt`
- `btc_navy_units.txt`
- `btc_events_l_english.yml`

### 7.2. File Organization

Mods that organize their files logically are easier to maintain and debug. Rather than placing all scripts in a single file, successful mods split content by feature or category. For example, naval content might be separated from land military content, and economic events might be in a different file from political events.

### 7.3. Load Order Management

When mods need to override vanilla content or other mods, numbered prefixes control the load order. Files are loaded alphabetically, so `00_my_file.txt` loads before `01_my_file.txt`. This is particularly important for files in the `common/` directory, where later files can override earlier definitions.

### 7.4. Multiplayer Compatibility

Mods intended for multiplayer use must follow additional guidelines:

- Set `"multiplayer_synchronized": true` in `metadata.json`
- Avoid client-side only modifications that could cause desyncs
- Test thoroughly with multiple players
- Ensure all players use identical mod versions
- Document any known multiplayer issues

### 7.5. Version Control Integration

Mods that use Git or other version control systems benefit from:

- Clean directory structures with no generated files
- Meaningful commit messages documenting changes
- Branching strategies for experimental features
- Tagged releases for stable versions

## 8. Mod Complexity Tiers

Based on the community analysis, mods can be categorized into three complexity tiers, each requiring different levels of expertise and development time.

### 8.1. Simple Mods (1-20 files)

Simple mods make focused changes to specific game systems. They typically modify existing content rather than adding entirely new systems. Examples include:

- Balance adjustments to unit stats or economic values
- Small UI improvements or information displays
- Individual feature additions like new decisions or events

These mods are ideal for beginners and can be completed in a few hours to a few days.

### 8.2. Medium Mods (20-100 files)

Medium mods add substantial new content or modify multiple interconnected systems. They require a deeper understanding of the game's architecture and scripting language. Examples include:

- Content expansions adding new nations, missions, or events
- Gameplay overhauls affecting multiple systems
- Comprehensive localization packages
- UI redesigns with multiple new panels

These mods typically require several days to weeks of development and benefit from planning and design documentation.

### 8.3. Complex Mods (100+ files)

Complex mods represent major undertakings that can fundamentally transform the game experience. They often involve:

- Total conversions to different time periods or settings
- Major gameplay overhauls touching most game systems
- Comprehensive content packs with hundreds of events, missions, and features

These mods require months of development, team collaboration, and extensive testing. They benefit from formal project management and development processes.

## 9. Practical Workflow

A recommended workflow for mod development, based on community practices:

### 9.1. Planning Phase

Before writing any code, successful modders define their mod's scope and goals. This includes:

- Identifying which game systems will be modified
- Sketching out the mod's feature list
- Determining compatibility requirements
- Planning the file structure

### 9.2. Development Phase

Development should proceed incrementally, with frequent testing:

1. Set up the basic mod structure and metadata
2. Implement one feature at a time
3. Test each feature in-game before moving to the next
4. Add localization as features are completed
5. Document code with comments

### 9.3. Testing Phase

Thorough testing prevents bugs and compatibility issues:

- Test with a clean game installation
- Test with other popular mods to check for conflicts
- For multiplayer mods, test with multiple players
- Check the error log for warnings and errors
- Verify all localization keys are defined

### 9.4. Release Phase

Preparing for release involves:

- Creating a thumbnail image for the launcher
- Writing a clear mod description
- Documenting known issues and compatibility notes
- Choosing appropriate tags for discoverability
- Setting up a changelog system for future updates

## 10. Common Pitfalls and Solutions

### 10.1. Localization Not Appearing

**Problem**: Text shows as localization keys instead of readable text.

**Solution**: Ensure localization files are UTF-8 with BOM encoding and follow the correct naming convention.

### 10.2. Mod Not Loading

**Problem**: The mod doesn't appear in the launcher or fails to load.

**Solution**: Verify `metadata.json` is valid JSON and in the correct location. Check the error log for specific issues.

### 10.3. Events Not Firing

**Problem**: Events never trigger in-game.

**Solution**: Remember that EU5 events must be explicitly triggered. Add on_action hooks or decision triggers.

### 10.4. Multiplayer Desyncs

**Problem**: Multiplayer games desynchronize when using the mod.

**Solution**: Ensure all players have identical mod versions and that the mod is marked as multiplayer synchronized.

## 11. Reference: Sample Mod Structure

The EU5 MP Project includes a reference mod demonstrating these principles:

```
src/template_mod/
├── .metadata/
│   └── metadata.json
├── in_game/
│   ├── common/
│   │   └── eu5mp_sample_modifiers.txt
│   └── events/
│       └── eu5mp_sample_events.txt
├── main_menu/
│   └── localization/
│       └── eu5mp_sample_l_english.yml
└── README.md
```

This structure demonstrates:
- Proper metadata configuration
- Event file organization
- Modifier definitions
- Localization with UTF-8 BOM
- Documentation practices

For complete details, see the [template mod README](../src/template_mod/README.md) and the [raw analysis data](Mod_Structure_Analysis.txt).

## 12. Conclusion

Creating successful EU5 mods requires understanding both the technical requirements and the community best practices. By following the patterns established by successful community mods and adhering to the game's architectural principles, modders can create high-quality content that enhances the EU5 experience.

The framework presented in this guide provides a foundation for mod development, from simple tweaks to complex overhauls. As the modding community continues to grow and evolve, these patterns will be refined and expanded, but the core principles of clear organization, proper documentation, and thorough testing will remain essential.

## 13. References

[1] Manus AI analysis of 16 EU5 mods from Steam Workshop, January 2026.
[2] [Mod structure - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Mod_structure)
[3] [Event modding - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Event_modding)
[4] [Localization - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Localization)
[5] [Interface modding guide - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Interface_modding_guide)

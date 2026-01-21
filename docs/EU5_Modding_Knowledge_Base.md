# European Universalis 5 Modding Knowledge Base

**Author:** Manus AI
**Date:** Jan 21, 2026

## 1. Introduction

European Universalis 5 (EU5), released in November 2025, is a grand strategy game developed by Paradox Development Studio. Built upon an updated version of the Clausewitz Engine and featuring the Jomini scripting layer, EU5 offers a powerful and flexible platform for modding. This document provides a comprehensive overview of the EU5 modding landscape, covering everything from fundamental concepts to advanced techniques, to serve as a foundational knowledge base for your modding projects.

## 2. Game Architecture

Understanding the technical foundation of EU5 is crucial for effective modding. The game's architecture is composed of two primary components: the Clausewitz Engine and the Jomini scripting layer.

*   **Clausewitz Engine**: This is the core game engine that handles the underlying systems, rendering, and performance. The version used in EU5 features significant improvements over its predecessors, including better multi-core support, which addresses some of the performance bottlenecks present in earlier Paradox titles like EU4. [1]
*   **Jomini Scripting Layer**: Jomini serves as an intermediate layer between the Clausewitz Engine and the game's content. It provides a standardized set of scripting tools and a scripting language that is shared across several modern Paradox titles, including Crusader Kings 3 and Victoria 3. This shared foundation means that experience with modding these other games is often transferable to EU5. [2]

## 3. Getting Started with Modding

This section outlines the initial steps to set up your development environment and create your first mod.

### 3.1. Development Environment

A proper development environment can significantly streamline the modding process. The recommended setup involves a source code editor with support for Paradox scripting languages.

| Editor                  | Recommended Extensions         | Notes                                                                 |
| ----------------------- | ------------------------------ | --------------------------------------------------------------------- |
| **Visual Studio Code**  | CwTools, Paradox Highlight     | Free, powerful, and the most popular choice for Paradox modding.        |
| **IntelliJ IDEA**       | Paradox Language Support       | Community Edition is free and offers robust features.                 |
| **Notepad++**           | (Custom Language File)         | A lightweight alternative, suitable for minor edits.                  |

### 3.2. Creating a New Mod

All mods are located in the `Documents/Paradox Interactive/Europa Universalis V/mod` directory. Each mod must have its own subfolder. The basic structure of a mod is as follows:

```
/my_mod_name
├── .metadata/
│   └── metadata.json
├── in_game/
│   ├── common/
│   ├── events/
│   └── gui/
└── localization/
```

The `metadata.json` file is essential for the game to recognize and load the mod. It contains key information such as the mod's name, version, and dependencies. [3]

### 3.3. Debugging and Console Commands

EU5 includes a robust debug mode that is indispensable for mod development. To enable it, add the `-debug_mode` launch option in Steam. This provides access to the in-game console and enables hot-reloading, which applies script changes without restarting the game.

Key console commands for modders include:

*   `script_docs`: Generates documentation for effects, triggers, and scopes.
*   `dump_data_types`: Generates documentation for GUI scripting.
*   `error.log`: The primary log file for identifying script errors, located in `Documents/Paradox Interactive/Europa Universalis V/logs`.

## 4. Core Modding Concepts

EU5's scripting language revolves around a few core concepts: Triggers, Effects, and Scopes.

### 4.1. Triggers and Effects

*   **Triggers** are conditions that check the current game state. They are used to determine if an event can fire, an option is visible, or a decision can be taken. Triggers return a boolean value (true or false). [4]
*   **Effects** are commands that change the game state. They are used to apply modifiers, change country ownership, create characters, and more. [5]

Both triggers and effects can be *inline* (for simple operations) or *block* (for more complex logic) and are highly dependent on the current **scope**.

### 4.2. Scopes and Scope Links

A **scope** refers to the specific game object (e.g., a country, a character, a location) that a script is currently focused on. **Scope links** are used to access data from or apply effects to other scopes. For example, `c:FRA.gold` would access the treasury of the country with the tag FRA.

### 4.3. Script Values

Script values are used for mathematical calculations and creating dynamic numerical values. They can be defined as reusable named values in the `common/script_values/` folder or created inline within other scripts. They support a wide range of arithmetic and logical operators. [6]

## 5. Game Content Modding

This section covers the modding of specific game content types.

### 5.1. Events

Events are pop-up messages that present the player with information and choices. They are defined in `.txt` files within the `in_game/events/` folder. Unlike EU4, EU5 does not use `mean_time_to_happen` for events; all events must be fired explicitly through on_actions, decisions, or other scripts. [7]

### 5.2. Countries

Countries are defined in two parts: a **country definition** file in `in_game/setup/countries/` that sets the tag, color, and culture, and a **country setup** file in `<top_folder>/setup/start/` that defines the starting situation, including owned provinces, capital, and ruler. [8]

### 5.3. Localization

All text displayed to the player is handled through the localization system. Localization files are in `.yml` format and must be encoded in **UTF-8-BOM**. Each language has its own subfolder and file naming convention (e.g., `_l_english.yml`). The system supports dynamic text, color formatting, and icons. [9]

## 6. Advanced Modding Topics

### 6.1. Interface (GUI) Modding

The user interface is highly moddable through `.gui` files. The system is modular, using templates and types to create reusable UI components. Creating new windows and widgets allows for the development of complex new game features. [10]

### 6.2. Map Modding

EU5 includes a powerful map editor for modifying the game world. This tool allows for editing the heightmap, terrain textures, and location setup. However, it has high system requirements, recommending at least 32GB of RAM. [11]

### 6.3. Graphics Modding

Flags in EU5 are generated dynamically through a scripted coat of arms system, a significant change from the static `.tga` files of EU4. This allows for flags to change based on triggers and game conditions. [12]

## 7. Best Practices and Resources

*   **Use a proper IDE**: Tools like VS Code with the CwTools extension can catch errors and improve readability.
*   **Avoid Overwriting Vanilla Files**: Create your own files and use the `replace_paths` feature or specific load orders to override game content. This improves mod compatibility.
*   **Use Version Control**: Git is an invaluable tool for tracking changes and collaborating with others.
*   **Consult Community Resources**: The official EU5 Wiki, the Paradox Forums, and community Discord servers are essential resources for any modder.

## 8. Conclusion

The modding architecture of European Universalis 5 represents a significant evolution from previous Paradox titles. With the power of the updated Clausewitz Engine and the flexible Jomini scripting layer, modders have an unprecedented ability to create new content and transform the game. While the learning curve can be steep, the extensive documentation and active community provide a strong foundation for success.

## 9. References

[1] [Europa Universalis V - PC performance graphics benchmarks](https://en.gamegpu.com/test-gpu/rts-strategii/europa-universalis-v-test-gpu-cpu)
[2] [Grand Jomini Modding Information Manuscript](https://forum.paradoxplaza.com/forum/threads/grand-jomini-modding-information-manuscript.1170261/)
[3] [Mod structure - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Mod_structure)
[4] [Trigger - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Trigger)
[5] [Effect - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Effect)
[6] [Script value - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Script_value)
[7] [Event modding - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Event_modding)
[8] [Country modding - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Country_modding)
[9] [Localization - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Localization)
[10] [Interface modding guide - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Interface_modding_guide)
[11] [Map modding - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Map_modding)
[12] [Flag modding - Europa Universalis 5 Wiki](https://eu5.paradoxwikis.com/Flag_modding)

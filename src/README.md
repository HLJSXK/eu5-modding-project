# Source Files

This directory contains mod source files and templates for the EU5 Modding Project.

## Structure

### `template_mod/`

A minimal, ready-to-use mod template demonstrating EU5 modding best practices. This template includes only essential sample files to serve as a starting point for new mods.

**Contents:**
- **Proper metadata configuration** for multiplayer synchronization
- **Sample events** with detailed comments explaining EU5 event structure
- **Sample modifiers** demonstrating country and province patterns
- **Localization file** with correct UTF-8 BOM encoding
- **Comprehensive documentation** in the mod's README

**Usage:**
1. Copy the `template_mod/` directory to your EU5 mod folder:
   ```
   Documents/Paradox Interactive/Europa Universalis V/mod/
   ```
2. Rename it to your mod's name
3. Modify the files to create your custom mod
4. Update `metadata.json` with your mod's information

### `dynamic_missions/`

A complete, functional mod implementing a dynamic mission system for EU5. This serves as both a playable mod and a reference implementation for complex modding patterns.

**Features:**
- **Establish New City Mission** - Multi-stage city development system
- **Large Research Project Mission** - Research and innovation mechanics
- **Custom GUI** - Situation panels and interfaces
- **Full localization** - English and Simplified Chinese

**Usage:**
1. Copy the `dynamic_missions/` directory to your EU5 mod folder
2. Enable in the launcher to play with dynamic missions
3. Reference the code for advanced modding techniques

For detailed documentation, see the [Dynamic Missions Design](../docs/design/Dynamic_Missions_Design.md) documents.

## Creating New Mods

When creating a new mod:

1. **Start with the template**: Copy `template_mod/` as your base for simple mods
2. **Reference dynamic_missions**: Study `dynamic_missions/` for complex features
3. **Follow naming conventions**: Use a consistent prefix for all your files (e.g., `mymod_`)
4. **Use UTF-8-BOM encoding**: All `.yml` localization files must use UTF-8 with BOM
5. **Test frequently**: Enable debug mode in EU5 and test after each change
6. **Document your code**: Add comments explaining complex logic

## Guidelines

- Follow EU5 scripting conventions as documented in `/docs/technical/EU5_Mod_Framework_Guide.md`
- Reference the analysis in `/docs/technical/Mod_Structure_Analysis.txt` for common patterns
- Use the template as a starting point to ensure proper structure
- Keep your mod files organized by feature or system
- Test all changes in debug mode before releasing

## Resources

- [EU5 Modding Knowledge Base](../docs/technical/EU5_Modding_Knowledge_Base.md) - Comprehensive modding reference
- [EU5 Mod Framework Guide](../docs/technical/EU5_Mod_Framework_Guide.md) - Practical development framework
- [Template Mod README](template_mod/README.md) - Detailed template documentation
- [Dynamic Missions README](dynamic_missions/README.md) - Dynamic missions mod documentation
- [Dynamic Missions Framework](../docs/technical/Dynamic_Missions_Framework_Architecture.md) - Technical architecture


## Community Mod References

For additional learning resources, see the [Community Mod References](../reference_mods/) directory, which contains 12 real community mods from Steam Workshop. These mods provide:

- **Real-world examples** of mod structure and organization
- **Vanilla game variables** and definitions used in actual mods
- **Code patterns** from successful community mods
- **Different mod types** - translations, gameplay, UI, mechanics

Browse the [Reference Mods Index](../reference_mods/MOD_INDEX.md) for detailed information about each mod.

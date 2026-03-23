# Source Files

This directory contains mod source files and templates for the EU5 Modding Project.

## Structure

### `stable/`

The **stable branch** of the EU5 MP mod, based on reference mod **3644897537** (Amalgamation Synergy). This is the primary mod used in MP sessions, providing a well-tested set of gameplay balance tweaks.

**Features:**
- **War Mechanics** - Harsher war exhaustion, more impactful occupation
- **Anti-Snowballing** - Progressive build cost increases, halved base RGO size
- **Tax Efficiency** - Rebalanced tax efficiency system
- **Colonial Restrictions** - AI colonization limits, historical colonizer exceptions
- **Price Rebalancing** - Scaled gold transfers, adjusted diplomatic costs
- **Little Ice Age** - More forgiving ice age event penalties

**Status:** Active, stable — primary mod for MP sessions.

**Usage:**
1. Copy the `stable/` directory to your EU5 mod folder:
   ```
   Documents/Paradox Interactive/Europa Universalis V/mod/
   ```
2. Enable in the launcher

For detailed documentation, see [stable/README.md](stable/README.md).

### `develop/`

The **development branch** of the EU5 MP mod, formerly known as `dynamic_missions`. This mod implements a dynamic mission system and is currently under development pause.

**Features:**
- **Establish New City Mission** - Multi-stage city development system
- **Large Research Project Mission** - Research and innovation mechanics
- **Custom GUI** - Situation panels and interfaces
- **Full localization** - English and Simplified Chinese

**Status:** Development paused — kept for future reference and resumption.

For detailed documentation, see the [Dynamic Missions Design](../docs/design/Dynamic_Missions_Design.md) documents.

### Mod Base Choice

For new work, choose one of the maintained bases:

- **`stable/`** for production-ready multiplayer balance changes
- **`develop/`** for dynamic mission systems and advanced scripted workflows

**Usage:**
1. Copy either `stable/` or `develop/` to your EU5 mod folder:
   ```
   Documents/Paradox Interactive/Europa Universalis V/mod/
   ```
2. Rename the copied directory to your mod's name
3. Modify the files to create your custom mod
4. Update `.metadata/metadata.json` with your mod's information

## Dual-Mod Strategy

As of 2026-03-23, the project maintains two parallel mods:

| Mod | Directory | Status | Focus |
|-----|-----------|--------|-------|
| Stable | `src/stable/` | Active | Game balance (based on ref mod 3644897537) |
| Develop | `src/develop/` | Paused | Dynamic mission system |

This is a temporary measure while dynamic mission development is deferred. The `stable` mod provides the core MP balance experience, while `develop` is preserved for future resumption.

## Creating New Mods

When creating a new mod:

1. **Start with stable**: Copy `stable/` as your base for reliable gameplay mods
2. **Reference develop**: Study `develop/` for complex features
3. **Follow naming conventions**: Use a consistent prefix for all your files (e.g., `mymod_`)
4. **Use UTF-8-BOM encoding**: All `.yml` localization files must use UTF-8 with BOM
5. **Test frequently**: Enable debug mode in EU5 and test after each change
6. **Document your code**: Add comments explaining complex logic

## Guidelines

- Follow EU5 scripting conventions as documented in `/docs/technical/EU5_Mod_Framework_Guide.md`
- Reference the analysis in `/docs/technical/Mod_Structure_Analysis.txt` for common patterns
- Use `stable/` as a clean, maintained starting point
- Keep your mod files organized by feature or system
- Test all changes in debug mode before releasing

## Resources

- [EU5 Modding Knowledge Base](../docs/technical/EU5_Modding_Knowledge_Base.md) - Comprehensive modding reference
- [EU5 Mod Framework Guide](../docs/technical/EU5_Mod_Framework_Guide.md) - Practical development framework
- [Stable Mod README](stable/README.md) - Stable mod documentation
- [Develop Mod README](develop/README.md) - Dynamic missions mod documentation
- [Dynamic Missions Framework](../docs/technical/Dynamic_Missions_Framework_Architecture.md) - Technical architecture


## Community Mod References

For additional learning resources, see the [Community Mod References](../reference_mods/) directory, which contains community mods from Steam Workshop. These mods provide:

- **Real-world examples** of mod structure and organization
- **Vanilla game variables** and definitions used in actual mods
- **Code patterns** from successful community mods
- **Different mod types** - translations, gameplay, UI, mechanics

Browse the [Reference Mods Index](../reference_mods/MOD_INDEX.md) for detailed information about each mod.

# Source Files

This directory contains mod source files and templates for the EU5 Modding Project.

## Structure

### `template_mod/`

A complete, ready-to-use mod template demonstrating EU5 modding best practices. This template includes:

- **Proper metadata configuration** for multiplayer synchronization
- **Sample events** with detailed comments explaining EU5 event structure
- **Sample modifiers** demonstrating country, province, and timed patterns
- **Localization files** with correct UTF-8 BOM encoding
- **Comprehensive documentation** in the mod's README

**Usage:**
1. Copy the `template_mod/` directory to your EU5 mod folder:
   ```
   Documents/Paradox Interactive/Europa Universalis V/mod/
   ```
2. Rename it to your mod's name
3. Modify the files to create your custom mod
4. Update `metadata.json` with your mod's information

## Creating New Mods

When creating a new mod:

1. **Start with the template**: Copy `template_mod/` as your base
2. **Follow naming conventions**: Use a consistent prefix for all your files (e.g., `mymod_`)
3. **Use UTF-8-BOM encoding**: All `.yml` localization files must use UTF-8 with BOM
4. **Test frequently**: Enable debug mode in EU5 and test after each change
5. **Document your code**: Add comments explaining complex logic

## Guidelines

- Follow EU5 scripting conventions as documented in `/docs/EU5_Mod_Framework_Guide.md`
- Reference the analysis in `/docs/Mod_Structure_Analysis.txt` for common patterns
- Use the template as a starting point to ensure proper structure
- Keep your mod files organized by feature or system
- Test all changes in debug mode before releasing

## Resources

- [EU5 Modding Knowledge Base](../docs/EU5_Modding_Knowledge_Base.md) - Comprehensive modding reference
- [EU5 Mod Framework Guide](../docs/EU5_Mod_Framework_Guide.md) - Practical development framework
- [Template Mod README](template_mod/README.md) - Detailed template documentation

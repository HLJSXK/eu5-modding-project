# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-01-22

### Added
- **Steam Account Name Configuration**: Users can now set custom account names for LAN multiplayer sessions
  - New `--account-name` flag for eu5-deployer
  - Default account name: "EU5Player"
  - Creates `force_account_name.txt` in steam_settings folder

- **Input Validation**: Added validation function for account names
  - Account name: 1-32 characters

### Changed
- Updated deployment workflow to include Steam settings configuration as Step 0
- Enhanced deployer package with new configuration functions:
  - `ConfigureSteamSettings()` - Main configuration function
  - `ValidateAccountName()` - Validates account name format

### Documentation
- Updated `docs/Goldberg_Emulator_Guide.md` with account name configuration instructions
- Updated `docs/Tools_Guide.md` with new command-line flags and usage examples
- Updated `docs/Quick_Start_Guide.md` with customization instructions and multi-player setup guide

### Technical Details
- Added `strings` package to deployer
- Template files created in `goldberg_emulator/steam_settings/`:
  - `force_account_name.txt` (default: "EU5Player")

## [1.0.0] - 2026-01-21

### Initial Release
- EU5 installation detector
- Goldberg Emulator deployment tool
- Automatic backup and restore functionality
- Cross-platform support (Windows, Linux, macOS)
- DLC configuration support
- Mods folder support

---

**Project Repository:** https://github.com/HLJSXK/eu5-modding-project  
**Goldberg Emulator:** https://gitlab.com/Mr_Goldberg/goldberg_emulator

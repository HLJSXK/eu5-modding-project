# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-01-22

### Added
- **Steam Account Name Configuration**: Users can now set custom account names for LAN multiplayer sessions
  - New `--account-name` flag for eu5-deployer
  - Default account name: "EU5Player"
  - Creates `force_account_name.txt` in steam_settings folder
  
- **Steam ID Configuration**: Users can now set custom Steam IDs to avoid conflicts in multiplayer
  - New `--steam-id` flag for eu5-deployer
  - Default Steam ID: "76561197960287930"
  - Creates `force_steamid.txt` in steam_settings folder
  - Validates Steam ID format (17 digits starting with 7656119)

- **Input Validation**: Added validation functions for account names and Steam IDs
  - Account name: 1-32 characters
  - Steam ID: Must be exactly 17 digits and start with "7656119"

### Changed
- Updated deployment workflow to include Steam settings configuration as Step 0
- Enhanced deployer package with new configuration functions:
  - `ConfigureSteamSettings()` - Main configuration function
  - `ValidateAccountName()` - Validates account name format
  - `ValidateSteamID()` - Validates Steam ID format

### Documentation
- Updated `docs/Goldberg_Emulator_Guide.md` with detailed account name and Steam ID configuration instructions
- Updated `docs/Tools_Guide.md` with new command-line flags and usage examples
- Updated `docs/Quick_Start_Guide.md` with customization instructions and multi-player setup guide
- Added examples for generating unique Steam IDs for multiple players

### Technical Details
- Added `regexp` and `strings` packages to deployer
- Template files created in `goldberg_emulator/steam_settings/`:
  - `force_account_name.txt` (default: "EU5Player")
  - `force_steamid.txt` (default: "76561197960287930")

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

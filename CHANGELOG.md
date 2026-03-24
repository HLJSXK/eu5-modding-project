# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- Synced vanilla reference files under `reference_game_files/` to EU5 version 1.1.10.
- Updated documentation to reflect the new reference baseline.

## [2.0.0] - 2026-03-24

### Changed
- Repository scope is now mod development only.
- Online multiplayer tooling moved to a separate repository:
  - https://github.com/HLJSXK/eu5-online-tools

### Removed
- Local online deployment and sync code from this repository.
- Go toolchain and online tool build artifacts from this repository.

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

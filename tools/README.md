# Development Tools

This directory contains helper scripts and utilities for EU5 mod development and LAN multiplayer setup.

## Available Tools

### 1. detect_eu5_folder.py

**Purpose:** Automatically detect EU5 installation directory by searching common Steam library locations.

**Usage:**
```bash
python3 tools/detect_eu5_folder.py
```

**Features:**
- Cross-platform support (Windows, Linux, macOS)
- Searches common Steam library paths
- Parses Steam's `libraryfolders.vdf` to find all library locations
- Validates EU5 installation by checking for key files
- Outputs machine-readable format for scripting

**Output:**
```
Detecting EU5 installation on Linux...
Checking Steam library: /home/user/.steam/steam

✓ Found EU5 installation: /home/user/.steam/steam/steamapps/common/Europa Universalis V

EU5 Main Folder: /home/user/.steam/steam/steamapps/common/Europa Universalis V
Binaries Folder: /home/user/.steam/steam/steamapps/common/Europa Universalis V/binaries

__EU5_PATH__=/home/user/.steam/steam/steamapps/common/Europa Universalis V
__BINARIES_PATH__=/home/user/.steam/steam/steamapps/common/Europa Universalis V/binaries
```

### 2. deploy_goldberg.py

**Purpose:** Deploy Goldberg Steam Emulator to EU5 installation for LAN multiplayer.

**Usage:**
```bash
# Auto-detect EU5 installation
python3 tools/deploy_goldberg.py

# Specify EU5 path manually
python3 tools/deploy_goldberg.py --eu5-path "/path/to/Europa Universalis V"

# Restore original files
python3 tools/deploy_goldberg.py --restore
```

**Features:**
- Automatic EU5 installation detection
- Backs up original `steam_api64.dll` before replacement
- Deploys Goldberg DLL and steam_settings folder
- Safe restoration of original files
- Detailed progress reporting

**What it does:**
1. Validates EU5 installation path
2. Creates backup of original `steam_api64.dll`
3. Copies Goldberg `steam_api64.dll` to binaries folder
4. Copies `steam_settings` folder (including DLC.txt and mods)
5. Reports deployment status

**Restoration:**
```bash
python3 tools/deploy_goldberg.py --restore
```

This will:
- Restore original `steam_api64.dll` from backup
- Remove `steam_settings` folder
- Return EU5 to normal Steam functionality

## Tool Development Guidelines

When adding new tools to this directory:

1. **Use Python 3.11+** for consistency with the project environment
2. **Include shebang:** `#!/usr/bin/env python3`
3. **Add docstrings:** Document purpose, usage, and parameters
4. **Make executable:** `chmod +x tool_name.py`
5. **Update this README:** Add documentation for the new tool
6. **Handle errors gracefully:** Provide clear error messages
7. **Support cross-platform:** Test on Windows, Linux, and macOS if applicable

## Dependencies

All tools use Python standard library only. No external dependencies required.

## Future Tools

Planned tools for future development:

- **mod_validator.py** - Validate mod structure and syntax
- **dlc_finder.py** - Automatically find EU5 DLC IDs from Steam
- **launcher_gui.py** - Graphical launcher for easy LAN setup
- **n2n_manager.py** - Manage n2n VPN connections for virtual LAN

## Contributing

When contributing new tools:

1. Follow the existing code style
2. Add comprehensive documentation
3. Test on multiple platforms if possible
4. Update this README with usage instructions

---

**Last Updated:** January 22, 2026

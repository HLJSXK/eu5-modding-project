# European Universalis 5 Modding Project

A comprehensive toolkit for **European Universalis 5** modding and LAN multiplayer setup.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Go Version](https://img.shields.io/badge/go-1.25+-00ADD8.svg)](https://golang.org)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/HLJSXK/eu5-modding-project)

## Overview

This project provides tools and documentation for EU5 modding and multiplayer setup, with a focus on enabling LAN multiplayer through Goldberg Steam Emulator. All tools are compiled as standalone executables requiring no runtime dependencies.

**Key Features:**
- 🎮 One-click LAN multiplayer setup
- 🔧 Automatic EU5 installation detection
- 💾 Safe backup and restoration
- 📦 Zero dependencies - standalone executables
- 🌐 Cross-platform support (Windows, Linux, macOS)
- 📚 Comprehensive modding documentation

## Quick Start

### For LAN Multiplayer

**Windows Users:**
1. Download the [latest release](https://github.com/HLJSXK/eu5-modding-project/releases) or clone this repository
2. Run `build\eu5-tools-windows-amd64\eu5-sync-ui.exe`
3. Complete deployment and mod sync in the UI, then launch EU5

**CLI (optional):**
```bash
go run ./cmd/eu5-deployer --restore
```

See the [Quick Start Guide](docs/guides/Quick_Start_Guide.md) for detailed instructions.

### For Modding

1. Clone this repository:
   ```bash
   git clone https://github.com/HLJSXK/eu5-modding-project.git
   cd eu5-modding-project
   ```

2. Read the [EU5 Modding Knowledge Base](docs/technical/EU5_Modding_Knowledge_Base.md)

3. Set up your development environment:
   - Install Visual Studio Code with CwTools extension
   - Enable debug mode in EU5 (`-debug_mode` launch option)

4. Use `src/stable/` as a practical baseline, and `src/develop/` for advanced dynamic mission patterns

## Documentation

### User Guides
- **[Quick Start Guide](docs/guides/Quick_Start_Guide.md)** - Fast setup for LAN multiplayer (中文)
- **[Tools Guide](docs/guides/Tools_Guide.md)** - Complete guide for deployment tools (中文)
- **[Project User Guide](docs/guides/Project_User_Guide.md)** - Project overview and features (中文)

### Technical Documentation
- **[EU5 Modding Knowledge Base](docs/technical/EU5_Modding_Knowledge_Base.md)** - Comprehensive modding reference
- **[EU5 Mod Framework Guide](docs/technical/EU5_Mod_Framework_Guide.md)** - Practical development framework
- **[Goldberg Emulator Guide](docs/technical/Goldberg_Emulator_Guide.md)** - Detailed setup and configuration

- **[Community Mod References](reference_mods/README.md)** - 12 community mods for learning and reference

### Design & Development
- **[Dynamic Missions Design](docs/design/Dynamic_Missions_Design.md)** - Complete dynamic mission system design and implementation
- **[Documentation Index](docs/README.md)** - Complete documentation structure

### Component Documentation
- **[Tools README](tools/README.md)** - Development tools documentation
- **[Source README](src/README.md)** - Mod source structure
- **[Assets README](assets/README.md)** - Graphics and media files

## Project Structure

```
eu5-modding-project/
├── cmd/                    # Executable source code
│   ├── eu5-detector/      # EU5 installation detector
│   ├── eu5-deployer/      # Goldberg deployment tool
│   ├── eu5-modsync/       # Mod publish/sync tool
│   └── eu5-sync-ui/       # Windows sync UI
├── pkg/                    # Shared Go packages
│   ├── detector/          # Detection logic
│   ├── deployer/          # Deployment logic
│   └── modsync/           # Mod sync logic
├── goldberg_emulator/     # Goldberg Emulator files
│   ├── steam_api64.dll    # Goldberg DLL
│   └── steam_settings/    # Configuration files
├── docs/                   # Documentation
│   ├── guides/            # User guides (Chinese)
│   ├── technical/         # Technical documentation
│   ├── design/            # Design documents
│   ├── task_summaries/    # Implementation summaries
│   └── README.md          # Documentation index
├── src/                    # Mod source files
│   ├── stable/            # Active multiplayer balance mod
│   └── develop/           # Dynamic missions development branch
├── reference_mods/       # Community mod examples
├── assets/                 # Graphics and media
├── tools/                  # Development utilities
├── build.sh               # Build script (Linux/macOS)
└── build.bat              # Build script (Windows)
```

## Available Tools

| Tool | Description | Windows | Linux | macOS |
|------|-------------|---------|-------|-------|
| **eu5-sync-ui** | One-click Windows UI for Goldberg deploy + mod sync | `build\eu5-tools-windows-amd64\eu5-sync-ui.exe` | - | - |
| **eu5-deployer** | Deploy or restore Goldberg files | `go run ./cmd/eu5-deployer` | `go run ./cmd/eu5-deployer` | `go run ./cmd/eu5-deployer` |
| **eu5-detector** | Detect EU5 installation location | `go run ./cmd/eu5-detector` | `go run ./cmd/eu5-detector` | `go run ./cmd/eu5-detector` |
| **eu5-modsync** | Publish/sync local mods via snapshot manifest | `go run ./cmd/eu5-modsync` | `go run ./cmd/eu5-modsync` | `go run ./cmd/eu5-modsync` |

Release artifacts include standalone executables. In this repository, `build.bat`/`build.sh` currently package the Windows Sync UI bundle.

## Building from Source

### Prerequisites
- Go 1.25 or higher
- Git

### Build Instructions

**Windows:**
```cmd
build.bat
```

**Linux/macOS:**
```bash
chmod +x build.sh
./build.sh
```

Build output is placed in the `build/` directory, including `eu5-tools-windows-amd64.zip` and `eu5-tools-windows-amd64/`.

## Game Information

- **Game:** European Universalis 5
- **Release Date:** November 2025
- **Engine:** Clausewitz Engine (updated)
- **Scripting:** Jomini scripting layer
- **Platform:** PC (Steam)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is for educational and modding purposes. European Universalis 5 is a trademark of Paradox Interactive.

## Links

- **Repository:** https://github.com/HLJSXK/eu5-modding-project
- **Issues:** https://github.com/HLJSXK/eu5-modding-project/issues
- **EU5 Wiki:** https://eu5.paradoxwikis.com/
- **Goldberg Emulator:** https://gitlab.com/Mr_Goldberg/goldberg_emulator

## Acknowledgments

- Paradox Interactive for European Universalis 5
- [Goldberg Steam Emulator](https://gitlab.com/Mr_Goldberg/goldberg_emulator) by Mr_Goldberg
- EU5 modding community

---

**Last Updated:** March 2026  
**Project Status:** Active Development  
**Version:** 1.0.0

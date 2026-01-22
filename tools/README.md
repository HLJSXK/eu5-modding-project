# Development Tools

This directory contains legacy Python scripts for reference. **For production use, please use the Go-based tools in the `build/` directory.**

## Current Tools (Go-based)

The project now uses Go-based tools that compile to standalone executables:

- **eu5-deployer** - Deploy Goldberg Emulator for LAN multiplayer
- **eu5-detector** - Detect EU5 installation location

See the [Tools Guide](../docs/Tools_Guide.md) for complete documentation.

## Legacy Tools (Python)

These Python scripts are kept for reference and development purposes:

### detect_eu5_folder.py

**Status:** Superseded by Go implementation  
**Purpose:** Detect EU5 installation directory

### deploy_goldberg.py

**Status:** Superseded by Go implementation  
**Purpose:** Deploy Goldberg Emulator to EU5

## Migration

The project has migrated from Python to Go for the following benefits:

- **Zero dependencies** - No Python installation required
- **Single executable** - Easy distribution
- **Fast startup** - Native machine code
- **Cross-platform** - Compile once, run anywhere

## For Developers

If you want to modify the tools:

1. Edit the Go source code in `cmd/` and `pkg/` directories
2. Build using `build.sh` (Linux/macOS) or `build.bat` (Windows)
3. Test the compiled executables in `build/` directory

See the main [README](../README.md) for build instructions.

---

**Note:** The Python scripts may be removed in a future version once the Go implementation is fully stable.

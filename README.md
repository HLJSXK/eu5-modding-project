# EU5 Modding Project

This repository now focuses on EU5 mod development only.

## Scope

- Mod source development (`src/stable`, `src/sol_standalone`, and compatibility targets under `src/`)
- Modding knowledge base and design documents
- Community and vanilla reference files for research

## Repository Split Notice

Online multiplayer tooling has been split into a separate repository:

- https://github.com/HLJSXK/eu5-online-tools

This repository keeps only mod-related content and documentation.

## Quick Start (Modding)

1. Clone repository
2. Use `src/stable/` as the full stable mod target
3. Use `src/sol_standalone/` for the SOL-only standalone target
4. Use `src/sol_pp_compatibility_submod/` for the SOL / Prosper or Perish compatibility layer
5. Use `src/sol_mnt_compatibility_submod/` for the SOL / MEIOU and Taxes compatibility layer
6. Use `src/sol_jtg_compatibility_submod/` for the SOL / Just Trade Goods compatibility layer
7. The full `stable` target contains a self-contained Glorp UI-based location window; Glorp UI and Construction Manager are not required
8. Read technical docs in `docs/technical/`

## Build / Deploy

Mod release versions use the local calendar date in six-digit `YYMMDD` form
(for example, `260726` for 2026-07-26). `build.bat` stamps the selected
target metadata automatically before generation and deployment. This is
independent of `supported_game_version`, which continues to track EU5.

Generated SOL sources are refreshed automatically before validation/deploy.
To run the generation chain without deploying:

```cmd
python scripts\gen_sol_chain.py --target all
python scripts\gen_sol_chain.py --target all --check
```

For the default deployment of stable, SOL standalone, and all compatibility
compatibility submods, run:

```cmd
build.bat
```

This regenerates and mirrors all active targets into the EU5 game mod folder.
Compatibility targets may be installed together, but only the one matching the
active overhaul should be enabled because they replace shared SOL effects. To
deploy only the full stable target, run:

```cmd
build.bat stable
```

For the SOL standalone deployment, run:

```cmd
build.bat sol_standalone
```

This mirrors `src\sol_standalone\` into the EU5 game mod folder.

For the SOL / Prosper or Perish compatibility submod, run:

```cmd
build.bat sol_pp_compatibility_submod
```

This mirrors `src\sol_pp_compatibility_submod\` into the EU5 game mod folder.

For the SOL / MEIOU and Taxes compatibility submod, run:

```cmd
build.bat sol_mnt_compatibility_submod
```

This mirrors `src\sol_mnt_compatibility_submod\` into the EU5 game mod folder.

For the SOL / Just Trade Goods compatibility submod, run:

```cmd
build.bat sol_jtg_compatibility_submod
```

This mirrors `src\sol_jtg_compatibility_submod\` into the EU5 game mod folder.

To build all targets, run:

```cmd
build.bat all
```

This mirrors the selected `src/<target>/` into the existing EU5 mod folder with
`robocopy /MIR` so debug hot reload can keep watching the same target directory:

`C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod\<target>`

Builds no longer write archives into the repository `build\` folder.

If write permission is denied, run terminal as Administrator.

## Main Directories

- `src/` - Active mod source files
- `docs/` - Modding documentation and design notes
- `reference_official_defines/` - Official define/type references for EU5 syntax verification
- `reference_game_files/` - Vanilla reference assets
- `reference_mods/` - Community mod references
- `assets/` - Images and media assets

## Documentation

- `docs/README.md` - Documentation index
- `docs/guides/AI_Tool_Workflow_Prompt.md` - AI tool prompt and EU5 syntax verification workflow
- `docs/technical/EU5_Modding_Knowledge_Base.md`
- `docs/technical/EU5_Mod_Framework_Guide.md`
- `docs/archive/dynamic_missions/Dynamic_Missions_Design.md` (paused)
- `src/README.md`

## License

This project is for educational and modding purposes. European Universalis 5 is a trademark of Paradox Interactive.

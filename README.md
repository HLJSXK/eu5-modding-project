# EU5 Modding Project

This repository now focuses on EU5 mod development only.

## Scope

- Mod source development (`src/stable`, `src/sol_standalone`, `src/sol_pp_compatibility_submod`)
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
5. Read technical docs in `docs/technical/`

## Build / Deploy

Generated SOL sources are refreshed automatically before validation/deploy.
To run the generation chain without deploying:

```cmd
python scripts\gen_sol_chain.py --target all
python scripts\gen_sol_chain.py --target all --check
```

For the default deployment of stable, SOL standalone, and the SOL / Prosper or
Perish compact compatibility submod, run:

```cmd
build.bat
```

This regenerates and mirrors all three active targets into the EU5 game mod
folder. To deploy only the full stable target, run:

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

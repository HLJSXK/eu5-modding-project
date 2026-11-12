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

To run the build's generation and full validation without deployment:

```cmd
build.bat --validate-only
```

The build prints its Python and validator paths and retains validation output in
`tmp/build_validate.log`. Set `EU5_PYTHON` to the eu5 environment's `python.exe`
to select it explicitly; otherwise the active eu5 environment or the user's
Anaconda eu5 environment is used.

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
- `.eu5-base/reference_official_defines/` - Official define/type references for EU5 syntax verification
- `.eu5-base/reference_game_files/` - Vanilla reference assets
- `.eu5-base/reference_mods/` - Community mod references
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
## Shared EU5 foundation

Reusable EU5 references, official definitions, community-mod snapshots, game knowledge, GUI rendering, and shared AI rules live in the sibling `eu5-modding-base` project. Run `python scripts/bootstrap_base.py` after cloning to connect `.eu5-base/`, then read [the shared agent entry](.eu5-base/CLAUDE.md) and this project's `CLAUDE.md`. The project's own source, generated indexes, design notes, and workflow remain here.

## Command-line Workshop publishing

Run `workshop.ps1` from this repository; no uploader source checkout or expanded
workspace is needed. The default target is the main Mod. `-List` shows all targets.

```powershell
.\workshop.ps1 -List
# One-time binding: replace the example number with YOUR existing Workshop item ID.
.\workshop.ps1 -Init -ItemId 1234567890
# Offline profile/file check; does not upload or rebuild.
.\workshop.ps1
# After running this project's build.bat successfully:
.\workshop.ps1 -Upload
```

Select a different target with the first argument, e.g. `-List` shows the aliases
to use with `-Init -ItemId ...` and later `-Upload`. Every target needs its own ID.
Do not use the old 1.3 item's ID for a separate 1.4 item. ID 0/new-item creation
is intentionally unsupported. To change a binding, edit `.workshop/<target>.json`.

The wrapper uploads the selected source Mod directory (including generated files),
not the whole repository or a potentially stale game installation. Run the existing
build first: Great Projects supports `build.bat --package-only`; SOL supports
`build.bat stable` or its other existing target names. The wrapper does not build,
validate gameplay, check Steam ownership, or verify that a build is current.

Install the **Windows CLI**, not GUI, distribution of
[pdx-workshop-manager](https://github.com/kaiser-chris/pdx-workshop-manager/releases)
by putting `pdx-workshop-manager.exe` and `steam_api64.dll` in `.workshop/bin/`.
Alternatively set `PDX_WORKSHOP_MANAGER` or pass `-Executable` with the CLI path.
No Go SDK or Steamworks SDK is needed. Keep Steam running and logged in for upload.
If local PowerShell policy blocks the script, invoke it using
`powershell -NoProfile -ExecutionPolicy Bypass -File .\workshop.ps1` plus the flags;
this affects that invocation only. It does not override organization policy.

Profiles, the binary and upload logs are ignored by Git. Paths in the profile are
resolved relative to this repository, even when called from a different directory.
Checks print the target, title, version, item ID and content path. Upload runs retain
their resolved configuration and logs under `.workshop/runs/`. The wrapper also
detects upstream's zero-exit-code error case by requiring its success log marker.

By default, upstream updates content, the English title from metadata, tags, and
thumbnail. Descriptions and change notes are opt-in: add `descriptions` and/or
`change-note-directories` maps to the single Mod entry in the local profile, with
language keys such as `english` and `schinese` and paths relative to this repository.
Change-note filenames must match `<metadata version>.bbcode`. Existing localized
titles can be set with a `names` map. Description files are uploaded verbatim;
the wrapper does not convert Markdown to BBCode. Review their contents first.
SOL descriptions: docs/workshop_description_en.txt and docs/workshop_description_zh.txt (use english and schinese respectively).

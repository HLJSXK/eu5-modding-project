# EU5 Modding Project

This repository now focuses on EU5 mod development only.

## Scope

- Mod source development (`src/stable`, `src/develop`)
- Modding knowledge base and design documents
- Community and vanilla reference files for research

## Repository Split Notice

Online multiplayer tooling has been split into a separate repository:

- https://github.com/HLJSXK/eu5-online-tools

This repository keeps only mod-related content and documentation.

## Quick Start (Modding)

1. Clone repository
2. Use `src/stable/` as baseline for practical balance mods
3. Use `src/develop/` for active Dynamic Missions development
4. Read technical docs in `docs/technical/`

## Build / Deploy (Stable)

For a simple local deployment, run:

```cmd
build.bat
```

This also creates `build\stable.zip`.

For optional upload to Tencent COS (`modsync/packages/stable.zip`), run:

```cmd
build.bat --upload-cos --cos-bucket <bucket-name> --cos-region <region>
```

Credentials can come from either arguments or environment variables:

- `--cos-secret-id` / `--cos-secret-key`
- `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY`

Bucket and region can also come from environment variables:

- `TENCENT_COS_BUCKET`
- `TENCENT_COS_REGION`

This copies `src/stable/` to:

`C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod\stable`

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
- `docs/design/Dynamic_Missions_Design.md`
- `src/README.md`

## License

This project is for educational and modding purposes. European Universalis 5 is a trademark of Paradox Interactive.

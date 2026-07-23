# Source Files

This directory contains deployable EU5 mod source targets.

## Targets

### `stable/`

The full stable mod used for MP balance work. It includes the broader gameplay balance package, including SOL, war/economy balance, UI, and supporting systems.

### `sol_standalone/`

Standalone Standard of Living target. It keeps only the SOL income and demand pipeline plus the related UI:

- calibrated pop-demand baseline
- location income and liquid-funds calculations
- market unit-spending cache
- monthly `local_pop_demand` modifier application
- Global Living Standard situation panel
- SOL map mode and location tooltip

It excludes non-SOL systems from `stable`, including war balance, migration compatibility events, CMM toggles, age escalation, GDP-to-development, diplomacy costs, and difficulty rebalance.

### `sol_pp_compatibility_submod/`

Compatibility layer loaded after Prosper or Perish and `stable`. It removes the
SOL residuals from PP's Little Ice Age/weather handling, zeros final lumber pop
demand, includes PP victuals in SOL living-standard spending, and overrides the
location and situation goods panels. It is generated from the current stable
SOL files and the checked-in PP reference.

Generated SOL files are refreshed through `scripts/gen_sol_chain.py`; build runs
that chain automatically for the selected target before validation/deploy.

Its freely named game-data and GUI files use the `zz_` load-order prefix. The
`global_living_standard.gui` situation panel keeps its exact filename because
EU5 binds that file name to the `global_living_standard` situation ID.

### `sol_mnt_compatibility_submod/`

Final-loading compatibility layer for MEIOU and Taxes and full SOL. M&T owns
economic balance, goods prices and non-demand fields, production, food, RGO,
buildings, and estate maintenance. The layer replaces the seven SOL pop-demand
quantities with M&T-price-scaled values, removes wealth/development gates, and
keeps SOL's demand accounting and Living Standard UI synchronized. Exact-path
overrides reduce the SOL CMM values and scripted GUI callbacks to the settings
that remain active, so discarded economic controls leave no variable warnings.

The generated EPBM replacement preserves M&T's country totals and deductions
while caching attributable domestic maintenance on the five existing SOL
location variables. Its `location_window.gui` starts from M&T and adds only the
SOL income display and Living Standard button. This target is mutually
exclusive with other SOL compatibility submods.

### `sol_jtg_compatibility_submod/`

Compatibility layer loaded after all five Just Trade Goods mods and `stable`.
It applies SOL's approximate per-stratum demand scaling to the 22 new goods with
direct pop demand, adds their final quantities to SOL's market and country
spending caches, and rebuilds both goods panels with all 77 demand goods.

The target relies on JTG localization and DDS assets instead of copying them.
Just Spices must be enabled manually because its metadata ID is empty. This
target is mutually exclusive with `sol_pp_compatibility_submod` because both
replace the same two SOL scripted effects.

The standalone `location_window.gui` override is generated from the vanilla
reference by `scripts/generate_sol_location_window.py`, which is called by the
chain for `sol_standalone` and `all`.

## Build

From the repository root:

```cmd
build.bat stable
build.bat sol_standalone
build.bat sol_pp_compatibility_submod
build.bat sol_mnt_compatibility_submod
build.bat sol_jtg_compatibility_submod
build.bat all
```

Each target deploys to the EU5 game mod folder under its own target name. Normal builds do not write archives into the repository `build\` folder.

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

The standalone `location_window.gui` override is generated from the vanilla reference by `scripts/generate_sol_location_window.py`; build runs this automatically for `sol_standalone` and `all`.

## Build

From the repository root:

```cmd
build.bat stable
build.bat sol_standalone
build.bat all
```

Each target deploys to the EU5 game mod folder under its own target name. Normal builds do not write archives into the repository `build\` folder.

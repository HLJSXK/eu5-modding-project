# SOL Standalone

This deployment target contains only the Standard of Living income and demand pipeline, plus the related SOL UI:

- calibrated pop demand baseline
- market unit-spending cache
- location income and liquid-funds calculation
- monthly `local_pop_demand` location modifier
- Global Living Standard situation panel
- SOL map mode and location tooltip

It intentionally excludes the broader stable mod systems such as war balance, migration compatibility events, CMM toggles, age escalation, GDP-to-development, diplomacy costs, difficulty rebalance, and other non-SOL economy tweaks.

## Generated Files

`in_game/gui/location_window.gui` is generated from the vanilla reference file:

```cmd
python scripts/generate_sol_location_window.py
```

The generator copies `reference_game_files/game/in_game/gui/location_window.gui`
and injects only the SOL income display and living-standard tooltip button.
`build.bat sol_standalone` and `build.bat all` run this generator automatically.

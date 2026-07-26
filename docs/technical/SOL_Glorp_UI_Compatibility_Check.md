# SOL / Construction Manager / Glorp UI Compatibility Check

Audit date: 2026-07-26

## Scope

- Standard of Living `1.3.11` (`hades.sol`)
- Workshop `3736668860`: Construction Manager `2.2.11`
- Workshop `3601047146`: Glorp UI `1.3.10.1`

## Conflict audit

SOL has only one active same-path file overlap with either UI mod:

```text
in_game/gui/location_window.gui
```

EU5 replaces that GUI file as a whole. A vanilla-based SOL window would discard
Glorp UI's layout, while Glorp UI loaded after SOL would remove the SOL income
display and Living Standard entry.

The Glorp source window is not self-contained by itself. It expects:

- vanilla location-window types extracted into
  `gui/vanilla/cmfg_location_window_vanilla_types.gui`;
- the shared Glorp/CM `zoom_to_button` type;
- Construction Manager widgets, scripted GUIs, and the
  `cm_best_town_right` map mode.

The common non-GUI object names are only CMF dispatcher on-actions and Glorp's
`monthly_country_pulse`; SOL does not copy those objects. No localization-key
collisions were found.

## Built-in integration

The full `src/stable/` target uses Glorp UI only as a checked-in source
reference. Glorp UI and Construction Manager are not runtime dependencies.

`scripts/sync_location_window.py` produces a self-contained result by:

1. copying Glorp UI's extracted vanilla location types into SOL at the same
   relative path;
2. replacing `zoom_to_button` with the SOL-owned `sol_zoom_to_button` type;
3. removing Construction Manager auto-food/auto-expand widgets, upgrade
   callbacks, and town-rights mapmode actions;
4. replacing `Location.GetTotalIncome` with SOL's `local_sol_total_income`;
5. inserting the SOL Living Standard tooltip button before the migration
   spacer;
6. failing generation if any `glorpui_*` or `cm_*` runtime reference remains.

The source metadata and CM markers are still checked for reference drift. Those
checks do not create mod dependencies.

## Runtime requirements

Only Community Mod Framework remains a formal dependency of full SOL. Neither
Workshop `3601047146` nor `3736668860` is required for the Built-in window.

If either UI mod is enabled separately, `location_window.gui` remains an exact
whole-file load-order conflict. Loading SOL last keeps the self-contained SOL
window; CM-only location automation controls are intentionally not bundled.

## Target notes

- `src/stable/`: self-contained Glorp UI-based window is an integrated feature.
- `src/sol_standalone/`: remains vanilla-based.
- SOL-PP and SOL-JTG do not replace `location_window.gui`, so they retain the
  stable Built-in window.
- SOL-M&T supplies its own M&T-based final location window.

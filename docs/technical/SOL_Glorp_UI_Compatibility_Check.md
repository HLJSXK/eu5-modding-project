# SOL / Construction Manager / Glorp UI Compatibility Check

Audit date: 2026-10-05

## Scope

- Standard of Living `260726` (`hades.sol`)
- Workshop `3736668860`: Construction Manager `2.2.11`
- Workshop `3601047146`: Glorp UI `1.3.10.1`

## Conflict audit

SOL has only one active same-path file overlap with either UI mod:

```text
in_game/gui/location_window.gui
```

EU5 replaces that GUI file as a whole. A vanilla-based SOL window would discard
Glorp UI's layout, while Glorp UI loaded after SOL would remove the SOL income
display and Living Standard entry. Glorp UI and Construction Manager already
have the same conflict: both provide this exact path, and the winning file is
selected by load order.

The Glorp source window is an integration base, not an isolated file. It
contains Glorp UI changes and references to definitions supplied by:

- vanilla location-window types extracted into
  `gui/vanilla/cmfg_location_window_vanilla_types.gui`;
- the shared Glorp/CM `zoom_to_button` type;
- Construction Manager widgets, scripted GUIs, and the
  `cm_best_town_right` map mode.

The common non-GUI object names are only CMF dispatcher on-actions and Glorp's
`monthly_country_pulse`; SOL does not copy those objects. No localization-key
collisions were found.

## Built-in integration

The full `src/stable/` target uses the complete Glorp UI
`location_window.gui` as its merge base, then inserts the SOL Living Standard
button. The generated file deliberately retains both `glorpui_*` and `cm_*`
references. This is the same integration model Glorp UI uses for Construction
Manager: the GUI file is unified, while the referenced object definitions are
provided by whichever mods are enabled.

`scripts/sync_location_window.py` produces the unified result by:

1. copying Glorp UI's extracted vanilla location types into SOL at the same
   relative path;
2. migrating Glorp UI's 1.3 action-button and road-builder APIs to 1.4;
3. replacing the shared `zoom_to_button` type with the SOL-owned
   `sol_zoom_to_button` type;
4. replacing `Location.GetTotalIncome` with SOL's
   `local_sol_total_income`;
5. inserting the SOL Living Standard tooltip button before the migration
   spacer;
6. preserving the Glorp UI and Construction Manager widget/script/mapmode
   references present in the source window.

The source metadata and CM markers are checked for reference drift. Those
checks do not add Glorp UI or Construction Manager to SOL's formal metadata
dependencies, and they must not be used as a reason to strip valid optional
references from the unified window.

## Runtime requirements

Only Community Mod Framework remains a formal dependency of full SOL. Neither
Workshop `3601047146` nor `3736668860` is declared as a SOL metadata
dependency. Their definitions remain optional runtime inputs to the unified
location window.

The effective combinations are:

| Enabled mods | Winning `location_window.gui` | Expected result |
|---|---|---|
| SOL only | SOL's generated Glorp-based file | SOL + Glorp UI layout and button. `cm_*` references report missing definitions, but those errors do not prevent the SOL/Glorp layout from displaying. |
| SOL + Glorp UI | SOL's generated file (configure load order so SOL wins this exact path) | Same location window as SOL only. Other Glorp UI files also load, but Glorp UI cannot replace the SOL file when SOL wins the path. |
| SOL + Glorp UI + Construction Manager | SOL's generated Glorp-based file, with CM definitions loaded | SOL + Glorp UI + Construction Manager controls, with no missing `cm_*` definitions. Keep Construction Manager above Glorp UI so its definitions load while Glorp's integrated GUI remains the selected UI file. |

For Glorp UI + Construction Manager without SOL, keep Construction Manager
above Glorp UI so Glorp's integrated `location_window.gui` wins while
Construction Manager's definitions remain available. This is an exact-path
load-order rule, not a metadata dependency declaration.

## Target notes

- `src/stable/`: unified Glorp UI-based window with optional Construction Manager references is an integrated feature.
- `src/sol_standalone/`: remains vanilla-based.
- SOL-PP and SOL-JTG do not replace `location_window.gui`, so they retain the
  stable Built-in window.
- SOL-M&T supplies its own M&T-based final location window.

## Error log classification

The current `docs/error_log/error.log` contains both real 1.4/API problems and
expected optional-definition failures. The distinction is based on the
enabled-mod combination, not on the presence of a `cm_` prefix alone.

| Log entries | Classification | Meaning |
|---|---|---|
| Metadata parse error for `src/sol_standalone/.metadata/metadata.json` | Real error | Standalone metadata is missing the required `relationships` member. |
| `OnMouseEnterBuildRoadButton`, `OnMouseLeaveBuildRoadButton` callbacks | Real error | Legacy Glorp/1.3 callbacks are not present in the verified 1.4 API. |
| `ShowRoadbuilder` | Real error in the logged deployment | 1.4 uses `ShowRoadBuilder`; the current generator migrates this, so this line indicates an old deployed window or stale log and must be rechecked after deployment. |
| `GetArmyLevyPercentage`, `GetNavyLevyPercentage` | Real error | The current 1.4 API exposes the `...ForCountry(Arg0)` forms; old getter calls remain in the affected GUI snapshot. |
| `cm_is_auto_expand_on_icon`, `cm_auto_food_widget_location_window`, `cm_auto_expand_rgo_widget_location_window` | Optional Construction Manager dependency missing | Expected when Construction Manager is not enabled. Keep these references in the unified Glorp/SOL window; removing them would break the SOL + Glorp UI + Construction Manager combination. |
| `use_global_input_instance` | Real error | The property was removed from the 1.4 engine and must be migrated or removed from the copied support type. |
| `PERFORM_global_living_standard_recalculate_ACTION` | Deployment/load-state issue requiring retest | The message type exists in both stable and standalone SOL message files. Re-deploy and collect a fresh log after fixing metadata and stale GUI output before treating it as a missing definition. |

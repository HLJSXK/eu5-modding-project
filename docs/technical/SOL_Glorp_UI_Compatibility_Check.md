# SOL / Construction Manager / Glorp UI Compatibility Check

Audit date: 2026-10-06

## Scope

- Standard of Living `260726` (`hades.sol`)
- Workshop `3736668860`: Construction Manager `2.2.11`
- Workshop `3601047146`: Glorp UI `30.10.26` (`glorp.ui`), snapshot supports EU5 `1.4.*`

## Conflict audit

SOL overlaps the UI mods on this whole-file path:

```text
in_game/gui/location_window.gui
```

EU5 replaces that GUI file as a whole. Stable and standalone now use the
vendored Glorp UI 1.4 window as their source, then inject SOL's controls.
Loading Glorp UI after SOL still replaces the generated window and hides those
additions; configure load order so SOL wins this path when its controls are
wanted. PP compatibility continues to use PP's own complete window.

## Built-in integration

The full `src/stable/` and `src/sol_standalone/` targets use the Glorp UI 1.4
`location_window.gui` snapshot as their merge base. Stable extracts Glorp's
`LocationWindowTypes` block into `gui/Glorp_location_window_types.gui`; both
targets inject the SOL Living Standard button and optional Great Projects
references. Standalone also replaces the native income display with SOL's
income value. Construction Manager references already integrated into Glorp's
window remain part of that source; CM definitions are available when the
optional Construction Manager mod is enabled.

`scripts/sync_location_window.py` produces the result by:

1. extracting Glorp's `LocationWindowTypes` block into SOL's companion GUI
   file;
2. checking that the source uses the current 1.4 action-button API;
3. inserting the SOL Living Standard tooltip button into Glorp's demography
   row;
4. inserting the optional Great Projects button, panel and queue-close hooks.

## Runtime requirements

Only Community Mod Framework remains a formal dependency of full SOL. Neither
Workshop `3601047146` nor `3736668860` is declared as a SOL metadata
dependency. The Glorp source is vendored into SOL; optional Construction
Manager definitions resolve Glorp's integrated `cm_*` references when enabled.

The Living Standard row below the left-panel buttons adds one GUI type-load
condition: when Glorp UI is enabled, load SOL after Glorp UI so the generated
`SOL_lshud_glorp_compat.gui` definitions of `left_panel_info_bar` and
`left_panel_info_toggle` take effect. The generator preserves both Glorp type
bodies and adds a 36px offset. These definitions are unused without Glorp UI;
the compatibility shim does not replace a vanilla or Glorp GUI file path.

The effective combinations are:

| Enabled mods | Winning `location_window.gui` | Expected result |
|---|---|---|
| SOL only | SOL's Glorp-based file | Glorp UI 1.4 layout with SOL and optional Great Projects controls; unresolved optional `cm_*` definitions may be logged without Construction Manager. |
| SOL + Glorp UI | SOL's file (configure load order so SOL wins this exact path) | Vendored Glorp UI layout with SOL controls; the independent Glorp HUD shim moves its stats bar/toggle below the SOL row. |
| SOL + Glorp UI + Construction Manager | SOL's file | Vendored Glorp UI layout with SOL controls and Construction Manager definitions available. The Glorp HUD shim remains active. |
| SOL + PP compatibility | PP compatibility's file | PP's complete location window with the SOL button injected into `pp_location_card`. |

For Glorp UI + Construction Manager without SOL, keep Construction Manager
above Glorp UI so Glorp's integrated `location_window.gui` wins while
Construction Manager's definitions remain available. This is an exact-path
load-order rule, not a metadata dependency declaration.

## Target notes

- `src/stable/`: Glorp UI 1.4-based window with SOL and optional Great Projects controls is an integrated feature.
- `src/sol_standalone/`: Glorp UI 1.4-based window with SOL income and tooltip controls.
- SOL-PP generates a complete PP-based `location_window.gui` and injects the
  shared SOL button into PP's `pp_location_card`; SOL-JTG retains the stable
  built-in window.
- SOL-M&T supplies its own M&T-based final location window.

## Error log classification

The current `docs/error_log/error.log` contains both real 1.4/API problems and
expected optional-definition failures. The distinction is based on the
enabled-mod combination, not on the presence of a `cm_` prefix alone.

| Log entries | Classification | Meaning |
|---|---|---|
| `SOL_lshud_glorp_compat.gui:54` / property widgets must specify exactly one widget | SOL-owned copied Glorp tooltip error; source corrected, native hover pending | Glorp referenced legislative_efficiency_tooltip, which current vanilla comments out. The generator restores its still-valid modifier/localization content under a SOL-owned name and rewrites the copied reference. Composition tests now inspect this tooltip and the missing-template warning. |
| Metadata parse error for `src/sol_standalone/.metadata/metadata.json` | Real error | Standalone metadata is missing the required `relationships` member. |
| `OnMouseEnterBuildRoadButton`, `OnMouseLeaveBuildRoadButton` callbacks | Real error | Legacy Glorp/1.3 callbacks are not present in the verified 1.4 API. |
| `ShowRoadbuilder` | Real error in the logged deployment | 1.4 uses `ShowRoadBuilder`; the current generator migrates this, so this line indicates an old deployed window or stale log and must be rechecked after deployment. |
| `GetArmyLevyPercentage`, `GetNavyLevyPercentage` | Real error | The current 1.4 API exposes the `...ForCountry(Arg0)` forms; old getter calls remain in the affected GUI snapshot. |
| Glorp UI and Construction Manager location-window controls | Included in the vendored Glorp-based source | Stable and standalone preserve the Glorp UI 1.4 layout, including its integrated Construction Manager call sites. |
| `use_global_input_instance` | Historical Glorp compatibility issue | The stable window no longer copies Glorp's zoom-button type or its extracted shared types. The separate HUD compatibility shim only applies when Glorp UI is loaded. |
| `PERFORM_global_living_standard_recalculate_ACTION` | Message registration migrated for 1.4.3; native registration still needs runtime retest | Older builds required gui/messagetypes.txt; EU5 1.4.3 reads the messagetypes/ directory. gen_sol_messages.py now emits only SOL's type in main_menu/gui/messagetypes/SOL_messages.txt for stable/standalone, with no vanilla copy. Compatibility submods inherit this registration. |

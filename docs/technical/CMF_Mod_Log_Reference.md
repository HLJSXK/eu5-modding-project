# CMF Mod Log Reference

Captured on 2026-08-06 from reference mod `3692202776` and the wiki text
supplied in this session.

## Purpose

CMF exposes a shared global in-game log for mod actions. The caller is always
the current country scope, so the effect is meant to be run by the country that
performed the action.

## Public effects

| Effect | Inputs | Notes |
| --- | --- | --- |
| `cmf_log` | `action` (flag) | Basic log entry with no args. |
| `cmf_log_with_args` | `action`, `arg1`, `arg2` (flags) | Flag args are localization keys; renders as `arg1 action arg2`. |
| `cmf_log_with_scope_arg` | `action` (flag) | Requires `scope:cmf_log_arg2` saved before calling. |
| `cmf_log_with_scope_args` | `action` (flag) | Requires `scope:cmf_log_arg1` and `scope:cmf_log_arg2` saved before calling. |
| `cmf_clear_log` | `yes` | Clears all entries. |

## Storage and UI

- Entries are stored in global variable maps: `cmf_log_action`,
  `cmf_log_actor`, `cmf_log_arg_mode`, `cmf_log_arg1`, `cmf_log_arg2`.
- Entry keys are synthesized as `cmf_log_0` through `cmf_log_199`.
- The hard cap is 200 entries.
- GUI reads them through `CMFLogCount`, `CMFLogActorCountry`,
  `CMFLogEntryText`, `CMFLogArg1Name`, `CMFLogArg2Name`, `CMFLogHasEntries`,
  `CMFLogHasArg1(Index)`, `CMFLogHasArg2(Index)`, and
  `CMFLogIsScopeArgs(Index)`.
- The log pane uses `DataModelRepeatedItem(CMFLogCount)` and shows the actor
  flag, actor name, and formatted action text.
- The clear button is only shown in singleplayer; `CMF_ClearLog` is hidden in
  multiplayer.
- `CMF_CloseLogView` removes `cmf_log_view_open`.

## Localization notes

- `action` and flag args should point at loc keys.
- For custom text args, define a loc key explicitly.
- For dynamic countries, save them into `scope:cmf_log_arg1` /
  `scope:cmf_log_arg2` before calling the scope variants.

## Sources

- `reference_mods/3692202776/in_game/common/scripted_effects/cmf_log_effects.txt`
- `reference_mods/3692202776/in_game/common/scripted_guis/cmf_log_scripted_gui.txt`
- `reference_mods/3692202776/loading_screen/data_binding/cmm_macros.txt`
- `reference_mods/3692202776/in_game/gui/cmm/panes/cmm_log_pane.gui`
- User-provided wiki text in this session

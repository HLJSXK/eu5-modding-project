# EU5 GUI Modding Guide

> **Read this before writing or changing any `.gui` file, GUI expression, or GUI-displayed localization.**
> Every rule below is marked by evidence level:
> **[实机]** = confirmed against a 1080p in-game screenshot (2026-10-11),
> **[源]** = read directly from game/official files, **[推]** = inferred, not yet confirmed.
> Detailed derivations, screenshots, and the renderer that reproduces the game's GUI live in
> [`ai_gui_assessment/`](../../ai_gui_assessment/README.md).

## 0. How to work on GUI in this project

1. **Read the type definition before using it.** Never guess a type's blocks. Print the full, resolved definition of any
   `type` / `template` (vanilla + SOL):

   ```
   $env:PYTHONUTF8='1'; & $env:EU5_PYTHON ai_gui_assessment/renderer/guidef.py situation_card_common card_common
   ```

2. **Use the vanilla component catalogue.** `reference_game_files/game/in_game/gui/ui_library.gui` is Paradox's own
   catalogue of reusable types (windows, buttons, text formats, cards, portraits). Find the visual you want there,
   then copy its type. In-game it opens with the console command
   `GUI.CreateWidget gui/ui_library.gui ui_library_window` (close: `GUI.ClearWidgets ui_library_window`).
   Screenshots of all 26 pages: `ai_gui_assessment/screenshots/ui_library/`.

3. **Render before launching the game.** The renderer reads the real game textures/fonts/localization and SOL's
   `src/stable` GUI, applies the layout rules below, and writes a PNG plus an element tree with every element's
   computed rect (game folder must exist at `C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V`):

   ```
   & $env:EU5_PYTHON ai_gui_assessment/renderer/run.py situation
   & $env:EU5_PYTHON ai_gui_assessment/renderer/run.py ui_library windows windows=tooltips
   & $env:EU5_PYTHON ai_gui_assessment/renderer/compare.py SHOT RENDER sx sy w h [rx ry] [zoom] OUT
   ```

   Replace `situation` with `location`, `tooltip`, `event`, `market`, `government`, or `battle` for those screens.
   The SOL situation panel and location window have screenshot-matched regions, and the SOL location tooltip's
   outer width matches the roughly 550px game screenshot. No screen-wide pixel-accuracy claim applies (see §6). For a new screen,
   add a mock-data scenario in `renderer/scenarios.py` / `scen_location.py`.

4. **When the renderer and the game disagree, the game wins.** Record the corrected rule here and in
   `ai_gui_assessment/08_round2_results.md`.

## 1. Files, composition and overrides

| Rule | Level |
|---|---|
| `.gui` files override **by whole relative path**; there is no INJECT/REPLACE for GUI. Owning one button in `location_window.gui` means owning the full file (hence SOL's generators). | 源 |
| `type a = b { ... }` inherits `b`; `template x { }` + `using = x` pastes properties; `block "n" { default }` is a slot replaced **entirely** by `blockoverride "n" { }` (empty override deletes the default). | 源 |
| Override content lands **where the block sits**, and is validated there: a block inside an `hbox`/`vbox` child cannot receive `parentanchor` or a `%` size (`pdx_gui_validation.cpp: Unsupported property ... child of a hbox/vbox`). | 源 |
| Overrides propagate into nested type instances, but **an instance's own `blockoverride` beats one inherited from outside** (otherwise nested scrollbox-in-scrollbox would recurse forever). | 实机 |
| Text set on a button (`text` / `raw_text`) is drawn by the button type's `buttonText = { textbox }` child. | 实机 |
| Hidden children in `hbox`/`vbox` take **neither size nor spacing**. | 实机 |
| Nested widget `datacontext` expressions can refer to an ancestor's context: the battle view binds `Combat.GetDefender`, then a child binds `CombatSide.GetLeft`. A static renderer must retain the parent object while resolving the child. | 源 |

## 2. Layout

| Rule | Level |
|---|---|
| Box children: `fixed` keeps its hint; `expanding` / `growing` take extra space. **`expanding` children get extra space first; `growing` only gets leftovers.** `expand = {}` is a `growing` widget, so it does *not* steal space from an expanding sibling. | 实机 |
| If no child can grow, leftover space is **distributed evenly between the children** (first/last flush with the edges) — the box behaves like `justify-content: space-between`, not left-aligned. Use `expand = {}` to left/right align. Final-row spacer widgets in SOL goods grids exist for this reason. | 实机 |
| `min_width` on a non-text element acts as a minimum width. | 实机 |
| Text `max_width` also caps the element's width; an expanding `text_multi` stops at `max_width` and the parent centres it. | 实机 |
| `widgetanchor` defaults to `parentanchor`. | 实机 |
| A vertical scrollbar overlays the content; it does not narrow it. | 实机 |
| Fixed-width single-line text that does not fit **shrinks its font** down to `fontsize_min` (vanilla default 8). | 实机 |
| `righttoleft = yes` / `bottomtotop = yes` reverse box order. | 源 |
| A `dynamicgridbox` with `flipdirection = yes` lays items horizontally; `datamodel_wrap = 1` then starts a new row after each item. The IOs member list uses this to show three estate rows. This verified case does not establish vertical wrapping semantics. | 实机 |

## 3. Textures

| Rule | Level |
|---|---|
| `spriteborder` and `framesize` are in **GUI units**, not texture pixels: texture pixels = value × `texture_density`. | 实机 |
| A `ranged_slider` part instantiated through a template may have both its own `texture` and `background` layers. For example, `economy_slider_track` uses `bg_progress_bar_frame`; render the background before the track texture, including its margin and alpha. | 实机 |
| `corneredtiled` tiles the middle; a border-only pattern (e.g. `pattern_bevel_vertical_bis`) shows only the edge strip. | 实机 |
| A `modify_texture` with a `color` but no texture is a flat colour layer; the colour may be data-bound (`"[LocationPopItem.GetColor]"`). | 实机 |
| `modify_texture` without `blend_mode` behaves as normal (mask textures with black RGB still tint correctly). | 推 |
| Pie slices are drawn through the slice texture; `piechart_alpha.dds` is a ring, so vanilla pies are rings with an icon in the centre. | 实机 |
| Pop-type colours come from `main_menu/common/named_colors/02_map.txt` (`pop_nobles` …). | 源 |

## 4. Text, numbers and icons

| Rule | Level |
|---|---|
| Fonts: body `StandardGameFont` (NotoSerif; Chinese falls back to NotoSansSC), headers `HeadersFont` (NotoSerif SemiBold; Chinese NotoSerifSC). Font sizes: Small 15, Medium 18, Big 23. | 源 |
| Autoresized text is **21 px per line at font size 15** (single- and multi-line). The template's `size {0 23}` does not apply to autoresized text. | 实机 |
| `#name ... #!` applies a format from `loading_screen/gui/textformatting.gui`. **`##` prints a literal `#`.** | 实机 |
| Number suffix `\|+N`: colours by sign (positive green, negative red, zero plain) **without printing a `+`**. `\|=` / `\|+=`: also prints `+` on positive values. Digits = decimals, `%` multiplies by 100. | 实机 |
| `\|<1%`, `\|W`, `\|R`, `\|G`, `\|-=`, `\|=+`, `\|Y`: not yet confirmed. Engine-formatted strings (e.g. `GetGrowthForUI`) keep their own colour. | 推 |
| **Goods icons (`@wheat!`, `@amber!` …) are registered by the engine from the goods database and are NOT in `font_icons.gui`.** Check `in_game/common/goods/` instead. They render at `NJominiIcons.MODIFIER_TEXT_ICON_SIZE` (32 px at font 18, ≈27 px at font 15). | 实机 |
| Other `@icon!` names: `main_menu/gui/shared/font_icons.gui`. | 源 |

## 5. Engine behaviour of SOL's screens

| Rule | Level |
|---|---|
| Lateral panel at 1080p / UI scale 100%: 570 × 950 (1080 − topbar 40 − panel bar 90). | 实机 |
| A tooltip taller than the space below its anchor is shifted up so its bottom edge touches the screen bottom; it is not clipped or scaled. | 实机 |
| Situation panel action cards come from `generic_actions` with `type = situation`, **not** from resolutions. A resolution appears only via the situation's `resolution =` / `voters =` or a custom `scripted_action_tooltip` button. | 源 |
| Situation mapmode switching must use `trigger_on_create` + `PdxGuiWidget.PushMapModeOverride`; `_show` does not fire for a widget created visible. | 源 |
| Panel structure of SOL's three screens: [`ai_gui_assessment/03_sol_screens_anatomy.md`](../../ai_gui_assessment/03_sol_screens_anatomy.md). | 源 |

## 6. What the renderer cannot do (verify in game)

3D scenes, illustrations without accessible textures, procedural flags/coats of arms, character portraits, animations and hover states, and real
save data (all values are mock data). Static `dropdown` and `ranged_slider` states and the UI Library's
`TooltipBlockList` table are rendered with scenario data; the renderer does not execute engine actions or parse
arbitrary `textcontext` strings into tooltip tables. Remaining known differences are listed in
[`ai_gui_assessment/08_round2_results.md`](../../ai_gui_assessment/08_round2_results.md).

## 7. Further reading

| Document | Content |
|---|---|
| [`ai_gui_assessment/01_engine_model.md`](../../ai_gui_assessment/01_engine_model.md) | Engine model: loading, composition, states, interaction, view `Vars` |
| [`ai_gui_assessment/02_data_binding_and_text.md`](../../ai_gui_assessment/02_data_binding_and_text.md) | Expressions, Promote vs Function, GUI ↔ script bridge, text formats |
| [`ai_gui_assessment/04_community_patterns.md`](../../ai_gui_assessment/04_community_patterns.md) | Techniques used by community mods (windows, scripted widgets, lists) |
| [`ai_gui_assessment/05_ai_gaps.md`](../../ai_gui_assessment/05_ai_gaps.md) | Where AI has gone wrong on EU5 GUI and why |
| [`ai_gui_assessment/06_screenshot_requests.md`](../../ai_gui_assessment/06_screenshot_requests.md), [`08_round2_results.md`](../../ai_gui_assessment/08_round2_results.md) | In-game verification results |
| `docs/knowledge/anti_patterns.yaml` (category `gui`) | Known GUI mistakes, summarised in `BRIEF.md` |

> Note: `ai_gui_assessment/01`–`05` were written **before** the in-game screenshots. Where they disagree with
> this guide (e.g. hbox alignment, number formats, goods icons), this guide is authoritative.

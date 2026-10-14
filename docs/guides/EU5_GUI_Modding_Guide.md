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

   To check a design before it exists in `src/`, write it as a throwaway `.gui` and render it with mock values:
   `run.py proto <file.gui> <template_or_type> <mocks.json> [out]` (mocks: `script_values`, `gvm`, `paths`,
   `scenario`; output in `ai_gui_assessment/images/proto/`). `progressbar` and `barchart` are drawn since 2026-10-13.
   Explicit mock keys override the scenario; unspecified keys fall through to it. Missing script-value mocks are
   reported rather than replaced with zero. For compatibility previews, supply their content roots in
   `RENDER_EXTRA_ROOTS` (separated by `;` on Windows) so their actual DDS icons are loaded.

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
| A `blockoverride` requires an inherited block with that exact name. The bare `widget` has tooltip properties through `tooltip_se`, but no `sol_good_tooltip` slot. Assign `tooltip` directly; source evidence: defaults.gui:294 and agenda_view.gui:602. Hover text from a SOL location uses `Location.GetOwner.MakeScope`; country goods use the panel country, and only the location surface has a market price weight. The generic goods tooltip keeps static membership. | 源，实机悬停待验收 |
| `type a = b { ... }` inherits `b`; `template x { }` + `using = x` pastes properties; `block "n" { default }` is a slot replaced **entirely** by `blockoverride "n" { }` (empty override deletes the default). | 源 |
| Override content lands **where the block sits**, and is validated there: a layout child of an `hbox`/`vbox` cannot receive `parentanchor` or a `%` size (`pdx_gui_validation.cpp: Unsupported property ... child of a hbox/vbox`). This also applies to properties written directly in the shared type. Vanilla floating decorations set `ignore_layout = yes` (main_menu_cooltip_types.gui:254). The renderer checks resolved children after inheritance and overrides. | 实机错误日志 + 源 |
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
| **`text_single` inherits `autoresize = yes`, and autoresize beats a declared `size`.** A fixed-width column cell that does not set `autoresize = no` collapses to its content width, so neighbouring columns run together. | 实机 |
| **A wrapping text with no `max_width` reports its unwrapped width as a *minimum*.** An hbox measures its children with no width hint, so one uncapped paragraph (or `TooltipListBase` body) becomes the frame's minimum width and drags the whole tooltip past its 450px budget. Give every wrapping text an explicit `max_width`. | 实机 |
| `max_width` also caps the element's width; an expanding `text_multi` stops at `max_width` and the parent centres it. | 实机 |
| `widgetanchor` defaults to `parentanchor`. | 实机 |
| A vertical scrollbar overlays the content; it does not narrow it. | 实机 |
| Fixed-width single-line text that does not fit **shrinks its font** down to `fontsize_min` (vanilla default 8). | 实机 |
| **Fixed-width rows can contain children outside their own measured rectangle.** Budget the label, icons and all gaps, and split large groups explicitly. SOL uses six icons per 216px group row; inspect descendant positions as well as total dimensions. Estate mini-card text uses fixed widths with `autoresize = no`; funds and baseline occupy separate lines to preserve large figures. | 源 + 渲染检查 |
| `righttoleft = yes` / `bottomtotop = yes` reverse box order. | 源 |
| A `dynamicgridbox` with `flipdirection = yes` lays items horizontally; `datamodel_wrap = 1` then starts a new row after each item. The IOs member list uses this to show three estate rows. This verified case does not establish vertical wrapping semantics. | 实机 |
| **A bare `widget` never sizes to its children.** A widget-like element takes its hint from its own `size`, or only from children carrying `set_parent_size_to_minimum = yes` (a child's `resizeparent = yes` works the same). A bare `widget` holding an `hbox` measures **0** high, and `minimumsize` on the widget itself is measured too late to rescue it. Use a `vbox` as a framed container, and emit art as a **sized child widget**, never as a bare `background` on a childless element. | 源 |
| **Expression-valued properties must be bracketed as `"[...]"`.** Unbracketed, a numeric property does not evaluate and silently takes its default - two `layoutstretchfactor_horizontal` children then split a row evenly (36/36 in a 72px box) instead of proportionally. | 源 |

## 3. Textures

| Rule | Level |
|---|---|
| `spriteborder` and `framesize` are in **GUI units**, not texture pixels: texture pixels = value × `texture_density`. | 实机 |
| A `ranged_slider` part instantiated through a template may have both its own `texture` and `background` layers. For example, `economy_slider_track` uses `bg_progress_bar_frame`; render the background before the track texture, including its margin and alpha. | 实机 |
| `corneredtiled` tiles the middle; a border-only pattern (e.g. `pattern_bevel_vertical_bis`) shows only the edge strip. | 实机 |
| A `modify_texture` with a `color` but no texture is a flat colour layer; the colour may be data-bound (`"[LocationPopItem.GetColor]"`). | 实机 |
| `modify_texture` without `blend_mode` behaves as normal (mask textures with black RGB still tint correctly). | 推 |
| Pie slices are drawn through the slice texture; `piechart_alpha.dds` is a ring, so vanilla pies are rings with an icon in the centre. A `pieslice` `color` must be a literal `{ r g b a }` - a named colour cannot be used there. Slice `value`s may be expressions and are normalised by the engine, so pass raw counts and one chart works at any scale. | 实机 |
| Pop-type colours come from `main_menu/common/named_colors/02_map.txt` (`pop_nobles` …). | 源 |
| **Stacked and offset bars are `barchart` + `barslice`/`barslice_no_highlight`.** Slice values are normalised (raw counts are fine), `direction = vertical` stacks bottom-up, `righttoleft = yes` reverses; vanilla uses it inside tooltips (`combat_tooltips.gui:2909`). A transparent leading slice used as an offset has no vanilla precedent. | 源 |
| `flowcontainer` does not wrap by available width; vanilla wraps only with a fixed `wrap_count`. Split width-dependent rows in the generator. | 源 |
| **`using = X` inlines a `type X`, it is not a texture reference.** A `progressbar` whose `using` names a non-existent type resolves no texture and draws **nothing while still occupying its layout slot and reporting a full size** - invisible to any measurement check. Name `progresstexture` / `noprogresstexture` outright (progressbars.gui:285) and carry `texture_density` / `spriteType` / `spriteborder` on the element. Verify bars by pixel. | 源 |
| **`TooltipListBase` already contains a `TooltipTableHeader`.** A section caption needs only to override `tableheader_text` / `table_header_background`; adding a body child stacks a second header and roughly doubles the band height (~60px vs ~33px). | 实机 |
| **A `blockoverride` replaces a block entirely, and an instance's own override beats one inherited from outside.** One shared block name therefore cannot carry five different values into five sibling instances - each keeps its own default. Expose one container block per row (`block "sol_cells" {}`) and let the caller fill it with children that each carry their own override. Getting this wrong duplicates elements silently rather than erroring: emitting five cells *alongside* a block that already held five defaults produced ten per row. | 实机 |

## 4. Text, numbers and icons

**[Runtime lexer log + vanilla source] GUI strings do not accept backslash-n or backslash-t escapes.**
The user 2026-10-15 log reports `Backslash followed by neither quote nor backslash`
on every generated goods-cell tooltip. Use `[Localize('NEWLINE_BREAK')]` between
tooltip sections, as `in_game/gui/shared/character_tooltips.gui:1571` does.
Vanilla `main_menu/localization/english/economy_l_english.yml:38` and the Chinese
equivalent define `NEWLINE_BREAK` as a localization newline; localization and GUI
have different escaping rules. Escaping another backslash only makes the GUI
string lexically valid and does not establish a displayed line break. Renderer
`pdx.py` now rejects unsupported quoted-string escapes before expansion; bilingual
hover tests verify seven location sections and six country sections, including
additional lines for overlapping group memberships. Fresh in-game
confirmation of the generated fix remains pending.

**[Runtime log + vanilla source] Tooltip text templates need tooltip context.**
`tooltip_text_block_template` inherits `fonttintcolor = "[ExtraTooltipInfo.GetTintColor]"`
from `main_menu_cooltip_types.gui:336`. A regular situation panel has no
`ExtraTooltipInfo`: even static localized text repeatedly reports No context supplied / FetchData failed.
Use `text_multi` with `layoutpolicy_horizontal = expanding`, `autoresize = yes`
and an explicit `max_width`, as in `council_of_trent.gui:219`. Keep the tooltip template
inside actual contextual tooltips. Renderer now evaluates inherited text-tint bindings,
and situation mocks exclude tooltip-only contexts; a regression reproduces the original failure.
The fix preserves the supply explanation and wrapping. Fresh in-game confirmation remains pending.

2026-10-13 SOL dashboard corrections:

- **[实机错误日志 + 源] GUI arithmetic is typed.** Scope.ScriptValue returns CFixedPoint; Multiply_float returns float. Feeding the latter to FixedPointToInt causes FetchData failures. Keep dial calculations in *_CFixedPoint until integer conversion. The renderer now reports this mismatch.
- **[实机错误日志 + 源] A bare numeric binding such as max = "[1]" is invalid.** It produces an empty function call. Use max = 1; constants inside function arguments use explicit typed literals.
- **[实机错误日志 + 源] Text formatting is not valid inside numeric properties.** Population slices using `ScriptValue(...)|+0` produced ten statement-parser errors in the 16:53 log. Use `[FixedPointToFloat(Scope.ScriptValue(...))]` for each slice value (vanilla location_window.gui:1455); keep `|+0` in legend text. The renderer now rejects unquoted format suffixes in numeric bindings.
- **[实机错误日志 + 源] Separate a format tag from punctuation with whitespace.** `#R-[expense|+2]#!` and `#E/[target|+0]#!` produced unknown formatting tags when the ledger opened at 17:03. Use `#R -[expense|2]#!` (vanilla cooltip.gui:3479) and `#E /[target|0]#!`; plain number formats keep the enclosing colour. The renderer now flags these missing separators.
- **[实机错误日志] Generated and handwritten vocabulary must not define the same key.** SOL_GUI_SECTION_POP and SOL_GUI_SECTION_CONSUMPTION now have one owner in SOL_ls_ui localization, for each language and target.
- **[源 + 实机错误日志] Resolution message types use the fixed `main_menu/gui/messagetypes.txt` database.** An arbitrary SOL_economy_messages.txt file did not register the type. gen_sol_messages.py preserves every reference vanilla type and appends SOL's resolution type; another Mod owning this path needs an explicit merge. Registration happens even with show_message=no. A fresh runtime log remains required to confirm the filename correction.
- **[截图症状 + 源] Supply noprogresstexture explicitly.** Vanilla supplies the empty texture; the installed progressbar shader samples Texture1 for the empty region. A parent background does not supply this sampler. Missing it accompanied solid lime bars; the exact fallback colour is not established as a general rule.
- **[源] SOL tax/power weights are amounts.** Divide effective weights by local_total_tax_share before percent formatting; use the singular commoner key. A zero consumption baseline displays “无消费” with a neutral dial.
- **[推，渲染检查] Budget the complete framed tooltip.** The F dashboard initially measured 1244px high. Compact repeated figures, use a two-column population legend and split oversized compatibility goods groups. Chinese/English previews at 100% measure 484×1003 (stable/standalone), 484×1028 (PP) and 484×1078 (JTG), including the frame. These are static previews, not new in-game measurements; larger UI scales need in-game checking.
- **[源] Diagnostics refresh independently of optional solver preparation.** gls_accumulate_panel_stats aggregates estate display caches in its existing traversal, including small countries and disabled solvers.
- **[工具检查] Missing SOL script-value mocks are reported, not defaulted to zero.** A zero unknown-expression count must not hide missing estate funds/baseline data.
- **[源] Standalone must ship its shared GUI types.** The build mirrors only the selected target directory. `gen_sol_ls_gui.py` copies stable's shared kit into standalone and includes it in `--check`; loading stable types during preview does not prove standalone packaging.

2026-10-13 substitution integration:

- **[源 + 渲染像素检查] Full and dim icons must be mutually exclusive.** Drawing an alpha-0.3 copy over an opaque icon leaves the original bright. Bind the full copy to the cached supply condition and the dim copy to its inverse; verify the pixels as well as the properties. SOL's `sol_market_consumes_*` maps record supply, so dimming means no cached supply, not a shortage or zero demand.
- **[数据源 + 渲染检查] Labelled groups show every membership.** `goods_weights.csv` contains 56 unique goods and 67 memberships across 20 groups. `ordered()` uses the primary group to order a unique list; `group_rows()` shows an overlapping good in each of its groups. Repeated icons do not repeat spending. PP/JTG extras stay in the ungrouped tail.
- **[官方 API + 原版源 + 离线检查] Missing market weights are pending data, not neutral prices.** Check `GetVariableFromGlobalVariableMap(...).IsSet` (data_types_script.txt:34,3427), then use `SelectLocalization` (goods_details.gui:135) to choose the location price snippet or pending text. Only the location hover has a market; country goods use `Player.MakeScope` for the multiplier and the generic goods tooltip keeps static memberships.
- **[模组源 + 离线检查，实机悬停待验收] Show substitution lifecycle explicitly.** The guarded display value distinguishes disabled, enabled awaiting a snapshot, and initialized. Country goods show a compact refresh-year / eligible-count / largest-absolute-modifier summary; the last metric includes external demand offsets and differs from the substitution multiplier. The +/- corner markers indicate country multipliers above/below 1 only on supplied goods. Hover text explains the country scope and annual/full-refresh market cache.

`scripts/test_sol_substitution_ui.py` reads the shipped templates and installed game assets. It checks
all memberships, supply pixels, localized hover content, missing-cache text, lifecycle summaries, and
Chinese/English framed tooltip bounds for stable, standalone, PP and JTG. M&T inherits the base goods UI.
It uses mock values and does not execute engine hover or demand updates. To save review images:

```powershell
$env:PYTHONUTF8='1'
$env:SOL_UI_PREVIEW_OUT='ai_gui_assessment/images/substitution_integration'
& $env:EU5_PYTHON scripts/test_sol_substitution_ui.py
```

| Rule | Level |
|---|---|
| Fonts: body `StandardGameFont` (NotoSerif; Chinese falls back to NotoSansSC), headers `HeadersFont` (NotoSerif SemiBold; Chinese NotoSerifSC). Font sizes: Small 15, Medium 18, Big 23. | 源 |
| **`text` resolves a localization key; `raw_text` is printed verbatim.** `text` also evaluates an embedded `[expression]` (`text = "[Goods.GetDemandsInfo]"`). Put keys in `text`, and expressions / `@icon!` texticons / `#colour ... #!` markup in `raw_text`. A key placed in `raw_text` prints literally in the UI. | 实机 |
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

### 2026-10-14 F runtime screenshot corrections

- **[Runtime screenshot + official API]** Fractional float stretch weights made all estate markers coincide. Vanilla `SocietalValueItem.GetInertiaCapWeight` returns int32. Use scaled integer weights and hide zero-weight spacers; give population/income markers independent full tracks. Renderer rejects float weights; boundary positions are regression tested. New in-game confirmation is pending.
- **[Runtime screenshot; cause inferred from layout/source]** A fixed label in an unconstrained `size = { -1 17 }` header collapsed to ellipsis. Set positive widths for header, label and count. Fixed card policy prevents a lone card expanding to full row width. Width/height checks alone do not prove visible labels or non-overlapping descendants.
- **[Mod source]** Funds/baseline minus one is distinct from the final country-solver demand coefficient. By explicit user decision, all SOL GUI consumption balances use raw location alpha (displayed as alpha minus one); the country panel aggregates raw funds and baseline. Do not display country-solver beta or final/applied demand in panels or their tooltips. The location modifier retains the actual applied result. Goods count/gold line reflect cached supply, not consumption.


### Current SOL layout decision: sheet C balances (2026-10-14)

**User-directed design, source-backed bars, offline preview checked; new runtime confirmation pending.**
SOL now shows only three purchasing-power values per row: raw alpha minus one, available funds, baseline consumption. The total and five estates use two progressbar halves around 0, with the negative half invertprogress = yes (vanilla societal_values_lateralview.gui). Scale labels are -50%, -25%, 0, +25%, +50%; clamp only the bar/cursor, never the large numeric value. A zero baseline shows no consumption and a neutral bar. Preserve alpha-only scope; beta is visible via the actual location modifier, not these rows.

All dials, population/income charts, steel/gold share markers, income/population ratios and explanatory paragraphs are temporarily removed. Required/daily/luxury goods tiers are retained. The compatibility filename data/sol_ui_f_spec.yaml now describes this sheet C + F goods layout (schema 2); do not restore F charts solely because older audit documents request them. Local previews are in ai_gui_assessment/images/sheet_c_balances/.

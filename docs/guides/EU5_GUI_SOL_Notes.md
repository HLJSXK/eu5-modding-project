# SOL GUI Modding Notes

Read the [shared EU5 GUI guide](../../.eu5-base/docs/guides/EU5_GUI_Modding_Guide.md) first. This file records SOL-specific screen behavior, experiments, runtime evidence, and design decisions.

## SOL scenario adapter

### Living Standard left-panel row (2026-10-18)

**[Source and offline rendering; in-game acceptance pending.]** The latest design moves the persistent summary into a 570×36 row at `{ 0 130 }`, below the left panel's nine navigation buttons, and keeps the adopted contextual tooltip unchanged. Stable and standalone register a separate `layer = bottom` scripted widget. It hides while `LeftView.IsShown` or `LeftView.IsSideAttached`, follows `Animation_Show_Hide_UI`, and stable's SOL master switch still disables it. `scripts/gen_sol_lshud.py` owns both target GUIs, bilingual localization, ranking outputs and the Glorp UI compatibility shim.

Income remains yearly net gold per thousand people, read from the solver's individually nonnegative estate-income caches. Same-month histories prevent partial-year changes being labelled annual; initial figures remain pending until a full baseline exists. The annual ranking still uses a named `order_by` value and one country-cache-only pass.

When Glorp UI is installed, the generated `SOL_lshud_glorp_compat.gui` wraps its current `left_panel_info_bar` and `left_panel_info_toggle` source type bodies and shifts them down 36px. SOL must load after Glorp UI so its duplicate type names win; no vanilla or Glorp path is replaced, and the shim is unused without Glorp. The offline UI regression renders the row with the actual Glorp composition and checks the shifted bar and its collapse toggle. Native hover, UI scaling, scripted-widget hit testing, hide/show animation, and actual Workshop load order still require in-game confirmation.

`ai_gui_assessment/renderer/run.py` retains the SOL presets `situation`, `location`, `tooltip`, `goods_tooltip`, `event`, `market`, `government`, `battle`, `ui_library`, and `proto`. It loads the reusable renderer from `.eu5-base`, reads the installed game's textures, fonts, and localization, and overlays `src/stable` GUI files. Render output and element trees go to `ai_gui_assessment/images/` by default; set `EU5_RENDER_OUTPUT_ROOT` to choose another directory. Set `RENDER_EXTRA_ROOTS` for compatibility DDS assets outside the selected mod root. At 1080p and UI scale 100%, some SOL situation-panel and location-window regions match in-game screenshots, and the SOL location tooltip frame is approximately 550px wide; no screen-wide pixel-accuracy claim applies. For new SOL screens, add mock data to `renderer/scenarios.py` or `renderer/scen_location.py`.

```powershell
$env:PYTHONUTF8='1'
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py situation
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py ui_library windows windows=tooltips
& $env:EU5_PYTHON ai_gui_assessment/renderer/run.py proto <file.gui> <template_or_type> <mocks.json> [out]
```

The `proto` JSON supports `script_values`, `gvm`, `paths`, and `scenario`; explicit mock keys override the scenario. Missing script-value mocks are reported rather than replaced with zero. The actual game remains the authority when a static render differs; record comparisons in `ai_gui_assessment/08_round2_results.md`.

## SOL examples behind shared rules

- The bare `widget` has no `sol_good_tooltip` block. SOL goods cells assign `tooltip` directly; a location hover uses `Location.GetOwner.MakeScope`, whereas country goods use the panel country. Only the location surface has a market price weight, so the generic goods tooltip keeps static membership.
- Final-row spacer widgets in SOL goods grids keep fixed children aligned when an `hbox` distributes extra space. A six-icon SOL group row budgets 216px for icons; check descendant positions as well as its measured width. Estate mini-cards set `autoresize = no` and separate funds from baseline to preserve large figures.
- An inherited `blockoverride` cannot carry five different values into five siblings: each retains its own default. SOL uses a per-row `block "sol_cells" {}` so each emitted child carries its own override. An earlier attempt appended five cells beside five defaults and silently rendered ten.

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
$env:SOL_UI_PREVIEW_OUT='../../ai_gui_assessment/images/substitution_integration'
& $env:EU5_PYTHON scripts/test_sol_substitution_ui.py
```
## 5. Engine behaviour of SOL's screens

| Rule | Level |
|---|---|
| Lateral panel at 1080p / UI scale 100%: 570 × 950 (1080 − topbar 40 − panel bar 90). | 实机 |
| A tooltip taller than the space below its anchor is shifted up so its bottom edge touches the screen bottom; it is not clipped or scaled. | 实机 |
| Situation panel action cards come from `generic_actions` with `type = situation`, **not** from resolutions. A resolution appears only via the situation's `resolution =` / `voters =` or a custom `scripted_action_tooltip` button. | 源 |
| Situation mapmode switching must use `trigger_on_create` + `PdxGuiWidget.PushMapModeOverride`; `_show` does not fire for a widget created visible. | 源 |
| Panel structure of SOL's three screens: [`ai_gui_assessment/03_sol_screens_anatomy.md`](../../ai_gui_assessment/03_sol_screens_anatomy.md). | 源 |
### 2026-10-14 F runtime screenshot corrections

- **[Runtime screenshot + official API]** Fractional float stretch weights made all estate markers coincide. Vanilla `SocietalValueItem.GetInertiaCapWeight` returns int32. Use scaled integer weights and hide zero-weight spacers; give population/income markers independent full tracks. Renderer rejects float weights; boundary positions are regression tested. New in-game confirmation is pending.
- **[Runtime screenshot; cause inferred from layout/source]** A fixed label in an unconstrained `size = { -1 17 }` header collapsed to ellipsis. Set positive widths for header, label and count. Fixed card policy prevents a lone card expanding to full row width. Width/height checks alone do not prove visible labels or non-overlapping descendants.
- **[Mod source]** Funds/baseline minus one is distinct from the final country-solver demand coefficient. By explicit user decision, all SOL GUI consumption balances use raw location alpha (displayed as alpha minus one); the country panel aggregates raw funds and baseline. Do not display country-solver beta or final/applied demand in panels or their tooltips. The location modifier retains the actual applied result. Goods count/gold line reflect cached supply, not consumption.


### Current SOL layout decision: compact sheet C balances (2026-10-15)

**User-directed design, source-backed bars, offline preview checked; new runtime confirmation pending.**
SOL shows three purchasing-power values per row: raw alpha minus one, available funds, baseline consumption. The total and five estates use centered signed nonlinear bars with one shared numeric ruler (-100%, -50%, 0%, +100%, +200%) above the estate rows. Every track keeps two short minor ticks and a fixed two-unit-wide zero line. Labels, tracks and right-aligned values share columns. Estate rows are 42 units high with 18-point percentages and an 11-point gray funds / baseline pair underneath; its bilingual tooltip explains the ordering. The 64-unit total row has a faint gold background and one-unit gold outline, a 12-unit bar (estate bars: 8), and a 24-point percentage. No numeric scale is repeated inside individual rows. The negative fill uses `1-q²` for funds/base `q` in 0..1, with cursor position `q²/2`; positive raw balance `c=q-1` uses `c(4-c)/4` in 0..2, with cursor position `1/2 + fill/2`. Zero funds reaches -100%, baseline reaches centered 0%, and three times baseline reaches +200%. A zero baseline shows no consumption and a neutral bar. Preserve alpha-only scope; beta is visible via the actual location modifier, not these rows.

All dials, population/income charts, steel/gold share markers, income/population ratios and explanatory paragraphs are temporarily removed. Required/daily/luxury goods tiers are retained. The compatibility filename data/sol_ui_f_spec.yaml now describes this sheet C + F goods layout (schema 2); do not restore F charts solely because older audit documents request them. Current bilingual previews are in ../../ai_gui_assessment/images/compact_balances_20261015/; these use mock data, and new in-game confirmation is pending.

### Sheet C goods tooltips (2026-10-15)

**[Vanilla/official source; offline bilingual previews; in-game confirmation pending.]**
The actual goods tooltip is separate from the SOL basket cells' string hover.
`goods_details` is shared by `Goods_tooltip`, `Goods_Cards_tooltip` and
`SpecificGoodsMarket_tooltip` (production_tooltips.gui:458/495; market_tooltips.gui:1515).
It shows tier/group labels and all member icon/name chips, including the hovered good,
plus the seven static price preferences. Goods outside the membership table hide
the complete substitution section: heading, dividers, membership rows, price
preferences and the substitution market-price ratio. Gate on static membership,
not a market's current supply or cached consumption, so grouped goods still show
their alternatives when locally unavailable. The separate basket-cell hover keeps
its ungrouped string for compatibility goods.
Visibility uses an explicit allowlist from `goods_weights.csv`: extra goods from
other mods and unknown/default/empty keys hide the section even when no
`SOL_GOOD_SUB_<key>` localization exists. No fallback text or substitute data is
evaluated for those goods. Bilingual regressions cover all three tooltip types.

`block "sol_goods_price_context"` defaults to the static legend. Only the market
use site supplies its override: vanilla already binds `Market.GetMarketEntry(Goods.Self)`.
The generator owns that complete vanilla path and preserves every other block.
The live ratio divides `Market.GetPrice(Goods.Self)` by `Goods.GetDefaultMarketPrice`
(both CFixedPoint, official data_types_uncategorized.txt:98436/76572); guard zero base price
and invalid markets. It is a live reference price, not the cached applied country
multiplier. Preference boundaries match sol_substitution.py:29, including strict
comparisons at 0.40/0.65/0.85/1.30/1.70/2.30; column tooltips spell out full intervals.
The market-only `SOL_goods_market_price_tiers` highlights exactly one current
tier with a 1 GUI-unit gold outline and a faint gold fill, drawn as a sized
`ignore_layout = yes` child before the text. Four flat edge widgets use
`color_gold_texture` (window_components.gui:26); the beveled `bg_square_gold_tile`
was too heavy in the user's runtime screenshot. Compare the live price directly
against `Multiply_CFixedPoint(base_price, threshold)`, matching the runtime;
formatting or rounding the ratio first can select the wrong boundary tier.
Generic/card legends have no active tier, and invalid markets, zero base prices
and ungrouped goods have no highlight. Regression checks cover all seven tiers,
every boundary and the actual selected-column pixels. In-game confirmation remains pending.
Review images are in `../../ai_gui_assessment/images/sheet_c_goods/`. Generate them with
`SOL_UI_PREVIEW_OUT` and `scripts/test_sol_substitution_ui.py`; the renderer CLI also
accepts `run.py goods_tooltip wine 1.42` for a market preview.

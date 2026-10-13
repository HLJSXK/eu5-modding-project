# SOL Economy UI Redesign — Session Handoff (2026-10-13)

Branch: `substitution`. Current integration update (2026-10-13):

- The F-route dashboard is committed as `09ab11b1`; the existing substitution implementation and initial GUI integration are committed as `dfd3055f`. The GUI alignment described below is the follow-up implementation.
- Base and compatibility generators share `sol_goods_ui.py`. Labelled rows preserve all 67 CSV memberships; unique-list ordering remains separate. Full/dim supply icons are mutually exclusive, and +/- marks the consuming country's substitution direction. Compatibility-only goods stay neutral.
- Location hover uses the owner country and local market cache; missing weights say pending. Country hover uses Player without inventing a market. Both show disabled/pending/active states. Country goods begin with refresh year, eligible count and maximum absolute modifier; generic goods tooltips remain static.
- Core tests pass 14/14; the new `scripts/test_sol_substitution_ui.py` passes 5/5 with installed assets and mock values. The five-target generation check and changed-file validation pass. Bilingual framed tooltips measure 484×1003 (base/standalone), 484×1028 (PP), and 484×1078 (JTG), without unknown expressions or horizontal overflow.
- Review images and element trees: `ai_gui_assessment/images/substitution_integration/`. The country and location CLI renders report zero unknown expressions; the generic goods render retains ten known vanilla mock gaps. The CLI PNGs include outer margins.
- Goods inline icons are engine-registered from goods data, including camels; absence from font_icons.gui does not make them unsupported. Fixed widgets are retained for the grid footprint and positioned markers. Supply dimming is not a shortage measurement.

The sections below preserve the **initial redesign handoff**, including its old
dimensions, uncommitted status and open questions. Those are historical, superseded
by the update above and [the current implementation record](../technical/SOL_Substitution_Implementation_20261013.md).
This integration has not been launched in game; hover, demand updates, fixed-point
behavior and larger UI scales still need engine acceptance.

## Initial redesign snapshot

Original working tree: 42 changed/untracked paths, nothing committed at that point.

This is a handoff for the SOL economy front-end redesign: the location tooltip, the
country situation panel, and the goods tooltip. Read this before touching any of the
three surfaces.

---

## 1. What was asked and what was delivered

The task was a complete redesign of three SOL surfaces, ignoring the previous design,
so they share one visual language and show the new substitute-group data:

| # | Surface | File |
|---|---|---|
| a | Situation panel (country stats) | `src/stable/in_game/gui/panels/situation/global_living_standard.gui` |
| b | Location tooltip (location stats) | `src/stable/in_game/gui/SOL_economy_local.gui` |
| c | Goods tooltip override (substitute info) | `src/stable/main_menu/gui/shared/goods_details.gui` |
| d | Shared visual language | `src/stable/in_game/gui/SOL_living_standard_kit.gui` |

All three render clean (0 unknown expressions) and the full codegen chain passes
`--check`. **Nothing has been verified in the actual game yet** — see §6.

---

## 2. The design decision (the important part)

The first attempt only restyled the existing layout: metrics as rows, five estates as
columns, a 35-cell number matrix. The user rejected it — correctly — as "still stacked
numbers". The redesign changed the **organising principle**:

1. **The estate is the unit of reading**, not the statistic. Each estate owns one
   ledger row read straight across. A player asks "how are my nobles doing", not
   "show me column four of the power table".
2. **The population mix is a ring**, not a row of percentages.
3. **Goods are grouped by demand group**, with the group's name at the left of its row,
   so a shortage is readable off the row. This is the substitute-group feature made
   visible — previously it had no UI presence at all.

Section order on both surfaces: headline strip → composition (ring + legend) → estate
ledger → consumption coefficient → substitute groups.

### Ledger columns (must match between header and row)

`阶层 126 | 人口 46 | 力量 50 | 收入 58 | 维护费 52 | 存款/目标 96` — 428 + 8 margin
= 436, inside the 450 tooltip budget and the 486 panel content column.

### Two deliberate omissions (do not "fix" these by inventing numbers)

* **Country-side 力量 column is blank (`–`).** SOL computes a tax/power share only on
  the location side (`local_*_tax_share`). There is no country-level equivalent, and a
  fabricated figure would be worse than a gap.
* **The generic goods tooltip shows only static group membership.** The country
  substitute multiplier needs a consuming country and the price tier needs a market;
  the generic tooltip owns neither. Extension points are recorded in
  `scripts/gen_sol_goods_tooltip.py`'s docstring —
  `market_tooltips.gui:1523` `block "good_details_extra_info" {}` for market-context
  content, or a country-scoped panel.

---

## 3. Files

### New — UI kit and generators

| File | Lines | Purpose |
|---|---|---|
| `src/stable/in_game/gui/SOL_living_standard_kit.gui` | 314 | The shared kit. Types: `sol_stat_item`, `sol_caption`, `sol_note`, `sol_ring`, `sol_legend_row`, `sol_ledger_header`, `sol_ledger_row(_alt)`, `sol_kv_row(_alt)`, `sol_group_row`. Read its header comment first — it documents the budgets and the two width traps. |
| `scripts/gen_sol_ls_gui.py` | 625 | Generates both SOL surfaces for `stable` + `sol_standalone`, plus `SOL_ls_ui_l_*.yml` (estate names, ledger headers, group names). `--target stable\|sol_standalone\|all`, `--check`. |
| `scripts/gen_sol_goods_tooltip.py` | 303 | Copies vanilla `goods_details.gui` and injects the substitute-group section; emits `SOL_substitutes_l_*.yml` (~115 per-good keys). Same flags. |
| `scripts/sol_goods_order.py` | 108 | Grouping/ordering from `data/goods_weights.csv`. `ordered()` (group order, ungrouped last), `group_rows()` (label + members). |
| `scripts/sol_goods_ui.py` | 175 | **The single renderer for the goods block.** `render_goods_vbox` / `replace_goods_vbox` / `GROUP_LABELS`. PP and JTG generators import it. |

### Changed — generators

* `scripts/gen_sol_chain.py` — now calls the two new generators inside the `base_targets`
  block, **before** the compatibility generators (which rebuild the goods block inside
  their own output). Without this a build ships stale UI; this was a real gap found
  while writing this doc.
* `scripts/gen_sol_pp_compat.py` — `_render_gui` rebuilds the whole goods vbox via
  `replace_goods_vbox` instead of inserting victuals by line + spacer arithmetic. Drops
  `GOODS_PER_ROW`; drops `_victuals_widget`.
* `scripts/gen_sol_jtg_compat.py` — same rebuild; **removed its alphabetical sort**
  (`sorted(combined, key=...)`), which would have silently undone the group order.
  Drops its local `_goods_widget` / `_render_goods_vbox` / `GOODS_PER_ROW`.
* `scripts/gen_sol_mnt_compat.py` — **untouched and unaffected.** It only builds
  `location_window.gui` (a launcher button) and CMF scripted GUIs; it contains no goods
  grid. Verified.

### Changed — renderer

* `ai_gui_assessment/renderer/scen_location.py` — added `goods_tooltip(good="wine")`.
* `ai_gui_assessment/renderer/scenarios.py` — re-exports it.
* `ai_gui_assessment/renderer/run.py` — added the `goods_tooltip` entry point.

### Changed — localization

* `src/{stable,sol_standalone}/main_menu/localization/{english,simp_chinese}/SOL_economy_l_*.yml`
  — shortened `GLS_PANEL_INFO_BODY` so it fits one line (it was orphaning `。` onto a
  second line).
* New generated: `SOL_ls_ui_l_*.yml` (UI vocabulary) and `SOL_substitutes_l_*.yml`
  (per-good substitute membership) in both targets.

### Docs updated this session

`docs/knowledge/anti_patterns.yaml` (+5 entries), `docs/guides/AI_Tool_Workflow_Prompt.md`
(violations table), `docs/guides/EU5_GUI_Modding_Guide.md` (layout/texture/text rules),
`docs/knowledge/PROJECT_OVERVIEW.md`, `docs/knowledge/BRIEF.md`.

---

## 4. Commands

```powershell
# Generate everything (regenerates all five targets)
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_chain.py

# Check without writing
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_chain.py --check

# Just the UI (both targets, or one)
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_ls_gui.py --target stable
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_goods_tooltip.py

# Render for visual checking (output -> ai_gui_assessment/images/<RENDER_OUT>/)
$env:PYTHONUTF8='1'; $env:RENDER_OUT='lsgui'; & $env:EU5_PYTHON ai_gui_assessment/renderer/run.py tooltip
$env:PYTHONUTF8='1'; $env:RENDER_OUT='lsgui'; & $env:EU5_PYTHON ai_gui_assessment/renderer/run.py situation
$env:PYTHONUTF8='1'; $env:RENDER_OUT='lsgui'; & $env:EU5_PYTHON ai_gui_assessment/renderer/run.py goods_tooltip wine

# Validate
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/validate.py --changed
```

`EU5_PYTHON` = `C:\Users\Hades\anaconda3\envs\eu5\python.exe`.

---

## 5. Verified state

| Check | Result |
|---|---|
| `gen_sol_chain.py --check` (all five targets) | **OK** |
| `validate.py --changed` | **OK** — 24 files, no issues |
| Location tooltip render | **492 × 933**, 0 unknown expressions |
| Situation panel render | 0 unknown expressions |
| Goods tooltip render (`wine`) | **442 × 372**, 0 unknown expressions in SOL code |

Images: `ai_gui_assessment/images/lsgui/` — `r3_location_sol_tooltip.png`,
`r1_situation_panel.png`, `r4_goods_tooltip.png` (plus `*_tree.txt` element dumps).
`_pie_test.png` and `_ring_zoom.png` are my scratch probes; safe to delete.

The goods tooltip's 10 reported "unknown expressions" are all vanilla
`StringPairList.*` / mapmode calls — pre-existing renderer gaps, **not** SOL code.

---

## 6. Open items, in priority order

1. **Nothing is verified in game.** Every check so far is the renderer. The renderer
   reproduces the engine's layout rules (it caught the column collapse and the width
   blow-up, and those fixes are correct by its rules), but the three surfaces have not
   been launched. **This is the first thing to do.** Expect the goods-icon rows and the
   piechart to be the likeliest divergence.
2. **The goods-tooltip icon is a `paint_brush` behaviour question.** `sol_goods_ui.py`
   emits an explicit `icon = { texture = "gfx/interface/icons/trade_goods/icon_goods_<good>.dds" }`
   per good rather than the `@<good>!` texticon, because the old SOL grid special-cased
   `camels` and I could not confirm the inline form resolves for compat goods. Compat
   goods ship their own DDS at that path (PP `3613232232` victuals, JTG `3785316314`
   aromatics). If the inline texticon does work everywhere, it is the cheaper option.
3. **`sol_market_price_suppressed_*` is now computed in script but displayed nowhere.**
   The old grid drew a red down-arrow for consumed-but-expensive goods; I replaced that
   with dimming for not-consumed. Decide whether the suppression signal should come
   back — it is real information the panel used to show. If it returns, it belongs on
   the market-scoped tooltip, not the country panel: the map is market-keyed and the
   country scope has no market (this caused 56 unknown expressions before I removed it).
4. **Both surfaces are ~933px against a 1080px screen.** There is room; the density
   question is open. Options discussed: more breathing room in the goods block, or
   merging the consumption coefficient into one line.
5. **Uncommitted.** 42 paths, including 6 new files and 4 new generated localization
   files. Needs a commit — probably more than one (kit + generators; the two compat
   generator rewrites; docs).
6. **Docs note:** if the compat-generator rewrite and the UI redesign are committed
   separately, `PROJECT_OVERVIEW.md` and `BRIEF.md` are already updated for both.

---

## 7. Gotchas that cost real time here

These are now in `docs/knowledge/anti_patterns.yaml` and the GUI guide — read them
before editing the kit:

* **`autoresize = yes` beats a declared `size`.** `text_single` inherits it. Every fixed
  column needs `autoresize = no` or it collapses to content width and the columns fuse
  into one run of digits.
* **A wrapping text with no `max_width` reports its *unwrapped* width as a minimum.**
  An hbox measures its children with no width hint, so one uncapped paragraph drags the
  entire tooltip past its frame. Every `sol_note` body needs an explicit `max_width`.
* **`text` localizes; `raw_text` is literal.** A key in `raw_text` prints raw. Labels use
  `text`; expressions, `@icon!` and `#colour…#!` go in `raw_text`.
* **A `blockoverride` replaces a block entirely and cannot parameterize siblings.** One
  container block per row (`sol_cells`, `sol_ledger_cells`), filled by the caller —
  otherwise five cells land *alongside* five defaults and you get ten.
* **`TooltipListBase` already emits a `TooltipTableHeader`.** A caption overrides it;
  adding a body stacks a second header and doubles the band height.
* **`pieslice` colour must be a literal `{ r g b a }`** — no named colours. Slice values
  are normalised, so pass raw counts. Pop colours come from
  `main_menu/common/named_colors/02_map.txt` (hsv360 → RGB).
* **A generated block that can change shape must be rebuilt, not line-patched.** The
  PP and JTG generators used to insert a good by line and compensate for a spacer
  count, which encodes the old flat-lattice layout; both now rebuild the whole vbox
  through `sol_goods_ui.py`.

---

## 8. Quick orientation for the next session

1. Read `docs/knowledge/BRIEF.md` (project rule) — it now carries the new anti-patterns.
2. Read the header comment of `src/stable/in_game/gui/SOL_living_standard_kit.gui` —
   budgets, the two width traps, and why each row exposes one container block.
3. Read `scripts/gen_sol_ls_gui.py`'s `render_tooltip` / `render_panel` — the structure
   lives in the generator, not hand-edited into the `.gui`.
4. **Do not hand-edit the three generated surfaces.** They are overwritten by
   `gen_sol_chain.py`. Change the kit or the generators instead.

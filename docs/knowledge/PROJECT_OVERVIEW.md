# EU5 Mod — Project Overview

> This document is maintained by AI. Update it whenever mod features or directory structure change.
> Last updated: 2026-05-03 (Dynamic export alpha coefficient via sol_era_coeff + local_sol_scarcity_adj)

## Project Identity

- Mod name: **Standard of Living (SOL)**
- Mod ID: `hades.sol` | Version: `1.1.0` | Target: EU5 `1.*.*`
- Requires Community Mod Framework v2.*
- Two active branches: `stable` (release) and `beta` (active development)

## Core Features

1. **War & Combat (Harsher Wars)** — War exhaustion has 3–4× greater impact on morale, levy size, stability, and legitimacy. Capital occupation yields +300% exhaustion, total occupation +400%. Increased sea-landing penalties and combat losses.

2. **Anti-Snowballing** — Building costs scale with age (+200% by Age 6). RGO expansion costs rise similarly. Base RGO size halved (1 vs. vanilla 2). Road construction costs: gravel ×2, paved ×3, modern ×4, railroad ×10.

3. **Tax Efficiency** — Base −15% tax efficiency applied to all countries. Bonuses remain meaningful but reduced, preventing tax-stacking dominance.

4. **Prosperity & Economic Decay** — Monthly prosperity decay decreases per age, modelling the world gradually becoming more prosperous. Ice Age event food penalties softened.

5. **Colonial Restrictions** — AI requires a tax base of 1000 (vs. vanilla 100) to colonize. Colonial nations restricted to capital-region colonization. Historical colonizers (Portugal, Spain, England, etc.) are exempt.

6. **Standard of Living (SOL) System** *(primary feature)* — Replaces static vanilla pop demands with dynamic, income-aware Engel curves. Implements 20 substitute-goods groups, a 6-tier price-scarcity system, and location-level demand caching. Pops shift consumption to cheaper substitutes when goods are scarce. Feeds back into a country-level SOL situation with a dedicated UI panel and map overlay.

## Directory Structure

```
eu5-modding-project/
├── src/
│   ├── stable/                  — active mod source (released)
│   │   ├── .metadata/           — metadata.json (mod ID, version, dependencies)
│   │   ├── in_game/
│   │   │   ├── common/
│   │   │   │   ├── age/         — age-scaling building/prosperity modifiers
│   │   │   │   ├── auto_modifiers/   — war exhaustion, tax efficiency penalties
│   │   │   │   ├── cabinet_actions/  — war exhaustion reduction, institution spread
│   │   │   │   ├── diplomatic_costs/ — rebalanced diplomatic action costs
│   │   │   │   ├── generic_actions/  — colonial charter restrictions
│   │   │   │   ├── goods/            — good definitions (fish as food category)
│   │   │   │   ├── goods_demand/     — pop goods demand injections (SOL system)
│   │   │   │   ├── on_action/        — trigger hooks
│   │   │   │   ├── prices/           — price adjustments (roads, diplomacy)
│   │   │   │   ├── resolutions/      — resolution definitions
│   │   │   │   ├── scripted_effects/ — country gold effects
│   │   │   │   ├── scripted_guis/    — custom GUI logic
│   │   │   │   ├── scripted_triggers/— custom trigger definitions
│   │   │   │   ├── script_values/    — SOL computation values (46+ files)
│   │   │   │   ├── situations/       — Standard of Living situation definition
│   │   │   │   └── trigger_localization/ — custom trigger text
│   │   │   ├── events/          — event definitions
│   │   │   ├── gui/
│   │   │   │   ├── panels/      — situation panels (global_living_standard.gui)
│   │   │   │   └── scripted_widgets/ — custom GUI widgets
│   │   │   └── loading_screen/common/defines/ — harsher combat defines
│   │   └── main_menu/
│   │       ├── common/
│   │       │   ├── script_values/    — tax efficiency bonus values
│   │       │   └── static_modifiers/ — country, location, province modifiers
│   │       └── localization/
│   │           ├── english/          — English UI strings
│   │           └── simp_chinese/     — Simplified Chinese UI strings
│   └── develop/                 — paused development branch (Dynamic Missions)
├── docs/
│   ├── knowledge/               — BRIEF.md, anti_patterns.yaml, valid_enums.yaml, PROJECT_OVERVIEW.md
│   ├── design/                  — SOL rebuild design doc, other active feature designs
│   ├── guides/                  — AI_Tool_Workflow_Prompt.md
│   ├── technical/               — EU5_Modding_Knowledge_Base.md, mod framework guide
│   ├── simulator/               — SOL simulator data and configs
│   └── archive/                 — archived design docs (paused features)
├── scripts/                     — Python codegen + validation (see Script Reference)
├── tools/
│   └── sol_demand_simulator/    — Engel curve designer + exporter (web UI via app.py)
├── data/                        — CSV demand tables, alpha bracket tables, settings JSON
├── assets/                      — images and media
├── build/                       — built mod output (deployed to Steam mod folder)
├── reference_game_files/        — vanilla EU5 script references
├── reference_mods/              — 18+ community mod examples
└── reference_official_defines/  — official EU5 syntax/type definitions
```

## Script Reference

| Script | When to run | Output |
|---|---|---|
| `gen_scarcity.py` | After editing scarcity tier data | `SOL_substitute_effects.txt`, `SOL_substitute_good_indicators.txt`, `SOL_goods_weight_values.txt`, scarcity localization |
| `gen_sol_ui.py` | After UI layout changes | `location_window.gui`, `SOL_substitute_tooltip.gui`, `global_living_standard.gui`, effects anchors |
| `gen_pop_goods.py` | After editing `target_demand.csv` | `z_SOL_pop_goods.txt` (pop goods demand injections) |
| `gen_demand_csv.py` | After demand calibration | `data/demand_price_table.csv` |
| `gen_brief.py` | After editing `*.yaml` or `PROJECT_OVERVIEW.md` | `docs/knowledge/BRIEF.md` (also calls `gen_index.py` automatically) |
| `gen_index.py` | Called by `gen_brief.py`; or run manually after structural changes | `data/index/` symbol indexes (icons, triggers, effects, modifiers, loc keys) |
| `gen_scaffold.py` | When creating a new EU5 file (event, effect, trigger, modifier, etc.) | Syntactically valid skeleton file with TODO markers |
| `validate.py` | Before launching game (`--changed` flag); `--ai-report` for JSON output | Console validation report; exit code indicates pass/fail |

Also: `gen_scarcity.py` is now split into focused submodules under `scripts/scarcity/` (effects_gen, weights_gen, indicators_gen, loc_gen, gui_gen). The top-level script remains the single entry point.

## Data Files

| File | Purpose |
|---|---|
| `data/target_demand.csv` | Source of truth: desired demand per pop type per good |
| `data/demand_price_table.csv` | Computed demand matrix (validated against vanilla) |
| `data/goods_weights.csv` | Good-to-substitute-group mappings |
| `data/alpha_bracket_table.csv` | Engel curve segment values (budget share by income bracket) |
| `data/alpha_generator_settings.json` | Engel curve design parameters |

## SOL System Architecture (Key Design Notes)

- **20 Substitute Goods Groups** (e.g., Luxury Drinks, Basic Clothing, Staple Food) — pops reallocate budget within a group when a good becomes scarce.
- **6-Tier Price Scarcity System** — price-based demand weight redistribution across group members.
- **Engel Curves** — income-dependent consumption patterns per pop stratum, parameterised in `tools/sol_demand_simulator/`.
- **Location-level caching** — monthly wealth + yearly location averages stored as script values for performance.
- **Country-level aggregation** — savings pressure per pop stratum, SOL per stratum, feeds the situation panel.
- **Hidden shim** in `SOL_goods_demand_values.txt`: dev-scaling cancellation (`×10 ÷ location.development`) — intentional, do not remove.
- **Dynamic export alpha coefficient** — `global_var:sol_era_coeff` (init 2.0, decays ×0.95/era via `sol_update_export_adj_era`) and `local_sol_scarcity_adj` script_value (±20% per-market basket correction) are injected into every demand-scale block in `z_SOL_group_demand_scales_location.txt`. Replaces the former baked-in EXPORT_ALPHA_MULTIPLIER = 2.0 in `engel_export.py`.

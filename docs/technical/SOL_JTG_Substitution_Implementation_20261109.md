# JTG substitution implementation audit — 2026-11-09

The JTG-only profile adds exactly 30 unique direct-demand goods to the original 56, retaining the original 20 groups, subscriptions, historical group sizes and Algorithm A. Twelve demand-free goods remain excluded; tribesmen and slaves have zero demand. No deployment or publication was performed; engine runtime and existing-save behavior remain unverified.

## Quantity and budget contract

Only the approved 11 cells change. All previous positive quantities remain unchanged; these additions bypass legacy historical scaling. The permanent provenance fixture scripts/fixtures/jtg_quantities_before_grouping_20261109.json records the task-start working-tree quantities, rather than git HEAD. The temporary full snapshot and 243-file default-target hashes are in tmp/jtg-substitution-baseline/.

Nominal default-price budget, before substitution (population-unit convention inherited from generated rows):

| Stratum | JTG before | JTG after | Combined before | Combined after | Increase |
|---|---:|---:|---:|---:|---:|
| nobles | 7.36 | 7.36 | 18.62776 | 18.62776 | 0 |
| clergy | 0.867 | 0.96942 | 2.180905 | 2.283325 | 0.10242 |
| burghers | 0.9187 | 0.9187 | 2.339025 | 2.339025 | 0 |
| laborers | 0.0015 | 0.003105 | 0.022985 | 0.02459 | 0.001605 |
| peasants | 0.00564 | 0.00585 | 0.02372 | 0.02393 | 0.00021 |
| soldiers | 0.0023 | 0.00362 | 0.033705 | 0.035025 | 0.00132 |
| tribesmen | 0 | 0 | 0 | 0 | 0 |

Slaves: zero before and after. Budget increases arise only from the 11 approved added quantity cells.

## Independent verification

The profile tests independently enumerate the approved mapping and quantity additions. The runtime fixture executes compatibility-rendered script bodies, using the real on-disk base 56 plus new JTG 30 auto-modifier and script-value definitions, and asserts 86 unique modifier definitions. It checks neutral prices, changed prices, overlapping groups, missing supply, external correction, repeated refresh without economic drift, toggle cleanup/re-enable, two populated countries sharing one market with owner switching, and population-weighted two-market aggregation. An old-cache fixture tests missing profile schema triggers the existing world-refresh entry point once; the world-refresh body is stubbed at that boundary, not represented as a full engine simulation.

All 86 goods have seven marker branches and contextual hover membership checked against the profile. The earlier lazaretto source-preservation/order/authoritative-hook and duplicate-cloves audits remain enabled. Default-target hash comparison is a one-time audit, not a permanent test tied to temporary files.

The previous broad UI suite remains a known 6-failure/1-error control (identical with the previous shared-module baseline), not a passing suite. Final renderer and generator results are recorded below as they complete.

## Recorded checks

- JTG tests: 19 passed (7 existing compatibility, 3 overlap, 3 profile/UI, 6 generated runtime). External-demand API/runtime tests: 2 passed; 21 total.
- Final JTG generator check: 16 outputs current, reported by implementing agent.
- Task-start 243 non-JTG files: SHA-256 unchanged after final JTG generation.
- BRIEF regenerated; dual-root migration/ID coverage passed (131 migration entries, 374 shared + 57 local rules).
- Static validator reports 30 unknown modifier errors for the 30 new JTG global goods modifiers because its whitelist contains vanilla definitions only. The dependency declarations are independently checked by the external-demand test. The initial run was an actual failure (not warnings), retained in tmp/jtg-substitution-validation.log. The validator was subsequently fixed to accept trusted, identity-matched, declared JTG dependency modifier definitions only; typo, wrong-target and nested-only declarations remain rejected. Final --changed --ai-report: 18 files, pass=true, errors=[], warnings=[], exit 0 (tmp/jtg-substitution-validator-final.json). Explicit new auto-modifier file validation also passes (tmp/jtg-modifiers-validate.json); validator regression suite: 17 passed.
- An intermediate broad UI run reported 8 failures and 1 error versus the previous 6 failures and 1 error. The two added JTG failures came from the test assuming fixed 122×66 single-row cards. JTG-specific assertions now check all 20 groups, 86 unique goods, ceil(member-count/6) rows, at most six per row and in-card boundaries. Alongside uniform row-height/top-alignment, the targeted layout run no longer reports JTG failures and retains only the two pre-existing PP layout failures. The main agent viewed tmp/jtg-final-zh/r1_situation_panel_full.png and confirmed top alignment. This targeted result does not claim the whole broad suite passes; final full-suite status remains separate.

The main agent independently reran 19 JTG, 2 external-demand and 17 validator tests: all passed. Final generator/Workshop audit passed 16 outputs and 42/30/12 source goods. The audit agent independently reran changed-source validation: 18 files, no errors or warnings (tmp/jtg-substitution-validation-final.json); 243 default-target hashes still match the task-start baseline.

Targeted layout log: tmp/jtg-layout-test.log. The JTG location tooltip is 520×1048, within the 1080-pixel viewport; wide group cards wrap instead of clipping. English final render was completed and viewed by the UI agent: tmp/jtg-final-en/r3_location_sol_tooltip.png (520×1048), r4_market_luxury.png (15 members, height 477), and r4_market_spices.png (11 members, height 448); Chinese counterparts are in tmp/jtg-final-zh. Vanilla statistics, market/base ratio 1.42, and seven-tier 0.75 highlight remain visible. English six-JTG-item HUD rendered with zero unknown expressions (hud_six_jtg_slots.png / hud_six_jtg_slots_detail.png). The bilingual neutral/up/down/missing/off matrix completed in tmp/jtg-profile-{simp_chinese,english}-{neutral,up,down,missing,off}, retaining only the prior one-expression/one-context fixture baseline.

Main-agent full-source validation: 187 files, pass=true, errors=[], warnings=[], exit 0.

Additional legacy HUD suite: 20 failing assertions apply to stable/standalone rather than JTG. Those default products remain byte-identical across the task-start 243-file hash audit; the shared HUD profile branch is active only with an explicit profile. No claim is made that this broad suite passes, and unrelated legacy assertions were not expanded into this compatibility change.

Final long-label correction is JTG-only: goods-details chips now use two 145-pixel columns rather than four 72-pixel columns, retaining default-target output. Final English renders (Chinese counterparts in tmp/jtg-final-zh): tmp/jtg-final-en/market_brassware.png 440×593, market_cinnamon.png 440×535, market_precision_instruments.png 440×419. All have zero unknown expressions; Precision Instruments spans x303..448 within the content right boundary 450, and Lacquerware fits. UI agent final generation/check: all 16 outputs current.

The 20 legacy HUD failing assertions involve test_foreign_country_map_tooltips_keep_the_primary_country (expected year 1338 absent; ranking unresolved country context) and test_sol_table_fills_content_and_stays_inside_frame (intrinsic_width differs from table_row.w, e.g. 77/119 versus 190). Their scope is stable/standalone, not the JTG profile; the agent did not save a separate log, so these are reported from its actual tool output rather than inventing a log artifact.

## Localization composition follow-up

JTG group cards, goods-detail labels and compact hover now share SOL-owned group keys through SOL_GOOD_GROUP_NAME_<GROUP> → SOL_SUBGROUP_<GROUP>. Knowledge resolves consistently as Knowledge / 知识. Commodity names remain owned by the original goods keys; auto-modifier names/descriptions compose those keys rather than overriding JTG translations. Independent offline tests resolve recursive key chains and simulate two alternate Chinese plaster/precision_instruments translations, verifying GUI Localize operands and auto labels follow both changes. This validates offline composition, not engine runtime localization. Original-name ownership, UTF-8 BOM and full bilingual key parity are checked separately.

Localization follow-up independent suite: 4 tests passed, including complete JTG English/Chinese key-set parity after explicit bilingual Knowledge group keys. The current generator check is 15/16: market_tooltips.gui differs only in a non-localization widget, TooltipScrolledStringPairList on disk versus TooltipStringPairList from the source template for Market.GetBurgherTradeInfo. This unrelated GUI content was not overwritten by the localization audit.

# SOL-PP Compact Compatibility Submod

This target is a late-loading compact compatibility layer for Standard of
Living and Prosper or Perish. It is not a standalone mod.

Load order:

1. Community Mod Framework
2. Prosper or Perish
3. Standard of Living
4. SOL-PP Compatibility Submod

The PP reference metadata currently has an empty mod ID, so metadata can only
declare Standard of Living as a formal dependency. Prosper or Perish must be
enabled manually.

The submod keeps PP's economic systems authoritative while retaining SOL's
Purchasing Power, SOL, demand accounting, country solver, substitution groups,
living-standard modifiers, UI and non-economic features. PP's `victuals` remains
a trade, building and logistics good, but its final population demand and all
SOL consumption paths are zero. PP's `silk` adds a seventh `luxury_goods`
member only in this target; the existing luxury budget is rebased so the group
does not grow on the first compatibility pass.

It disables SOL's seven Economic Balance groups: base tax efficiency, age
economic escalation, stability spending discount, diplomatic spending, difficulty
tax adjustments, GDP-to-development, and AI prosperity recovery. It also
neutralizes SOL's base location/RGO rebalance, winter and Little Ice Age
rebalance, and the food, RGO, and prosperity portions of age escalation. PP owns the
shared blockade, siege, occupation, and looting location modifiers: their SOL
deltas are canceled. PP owns shared price values as well, so SOL's road deltas
are not cleaned up by this submod: repeated price scalars replace instead of
adding, and `pp_road_gold_adjustments.txt` loads after
`A_SOL_economy_prices.txt`. PP's institution replacement wins as well.

The demand layer cancels SOL's remaining lumber pop demand, adds PP `silk` to
SOL living-standard spending and substitution, and overrides both SOL goods
display panels. It explicitly replaces the two SOL scripted effects whose market
and country aggregation bodies must change; unchanged full-SOL database objects
are not duplicated. The generator validates PP `0.10.0` at upstream commit
`967cadbe` before producing output.

The compact CMF panel is rebuilt from an explicit whitelist. It exposes only
settings backed by active compact behavior; the disabled `gdp_dev` setting and
callback are omitted. CMF clears each group's old setting list during
registration, so the obsolete entry is also removed from upgraded saves.

All freely named game-data and GUI files use the `zz_` load-order prefix.
`gui/panels/situation/global_living_standard.gui` is the sole exception because
EU5 requires a situation panel filename to match its situation ID exactly.

Generated compatibility files are refreshed with:

```powershell
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_chain.py --target sol_pp_compatibility_submod
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_chain.py --target sol_pp_compatibility_submod --check
```

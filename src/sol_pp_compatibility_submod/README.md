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

The submod keeps all PP systems active, while limiting SOL gameplay to:

- income-based pop demand and its UI, including PP `victuals`;
- age-scaled building efficiency and city/town upgrade costs;
- low-control construction efficiency;
- the default -15% base tax efficiency;
- difficulty tax-bonus adjustments and configurable AI devastation recovery;
- diplomatic-capacity spending and cultural-tradition stability discounts;
- harsher war exhaustion, enemy-troop/raiding/razing, colonial, and call-to-war restrictions;
- SOL gold transfer and non-conflicting action-price changes.

It neutralizes SOL's GDP-to-development, base location/RGO rebalance, winter and
Little Ice Age rebalance, and the food, RGO, and prosperity portions of age
escalation. PP also owns the
shared blockade, siege, occupation, and looting location modifiers: their SOL
deltas are canceled. PP owns shared price values as well, so SOL's road deltas
are canceled and PP's institution replacement wins.

The demand layer cancels SOL's remaining lumber pop demand, adds PP `victuals`
to SOL market spending, and overrides both SOL goods-display panels.
It adds only the new `victuals` script values and explicitly replaces the two
SOL scripted effects whose market and country aggregation bodies must change;
unchanged full-SOL database objects are not duplicated.

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

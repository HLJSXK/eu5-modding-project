# SOL-PP Compatibility Submod

This target is a compatibility layer for Standard of Living and Prosper or
Perish. It is not a standalone mod.

Load order:

1. Community Mod Framework
2. Prosper or Perish
3. Standard of Living
4. SOL-PP Compatibility Submod

The PP reference metadata currently has an empty mod ID, so metadata can only
declare Standard of Living as a formal dependency. Prosper or Perish must be
enabled manually.

The submod restores PP's intended Little Ice Age and weather/disaster modifier
results after SOL, cancels SOL's remaining lumber pop demand, adds PP victuals
to SOL market spending, and overrides both SOL goods-display panels.

All freely named game-data and GUI files use the `zz_` load-order prefix.
`gui/panels/situation/global_living_standard.gui` is the sole exception because
EU5 requires a situation panel filename to match its situation ID exactly.

Generated compatibility files are refreshed with:

```powershell
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_chain.py --target sol_pp_compatibility_submod
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_chain.py --target sol_pp_compatibility_submod --check
```

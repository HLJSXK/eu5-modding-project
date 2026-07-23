# SOL-M&T Compatibility Submod

This is a final-loading compatibility layer for MEIOU and Taxes and the full
Standard of Living mod. It is not standalone.

Required load order:

1. Community Mod Framework
2. MEIOU and Taxes
3. Standard of Living
4. SOL-M&T Compatibility Submod

M&T remains authoritative for prices, production, food, RGO, buildings,
estates, climate, and other economic balance. The compatibility layer retains
SOL's income-based pop demand, Living Standard UI/map, migration support, and
non-conflicting war, colonial, and diplomatic rules.

Population quantities start from SOL's final seven-pop matrix. Quantities are
scaled inversely against M&T default prices so default-price spending remains
as close as EU5's five-decimal fixed-point precision permits. Maize, millet,
and rice use equal quantities per pop while preserving their combined SOL
spending within that precision. Tools receives only the generic price scaling,
so laborer demand is `0.0005`; M&T's special `0.002` quantity is not retained.
All wealth and development demand gates remain removed.

The compatibility replacement of `epbm_calculate_maintenance` preserves M&T's
original calculation and charge variables while caching domestic final costs
on locations for SOL. Foreign and government buildings are excluded only from
SOL attribution. Dhimmi and Gaelic-clan tribes costs remain unassigned; normal
tribes and cossacks map to SOL tribesmen.

Generated files are refreshed with:

```powershell
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_chain.py --target sol_mnt_compatibility_submod
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_chain.py --target sol_mnt_compatibility_submod --check
```

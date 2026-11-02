# SOL-M&T Compatibility Submod

This is a final-loading compatibility layer for MEIOU and Taxes and the full
Standard of Living mod. It is not standalone.

Required load order:

1. Community Mod Framework
2. MEIOU and Taxes
3. Standard of Living
4. SOL-M&T Compatibility Submod

Validated against MEIOU and Taxes `0.2.12` for EU5 `1.4.*`. M&T remains
authoritative for economic balance, prices, production, food, RGO, buildings,
estates, climate, and maintenance. The compatibility layer retains SOL's
income-based pop demand, goods substitution, Living Standard UI/map, and
migration support.

Population quantities start from SOL's final seven-pop matrix. M&T nobles
receive a compatibility-only `x2` basket multiplier, selected after the latest
combined M&T+SOL 1340 save showed median noble purchasing power of about `+82%`.
The other six population baskets retain their existing quantities. After this
multiplier, quantities are scaled inversely against M&T default prices so
default-price spending follows the calibrated basket budget within EU5's
five-decimal fixed-point precision. Maize, millet, and rice use equal quantities
per pop while preserving the corresponding basket spending within that
precision. Tools laborer demand remains `0.002`. All wealth and development
demand gates remain removed.

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

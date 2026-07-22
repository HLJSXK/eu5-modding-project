# SOL-JTG Compact Compatibility Submod

This target is a late-loading compatibility layer for Standard of Living and
the five Just Trade Goods mods. It is not a standalone mod.

Load order:

1. Community Mod Framework
2. Just Brass, Just Meat, Just Soap, Just Spices, and Just Cheese (any order)
3. Standard of Living
4. SOL-JTG Compatibility Submod

All five JTG mods are required. Just Spices currently has an empty metadata ID,
so it cannot be declared as a formal dependency and must be enabled manually.

The submod applies SOL's approximate per-stratum demand scaling to the 22 JTG
goods that have direct pop demand:

- nobles: 1.05
- clergy: 0.45
- burghers: 1.75
- laborers: 0.02
- peasants: 0.10
- soldiers: 0.025
- tribesmen: 0

Scaled targets are rounded with magnitude-aware steps: values at or above 0.01
use 0.01 increments, then smaller values use 0.001, 0.0001, or 0.00001
increments. This keeps the visible balance values compact without erasing the
small commoner quantities.

Slave demand remains owned by the JTG mods and is not changed. The compatibility
layer also adds the 22 final quantities to SOL's market unit-spending cache and
shows all 77 SOL + JTG demand goods in both SOL goods panels.

The SOL-JTG and SOL-PP compatibility submods replace the same two SOL scripted
effects and are mutually exclusive. A combined PP + JTG stack requires a
separate merged compatibility target.

Generated compatibility files are refreshed with:

```powershell
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_chain.py --target sol_jtg_compatibility_submod
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_chain.py --target sol_jtg_compatibility_submod --check
```

To audit the checked-in demand data against an installed Workshop copy:

```powershell
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_jtg_compat.py --check --audit-workshop-root "C:\Program Files (x86)\Steam\steamapps\workshop\content\3450310"
```

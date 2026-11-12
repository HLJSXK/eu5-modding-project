# SOL-JTG Compact Compatibility Submod

This target is a late-loading compatibility layer for Standard of Living and
Just Goods. It is not a standalone mod.

Load order:

1. Community Mod Framework
2. Just Goods
3. Standard of Living
4. SOL-JTG Compatibility Submod

Just Goods is required as a formal dependency.

The submod applies SOL's approximate per-stratum demand scaling to the 30 Just
Goods goods that have direct pop demand:

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

Every `wealth_impact_threshold`, `development_threshold`, and regional demand
modifier supplied by Just Goods on those direct pop-demand goods is fully
negated, matching SOL's development-independent and income-driven demand model.
The checked-in data and Workshop audit track these fields so future Just Goods
gates cannot be missed silently.

Slave and tribesmen demand is zero. Twelve demand-free JTG goods remain excluded. The compatibility
layer also adds the 30 final quantities to SOL's market unit-spending cache and
shows all 86 SOL + JTG demand goods in both SOL goods panels.

All 30 demand goods join the original 20 substitute groups through an explicit JTG-only profile; subscriptions, historical group sizes and Algorithm A stay unchanged. Eleven explicit quantity additions complete subscribed groups without rescaling prior positive demand. The 86 goods share substitution markers, contextual tooltips and the six-slot HUD.

The SOL-JTG and SOL-PP compatibility submods replace shared SOL scripted
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

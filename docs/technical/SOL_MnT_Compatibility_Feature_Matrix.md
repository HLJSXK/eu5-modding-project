# SOL-M&T Compatibility Feature Matrix

Date: 2026-11-12

Validated source: MEIOU and Taxes `0.2.13`, EU5 `1.4.*`. M&T noble demand uses
an additional `x2` compatibility multiplier based on the combined-mod 1340
save (`+82.3%` median noble purchasing power before adjustment); other baskets
remain at their existing calibration.

## Stack Contract

Required load order:

1. Community Mod Framework
2. MEIOU and Taxes
3. Full Standard of Living
4. SOL-M&T Compatibility Submod

The compatibility submod is the final rules layer. M&T owns economic balance;
SOL owns its calibrated pop-demand and Living Standard presentation.

## Demand Resolution

| Area | Final behavior |
| --- | --- |
| Seven SOL pop types | M&T nobles receive a compatibility-only `x2` basket multiplier; the other six types are unchanged. Final quantities are then multiplied by `SOL price / M&T price` and rounded to EU5's five-decimal precision. |
| Maize, millet, rice | Each pop receives one equal quantity across all three goods; combined spending follows its calibrated basket budget within fixed-point rounding. |
| Tools | Laborer demand is `0.002`, following the SOL demand matrix and price conversion. |
| Slaves | Final slave goods demand is cancelled, including native generic demand. |
| Demand gates | All wealth and development thresholds are removed, and SOL's engine-wide development multiplier disable remains active. |
| Other goods fields | M&T price, production, food, transport, RGO, climate, origin, and availability fields remain unchanged. |

## Maintenance Resolution

The compatibility target replaces `epbm_calculate_maintenance` with the exact
M&T body plus marked location-cache insertions. M&T's country totals, shared
pool, assigned costs, crown costs, and actual deductions are unchanged.

| Cost source | SOL location attribution |
| --- | --- |
| Domestic nobles/clergy/burghers estate costs | Direct matching SOL stratum |
| Domestic peasants estate costs | Commoners |
| Domestic cossacks costs | Tribesmen |
| Domestic non-Gaelic tribes costs | Tribesmen |
| Domestic dhimmi and Gaelic tribes costs | Temporarily ignored by SOL |
| Domestic shared-pool costs | Allocated at the building location using M&T's estate powers and charge factor |
| Foreign and government/crown buildings | Remain in M&T charges but are ignored by SOL location attribution |

SOL's original one-gold-per-estate-building scan is replaced with an empty
effect, so it cannot overwrite the EPBM-derived location variables.

## SOL Feature Boundary

Retained: income-based demand, goods substitution, Living Standard
situation/map/location UI, and migration support.

Removed: base tax, age escalation, difficulty tax changes, AI recovery,
GDP-to-development, dynamic diplomatic spending, cultural-tradition stability
discount, SOL prices and gold-transfer scaling, location/RGO/low-control balance,
winter/raised-levy food changes, and Little Ice Age balance.

CMF exposes the SOL core controls; the compatibility-specific economic master
remains default-off. MnT owns prices, economic static modifiers, building
maintenance, food, RGO, and construction balance.

## Verification Boundary

### MnT 0.2.13 source audit (2026-11-12)

The upstream `Documentation/Change log.md` lists starvation severity scaling,
trade-route and food-production balancing, and tribal livelihood buildings.
Rendering against the current reference changes only one of the 14 generated
files: `zz_SOL_MnT_economic_static_authority.txt`. Its `province_starving`
replacement now comes from MnT's `MnT_location.txt`, without the vanilla fixed
`local_population_growth = -0.05` and `local_life_expectancy = -10` penalties.
MnT's `mnt_food_starvation_severity` auto modifier owns those scaled penalties;
retaining the old replacement would add fixed mortality on top of them.

Goods, spending values, EPBM instrumentation, prices, CMM, actions and the
location window render unchanged. The other upstream balance changes can
affect observed SOL through food, prices and income, but this audit found no
additional generated override changes. This is a comparison of the existing
compatch outputs with 0.2.13 plus the upstream changelog, not a complete source
diff against an archived 0.2.12 tree (the available older Git snapshot is 0.2.3).

`scripts/gen_sol_mnt_compat.py --check` pins the reference to MnT 0.2.13 and validates the 56-goods matrix,
price-scaling tolerance, equal grains, `tools`, threshold removal, M&T
non-demand fields, all three EPBM building traversals, unchanged M&T charge
logic, and the marked EPBM source-preservation invariant. It also verifies the
1.4 location window, SOL button, and all six Great Projects queue hooks.
`scripts/validate.py` checks static project syntax. A combined in-game load,
runtime log review, M&T-only charge comparison, and GUI interaction test remain
required before claiming runtime compatibility.

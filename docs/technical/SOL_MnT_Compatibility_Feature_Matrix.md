# SOL-M&T Compatibility Feature Matrix

Date: 2026-07-22

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
| Seven SOL pop types | SOL final quantities are multiplied by `SOL price / M&T price`, then rounded to EU5's five-decimal precision. |
| Maize, millet, rice | Each pop receives one equal quantity across all three goods; combined SOL default-price spending is preserved within fixed-point rounding. |
| Tools | Laborer demand is `0.0005`; M&T's special `0.002` quantity is not retained. |
| Slaves | M&T final slave quantities are retained. |
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

Retained: income-based demand, Living Standard situation/map/location UI,
migration support, war exhaustion and non-conflicting war-location effects,
wartime cabinet restriction, colonial restrictions, and the 30-favor call-to-war
cost.

Removed: base tax, age escalation, difficulty tax changes, AI recovery,
GDP-to-development, dynamic diplomatic spending, cultural-tradition stability
discount, SOL prices and gold-transfer scaling, location/RGO/low-control balance,
winter/raised-levy food changes, and Little Ice Age balance.

CMF exposes only `sol_on`, `sol_map`, `hw_on`, `iwe`, `hwe`, and `rwe`.

## Verification Boundary

`scripts/gen_sol_mnt_compat.py --check` validates the 55-goods matrix,
price-scaling tolerance, equal grains, `tools`, threshold removal, M&T
non-demand fields, and the marked EPBM source-preservation invariant.
`scripts/validate.py` checks static project syntax. A combined in-game load,
runtime log review, M&T-only charge comparison, and GUI interaction test remain
required before claiming runtime compatibility.

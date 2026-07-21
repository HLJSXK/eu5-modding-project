# Standard of Living - Feature List

## Current Status

**Version:** v1.3 beta  
**Scope:** this version only includes basic SOL-based demand scaling plus the retained balance systems listed below.  
**Game target:** Europa Universalis V 1.3 beta environment / 1.* metadata target  
**Dependency:** Community Mod Framework 2.* is used for in-game configuration.

This build exists because EU5 engine changes broke the older SOL 1.2 demand architecture. The current version is intentionally narrower and more stable: it keeps the calibrated pop-demand baseline and replaces the old experimental chain with a local demand coefficient applied through `local_pop_demand`.

There is no v1.2 Workshop version because the engine does not support the previous implementation cleanly. For the older v1.1 branch, use:

[v1.1 version - Standard of Living](https://steamcommunity.com/sharedfiles/filedetails/?id=3706951645)

## Removed Since The Older SOL Design

The following systems are no longer active in the EU5 1.3 beta build:

- Substitute-goods group system.
- Market scarcity tiers.
- Per-good demand redistribution.
- Per-stratum piecewise Engel-curve chain.
- Market-hub scarcity corrections.
- `sol_era_coeff` based old redistribution logic.

Legacy data and scripts may still exist in the repository as reference material, but they are not part of the active runtime.

## Design Goal

Vanilla pop demand is too static for the kind of economy SOL is trying to create. The mod aims to make demand react to actual economic capacity:

- Richer locations should be able to consume more.
- Poorer or overbuilt locations should consume less.
- Estate savings should influence national spending pressure.
- Development must not scale or gate pop demand, so calibrated values remain comparable across locations.
- Markets should influence base spending, but expensive goods should not inflate the baseline infinitely.

The result is a lighter model that is easier to maintain under the EU5 1.3 engine while still making population demand more dynamic than vanilla.

## Core SOL Demand System

### 1. Calibrated Baseline Demand

SOL recalibrates baseline pop demand for 55 goods through `demand_add` injections.
It also sets the engine-wide development demand scale to zero and fully negates every vanilla per-good `development_threshold`.

Source flow:

```text
data/target_demand.csv
-> scripts/gen_pop_goods.py
-> src/stable/in_game/common/goods/z_SOL_pop_goods.txt
```

This baseline remains important. The monthly SOL multiplier scales these corrected `demand_add` values. Removing the baseline would change absolute pop demand before SOL's multiplier is applied.

### 2. Market Unit Spending Cache

Once per year, SOL scans world markets and stores market-keyed spending maps. For each pop type and good, it calculates one-unit base spending using:

```text
unit consumption quantity * min(market price, default price)
```

This means cheap goods can lower base spending, but expensive goods do not push the baseline above vanilla default price forever.

The active market cache uses `global_variable_map` keyed by market scope, not by market center location.

### 3. Estate-Building Maintenance

Once per year, SOL scans every owned land location and counts estate buildings by estate type:

- Nobles
- Clergy
- Burghers
- Commoners
- Tribesmen

Each cached estate building subtracts 1 gold from the matching stratum's local income. This makes local estate construction affect the consumption capacity of the stratum that owns or uses those buildings.

### 4. Monthly Local Demand Coefficient

Every month, each country refreshes its owned land locations. SOL calculates a local final demand scale using:

```text
local liquid funds / base spending
```

Where:

- Local liquid funds come from total local stratum income after estate-building maintenance.
- National savings pressure adjusts how much income is treated as available for consumption.
- Base spending comes from the market-keyed unit spending cache multiplied by local pop counts.
- Development does not modify this calculation; both the global demand multiplier and per-good development gates are disabled.

The result is applied for one month through:

```text
sol_local_pop_demand_modifier
local_pop_demand = 1
size = final demand scale - 1
```

### 5. Living Standard UI

SOL adds UI support for inspecting the system:

- National Living Standard situation.
- Map coloring based on cached local demand coefficients.
- Location-level SOL panel and tooltip information.
- Manual cache refresh action.
- Display rows for income, savings, maintenance, base spending, liquid funds, and final coefficient.

## Economic Balance Systems

These features are retained alongside the SOL demand model.

### Age Economic Escalation

Economic pressure grows across ages. By Age 6, the active totals reach:

| Effect | Age 6 total |
|---|---:|
| Global building efficiency | -100% |
| RGO expansion cost | +100% |
| City upgrade cost | +50% |
| Town upgrade cost | +50% |
| Pop food consumption | +50% |
| Global monthly prosperity | +0.001 |

The early game begins with mild prosperity scarcity. Later ages become more prosperous but much more expensive to expand in.

### Anti-Snowball Construction

SOL slows runaway expansion by changing baseline construction incentives:

- Base RGO size is reduced to 1.
- Total-population RGO scaling is reduced.
- Low-control locations receive a construction-efficiency penalty.
- Road and railroad prices are increased:

| Action | SOL cost change |
|---|---:|
| Gravel road | x2 |
| Paved road | x2 |
| Modern road | x3 |
| Railroad | x5 |

### Tax, Difficulty, Diplomacy, And Development

- Base tax efficiency defaults to **-15%** and can be adjusted through CMF.
- AI Hard / Very Hard tax bonuses are halved.
- Player Easy / Very Easy tax bonuses are halved.
- Diplomatic spending changes with used diplomatic capacity.
- Cultural tradition can reduce stability investment cost.
- GDP-to-development gives yearly development growth scaled by local GDP.
- AI countries can receive a configurable devastation-recovery bonus to help negative-prosperity areas recover.

## War And Expansion Systems

### Harsher War Exhaustion

War exhaustion is more dangerous. It can further reduce or damage:

- Levy size.
- Control.
- Stability.
- Legitimacy.
- Defensive capability.

Occupation pressure is also stronger:

| Condition | SOL effect |
|---|---:|
| Total occupation | +1.6 monthly war exhaustion on top of vanilla |
| Capital occupied | +0.2 monthly war exhaustion on top of vanilla |

The Reduce War Exhaustion cabinet action can optionally be restricted to peacetime through CMF.

### Local War Damage

War-related local modifiers are harsher. The following conditions can more strongly affect prosperity, control, construction, migration attraction, development, raw materials, and food:

- Blockade.
- Siege.
- Occupation.
- Hostile troops.
- Looting.
- Horde raiding.
- Razing.

### Colonial Restrictions

The AI generally needs more than **500 tax base** to create colonial charters.

Exceptions:

- Historical colonizers are exempt.
- Colonial nations can colonize only in the region of their capital.
- Players are not restricted by this rule.

### Diplomatic Action Restraint

Asking another country to join a war costs more favors. This is intended to reduce call-to-arms spam.

## Food, Climate, And Price Balance

### Food And Climate

- Normal winters and raised levies create stronger local food pressure.
- Extreme Little Ice Age food and output penalties are softened to reduce pure disaster spirals.

### Price Rebalancing

Several gold transfers and action prices are rebalanced. Examples include:

- Generals require gold.
- Admirals require gold.
- Advisors and artists require gold.
- Several religious and diplomatic actions have adjusted gold scaling or caps.
- Roads and railroads are more expensive.

## CMF Settings

Community Mod Framework 2.* enables in-game control of the major SOL modules.

| Setting group | Controls |
|---|---|
| SOL pop demand | Master toggle, map coloring |
| Economic balance | Master toggle, base tax efficiency, age escalation, stability investment discount, diplomatic spending adjustment, difficulty tax nerf, GDP-to-development, AI prosperity recovery |
| War acceleration | Master toggle, higher war exhaustion, harsher war exhaustion effects, wartime Reduce War Exhaustion restriction |

When CMF variables are unavailable, many systems have default-on fallback behavior, but the Workshop package declares CMF as a dependency and it is recommended to use it.

## Compatibility

Existing saves can be loaded, but new campaigns are recommended.

Older saves may show a migration notice on first load. The economy may need time to refresh market caches and stabilize prices after loading.

Compatibility with other mods is not guaranteed, especially if they edit:

- Pop demand.
- Goods definitions.
- Local or country economic modifiers.
- War exhaustion.
- Colonial charters.
- Road or action prices.
- Living Standard / situation GUI.

I cannot currently test EU5 1.3 in long campaigns reliably because long games continue to crash on my side. If you find a specific conflict or balance issue, please report it and I will try to fix it.

## Recommended Load And Play Notes

- Use the latest Workshop version of SOL.
- Enable Community Mod Framework 2.*.
- Prefer a new campaign when testing balance.
- If loading an old save, let the game run for a while so yearly and monthly caches can refresh.
- In multiplayer, all players should use the same mod version, dependency set, and CMF settings.

## Feedback Template

When reporting problems, please include:

- Game version.
- SOL version.
- New campaign or old save.
- Country and year.
- Other enabled mods.
- Whether CMF settings were changed.
- What happened before and after the issue.
- Screenshots or logs if available.

Useful report examples:

- A good's demand is consistently too high or too low.
- A country collapses economically in a repeatable way.
- SOL map coloring or panel values look wrong.
- War exhaustion or colonial restrictions behave unexpectedly.
- A compatibility conflict can be reproduced with a small mod list.


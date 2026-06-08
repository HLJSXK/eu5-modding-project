# Standard of Living v1.1 - Feature List

## Current Status

**Version:** v1.1.0 legacy

**Scope:** full pre-1.3 SOL demand system plus the retained economy, war, expansion, food, climate, and price balance systems.

**Game target:** Europa Universalis V 1.1-era gameplay / 1.* metadata target

**Dependency:** Community Mod Framework 2.* is used for in-game configuration.

This is the older full version of Standard of Living. Unlike the later 1.3 beta build, v1.1 keeps the complete substitute-goods model, scarcity tiers, per-stratum Engel curves, and market-hub scarcity corrections.

Use this branch if you want the original full SOL economy. If you are playing a newer EU5 version, check the current Workshop page first.

## Design Goal

Vanilla pop demand is too static for the kind of economy SOL is trying to create. The v1.1 design aims to make demand react to actual economic capacity and market conditions:

- Richer strata should consume more and shift toward higher-value goods.
- Poorer strata should remain more exposed to staple food and basic goods.
- Goods should be substitutable inside meaningful consumption groups.
- Scarce goods should lose demand share, while cheap surplus goods should absorb demand.
- Markets should matter, but demand should remain tied to income rather than pure price loops.
- War, low control, food pressure, and expansion costs should all push back against runaway growth.

## Full SOL Demand System

### 1. Calibrated Baseline Demand

SOL recalibrates baseline pop demand through generated goods-demand injections.

Source flow:

```text
data/target_demand.csv
-> scripts/gen_pop_goods.py
-> src/stable/in_game/common/goods/z_SOL_pop_goods.txt
```

This baseline is not the whole system. It is the corrected foundation that the dynamic SOL model scales, redistributes, and displays.

### 2. Substitute-Goods Groups

The v1.1 branch includes 20 demand groups. Goods inside a group can substitute for one another when market prices change.

| Group | Example goods |
|---|---|
| Basic clothing | Cloth, leather |
| Crude goods | Lumber, masonry, tools, pottery |
| Staple food | Wheat, rice, millet, maize, potato, legumes |
| Condiments | Sugar, salt, olives |
| Heating fuel | Lumber, coal, beeswax |
| Household goods | Furniture, pottery, glass, paper, beeswax |
| Standard clothing | Cloth, fine cloth |
| Intoxicants | Wine, beer, liquor, tobacco |
| Luxury drinks | Tea, coffee, wine, cocoa |
| Luxury food | Wild game, victuals, fruit, fish |
| Luxury goods | Fine cloth, fur, porcelain, lacquerware, marble, glass |
| Protein food | Fish, wild game, livestock |
| Spices | Saffron, pepper, cloves, chili |
| Precious goods | Gold, silver, jewelry |
| Treasures | Amber, gems, ivory, pearls |
| Medicine | Medicaments, mercury |
| Ritual goods | Incense, mercury |
| Weapons | Weaponry, firearms |
| Mounts | Horses, elephants |
| Knowledge goods | Paper, books |

Some goods appear as secondary display members in more than one demand group. Their primary scarcity indicator group remains unique, which keeps substitution and scarcity scoring stable.

### 3. Scarcity And Surplus Tiers

Each market classifies goods by price relative to default price. The tier changes the good's demand weight inside its substitute group.

| Tier | Price condition | Demand weight |
|---|---:|---:|
| Severe shortage | Above 230% | 0.25 |
| Moderate shortage | Above 170% | 0.50 |
| Mild shortage | Above 130% | 0.75 |
| Affordable surplus | Below 85% | 1.25 |
| Cheap surplus | Below 65% | 1.50 |
| Very cheap surplus | Below 40% | 2.00 |

In plain language: pops try to avoid scarce substitutes and buy more of the cheaper alternatives.

### 4. Per-Stratum Engel Curves

The old SOL system does not treat all pops as one average consumer. Demand is calculated through stratum-specific budget shares for:

- Nobles.
- Clergy.
- Burghers.
- Commoners.
- Tribesmen.

This means price shocks have different effects depending on who is doing the consuming. Commoner demand is more sensitive to staple-food pressure, while noble demand is more exposed to luxury and prestige goods.

### 5. Era Demand Coefficient

The v1.1 demand model uses an era coefficient to compensate for early-game missing goods, limited building slots, and low substitute variety. It starts stronger in Age 1 and decays as the game progresses.

| Age | SOL era coefficient |
|---|---:|
| Age 1 | 1.5 |
| Age 2 | 1.425 |
| Age 3 | 1.35375 |
| Age 4 | 1.28606 |
| Age 5 | 1.22176 |
| Age 6 | 1.16067 |

This is one of the major differences between the full v1.1 system and the later reduced 1.3 beta model.

### 6. Market-Hub Scarcity Correction

Scarcity pressure is stored per market and per stratum on the market hub location. Each year, the mod updates variables such as:

```text
sol_market_scarcity_adj_nobles
sol_market_scarcity_adj_clergy
sol_market_scarcity_adj_burghers
sol_market_scarcity_adj_commoners
sol_market_scarcity_adj_tribesmen
```

The correction is budget-share-weighted. A shortage of goods that matter to commoners depresses commoner demand more strongly; a shortage of goods that matter to nobles depresses noble demand more strongly.

### 7. Living Standard UI

SOL adds UI support for inspecting the full system:

- National Living Standard situation.
- Living Standard map coloring.
- Country-level and stratum-level SOL values.
- Location-level SOL data.
- Substitute-goods tooltip overrides.
- Scarcity and demand indicators in goods tooltips.

## Economic Balance Systems

### Age Economic Escalation

Economic pressure grows across ages. The active effect is cumulative for the current age.

| Age | Building and RGO cost | City/town upgrade cost | Pop food consumption | Monthly prosperity |
|---|---:|---:|---:|---:|
| Age 1 | 0% | 0% | 0% | -0.0015 |
| Age 2 | +20% | +10% | +10% | -0.001 |
| Age 3 | +40% | +20% | +20% | -0.0005 |
| Age 4 | +60% | +30% | +30% | 0 |
| Age 5 | +80% | +40% | +40% | +0.0005 |
| Age 6 | +100% | +50% | +50% | +0.001 |

The early game has tighter prosperity. Later ages become more prosperous but much more expensive to expand in.

### Anti-Snowball Construction

SOL slows runaway expansion by changing baseline construction incentives:

- Base RGO size is reduced to 1.
- Total-population RGO scaling is reduced.
- Low-control locations receive an extra construction-cost penalty.
- Road and railroad prices are increased:

| Action | Vanilla cost | SOL v1.1 cost | Change |
|---|---:|---:|---:|
| Gravel road | 10 | 20 | 2x |
| Paved road | 25 | 50 | 2x |
| Modern road | 50 | 150 | 3x |
| Railroad | 100 | 500 | 5x |

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
| Total occupation | +1.6 monthly war exhaustion on top of vanilla, for a net 2.0 per month |
| Capital occupied | +0.2 monthly war exhaustion on top of vanilla, for a net 0.3 per month |

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

- Mild winters have stronger food pressure than vanilla.
- Normal winters have much stronger food pressure than vanilla.
- Raised levies reduce local raw-material output and local food.
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

Older saves may need time to refresh market caches, yearly SOL variables, and monthly demand values after loading.

Compatibility with other mods is not guaranteed, especially if they edit:

- Pop demand.
- Goods definitions.
- Goods prices.
- Local or country economic modifiers.
- War exhaustion.
- Colonial charters.
- Road or action prices.
- Living Standard / situation GUI.

The full v1.1 demand model is heavier than the later reduced 1.3 beta model because it includes substitute goods, scarcity tiers, per-stratum Engel curves, and market-hub scarcity correction.

## Recommended Load And Play Notes

- Use the v1.1 Workshop item when playing the old branch.
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
- Pops are not shifting away from scarce goods as expected.
- A country collapses economically in a repeatable way.
- SOL map coloring or panel values look wrong.
- War exhaustion or colonial restrictions behave unexpectedly.
- A compatibility conflict can be reproduced with a small mod list.

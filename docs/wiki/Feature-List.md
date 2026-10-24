# Standard of Living - Feature List

## Current Status

**Game target:** Europa Universalis V 1.4.*
**Dependency:** Community Mod Framework 2.* (in-game settings)
**Recommended:** start a new campaign after updating.

Standard of Living (SOL) is an economy and balance overhaul. It replaces vanilla's fixed pop demand with demand that follows what each estate can actually afford. It adds goods substitution and a living-standard score that includes things money cannot buy, and ships an anti-snowballing and harsher-war balance layer.

Release targets:

| Target | What it is |
|---|---|
| Standard of Living | The full mod: demand system, substitution, living standard, UI and the balance layer. |
| SOL Standalone | Only the demand, substitution, living-standard and UI systems, without the balance layer and without CMF. Do not enable it together with the full mod. |
| SOL-PP / SOL-M&T / SOL-JTG | Compatibility submods for Prosper or Perish, MEIOU and Taxes, and Just Goods. Load them below both main mods. |

### A short history

SOL 1.1 (EU5 1.1) had substitute groups and per-estate Engel curves. An engine change in EU5 1.2 broke the interface that design relied on, so later versions shipped only income-based demand. The current version restores goods substitution on a new country-level design. Engel curves, cultural/religious preferences and market-hub scarcity corrections stay retired.

## Design Goal

Vanilla pop demand is fixed and low. Estates cannot spend their income, so they hoard enormous savings, while the market only works because the state builds end-consumer buildings and buys goods itself. SOL aims for:

- Pops that spend what they actually earn, so money flows back into the market.
- Demand that reacts to prices, with substitution inside a category of goods.
- A living standard that reflects more than money: health, clean water, pollution and culture.
- A balance layer that keeps a richer economy from snowballing too early.

## 1. Income-Based Demand (Purchasing Power)

### Calibrated baseline basket

SOL recalibrates the baseline pop demand for 56 goods. The baskets are based on 1340 country medians: nobles ×1, clergy ×2, commoners (laborers, peasants and soldiers) ×4, and burghers about ×0.66 of the earlier calibration. Each quantity is rounded to one or two significant digits.

- The engine-wide development demand multiplier is set to zero, and every vanilla per-good development threshold is negated. Development no longer scales or gates demand.
- Pops pay the nominal price of the goods they buy; vanilla's purchase-side surcharge is removed so income accounting matches spending.

### Market base spending

Once a year, SOL scans every market and caches what one unit of each pop type's basket costs there, using `quantity × min(market price, default price)`. Cheap goods lower base spending; expensive goods never push it above the default price.

### Liquid funds

For each estate in each location, SOL computes the money it can actually spend:

- Its share of the location's income.
- Minus estate-building maintenance: each building of an estate costs that estate 1 gold of local income, counted yearly.
- Adjusted by national savings pressure: savings above the estate's target raise spending, and savings below it lower spending (capped at +50%).

### Purchasing power and the demand coefficient

```text
purchasing power = liquid funds / base spending
```

Purchasing power is the only input to demand. Zero funds means −100%; three times the baseline means +200%. Every month, a one-month `local_pop_demand` modifier is applied to each owned land location.

A country-level solver then adjusts the per-location coefficients so that each estate's national total matches its national purchasing power, while preserving local differences. It tries an exact solve first and falls back to a strict "never worse than raw" approximation. Countries with fewer than five locations skip the solver.

### Calculation frequency

Players are recalculated monthly. By default, AI countries are recalculated once a year on their own anniversary, which greatly reduces late-game cost. New countries, newly acquired locations, game start/load and settings changes are handled immediately. You can switch AI back to monthly in the CMF Performance tab.

## 2. Goods Substitution

### Substitute groups

56 goods belong to 20 groups. Some goods belong to more than one group (67 memberships in total).

| Tier | Group | Goods |
|---|---|---|
| Required | Staple | wheat, rice, millet, maize, potato, legumes |
| Required | Protein | fish, wild game, livestock |
| Required | Clothing | cloth, leather |
| Required | Heating | lumber, coal, beeswax |
| Required | Crude goods | lumber, masonry, tools, pottery |
| Daily | Seasoning | sugar, salt, olives |
| Daily | Household | furniture, pottery, glass, paper, beeswax |
| Daily | Fine cloth | cloth, fine cloth |
| Daily | Drink | wine, beer, liquor, tobacco |
| Daily | Medicine | medicaments, mercury |
| Daily | Ritual | incense, mercury |
| Daily | Knowledge | paper, books |
| Luxury | Delicacy | fish, wild game, fruit |
| Luxury | Fine drink | tea, coffee, wine, cocoa |
| Luxury | Luxury | fine cloth, fur, porcelain, lacquerware, marble, glass |
| Luxury | Spice | saffron, pepper, cloves, chili |
| Luxury | Precious | gold, silver, jewelry |
| Luxury | Treasure | amber, gems, ivory, pearls |
| Luxury | Weapons | weaponry, firearms |
| Luxury | Mounts | horses, camels, elephants |

### Whole-group consumption

Each pop type subscribes to whole groups. An estate either needs a whole category or none of it; it never needs only part of a group.

| Group | Nobles | Clergy | Burghers | Laborers | Peasants | Soldiers |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Staple, Protein, Crude goods, Heating, Household, Seasoning, Drink, Medicine, Delicacy | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Clothing, Weapons | ✓ | | | ✓ | ✓ | ✓ |
| Fine cloth, Luxury, Spice, Knowledge | ✓ | ✓ | ✓ | | | |
| Fine drink | ✓ | ✓ | ✓ | | | ✓ |
| Precious, Treasure | ✓ | | ✓ | | | |
| Ritual | | ✓ | | | | |
| Mounts | ✓ | | | | | |

Tribesmen have no baseline basket.

### Price preferences

Each good gets a preference weight from its market price relative to its base price:

| Price / base price | Weight |
|---|---:|
| below 0.40 | ×2 |
| 0.40 – 0.65 | ×1.5 |
| 0.65 – 0.85 | ×1.25 |
| 0.85 – 1.30 | ×1 |
| 1.30 – 1.70 | ×0.75 |
| 1.70 – 2.30 | ×0.5 |
| above 2.30 | ×0.25 |

Inside each subscribed group, demand moves from expensive members toward cheap ones. Goods without supply drop out of the group, and the rest share its demand. Results from overlapping groups are combined.

### How it applies

Substitution is calculated per country, after aggregating the country's population by market and pop type, on the same schedule as the demand system. The result is applied as **"Goods substitution (good)"** country modifiers and also feeds the purchasing-power calculation, so base spending reflects what people actually buy. Demand modifiers from other sources are respected and multiplied, not overwritten.

The feature has its own CMF switch (on by default). Turning it off restores a neutral basket.

## 3. Living Standard

### Living standard vs purchasing power

- **Purchasing power** answers "how much of the basic basket can people afford?" It is the only input to demand.
- **Living standard (SOL)** answers "how well do people live?" It is an amount, not a percentage:

```text
SOL = flat bonuses + (1 + summed percentage bonuses) × annual liquid funds per 1,000 people
```

Percentages add together and multiply only the money part. Each estate's SOL is floored at zero, and country SOL is population-weighted. Living-standard bonuses never create spendable money and never change demand.

### Living-standard sources

SOL adds two location modifier types: **Local Living Standard** (flat) and **Local Living Standard Modifier** (percentage). The first batch is applied to 17 buildings and scales with building level like any native building modifier:

| Building | Effect |
|---|---|
| Hospital | +0.05 |
| Lazaretto, Pest House | +0.03 |
| Aqueduct System | +0.02 |
| Darüşşifa | +0.08 |
| Charité, Magistrato alla Sanità | +0.06 |
| Tanning Workshop / Tanning Manufactory / Tannery Mill | −0.01 / −0.02 / −0.03 |
| Putrefaction Works / Putrefaction Mill | −0.02 / −0.03 |
| Iron Mill, Steel Mill | −0.02 |
| Theater | +2% |
| Opera House | +3% |
| Library | +1% |

The rule of thumb: survival-level things (health, water, pollution) are flat values that matter most to the poor; quality-of-life things (culture) are percentages that matter most to the rich. More sources (war, disease, institutions) are planned.

### Effects of living standard

| Effect | Rule |
|---|---|
| Migration attraction | +0.02 per point of local SOL, up to +0.5 (reached at SOL 25) |
| Population growth | −0.1 percentage points when local SOL is below 0.1; +0.1 percentage points when it is above 10 |
| Tier | Low / Medium / High against the population-weighted world average (below 75% / above 133%) |
| World ranking | Countries and each estate are ranked by living standard every 1 January. Single-location countries are not ranked. |

## 4. Interface

### Four-section SOL bar

A row under the country buttons on the left panel:

1. **Living standard**: country SOL, tier medallion and year-on-year change. The tooltip lists the nation and each estate with population, SOL and change.
2. **Purchasing power**: national purchasing power. The tooltip shows a bar per estate from −100% to +200%.
3. **Goods substitution**: the tooltip shows every substitute group as a card, with supplied members and a seven-level substitution indicator under each good.
4. **World ranking**: rank and percentile. The tooltip shows neighbors in the ranking and each estate's world rank, percentile and the world's best.

Hover a section to preview its map mode; left-click to open it. The bar works with Glorp UI.

### Map modes

| Map mode | Colors |
|---|---|
| SOL Living Standard | Local living standard: red at 0, yellow at the world average, green at 3× the world average |
| SOL Purchasing Power | Local raw purchasing power, −100% to +200% |
| SOL Goods Substitution | Country colors; hover a country to see its substitution overview |
| SOL Rankings | Overall rank, greener is better; unranked countries are striped |

### Goods tooltips and the location window

- Goods tooltips list the good's substitute groups with every member, plus the seven price tiers. Market goods tooltips also show the current price ratio and highlight the current tier.
- The SOL button in the location window shows each estate's purchasing power and the goods consumed there. It is hidden on unowned locations.

## 5. Economic Balance

Based on Anti Snowballing by Ethereal. All parts can be configured through CMF.

### Age economic escalation

| Effect | Age 6 total |
|---|---:|
| Global building efficiency | −100% |
| RGO expansion cost | +100% |
| City upgrade cost | +50% |
| Town upgrade cost | +50% |
| Pop food consumption | +50% |
| Global monthly prosperity | +0.001 |

### Anti-snowball construction

- Base RGO size is reduced to 1, and total-population RGO scaling is reduced.
- Low-control locations get a construction-efficiency penalty.
- Road prices: gravel ×2, paved ×2, modern ×3, railroad ×5.

### Taxes, diplomacy and development

- Base tax efficiency defaults to **−15%** (adjustable in CMF).
- AI Hard/Very Hard and Player Easy/Very Easy tax bonuses are halved.
- Diplomatic spending scales with used diplomatic capacity.
- Cultural tradition can reduce stability investment cost.
- GDP-to-development: locations gain yearly development scaled by local GDP.
- Optional AI devastation recovery helps AI regions with negative prosperity recover.

## 6. War and Expansion

- War exhaustion further reduces levy size, control, stability, legitimacy and defensive capability.
- Total occupation adds +1.6 monthly war exhaustion and capital occupation +0.2, on top of vanilla.
- The Reduce War Exhaustion cabinet action can be restricted to peacetime.
- Blockades, sieges, occupation, hostile troops, looting, horde raiding and razing hit prosperity, control, construction, migration attraction, development, raw materials and food harder.
- AI generally needs more than 500 tax base to create colonial charters; historical colonizers are exempt, colonial nations colonize only in their capital region, and players are not restricted.
- Asking another country to join a war costs more favors.

## 7. Food, Climate and Prices

- Normal winters and raised levies create stronger local food pressure.
- Extreme Little Ice Age food and output penalties are softened to avoid pure disaster spirals.
- Generals, admirals, advisors and artists cost gold; several religious and diplomatic actions and gold transfers are rebalanced.

## 8. CMF Settings

| Tab | Settings |
|---|---|
| Features | SOL pop demand master switch, map coloring, goods substitution; economic balance master switch, base tax efficiency, age escalation, stability discount, diplomatic cost adjustment, difficulty tax nerf, GDP-to-development, AI prosperity recovery; war acceleration master switch, higher war exhaustion, more severe war exhaustion, wartime restriction on reducing war exhaustion |
| Performance | Reduce AI calculation frequency (yearly AI, default on); player/AI exact and approximation solves for the country-level solver (all default on) |

## 9. Compatibility

- A new campaign is recommended. Older saves load, but caches need time to rebuild and prices need time to settle.
- Prosper or Perish, MEIOU and Taxes and Just Goods each need their SOL compatibility submod, loaded below both main mods. Only one compatibility submod can be active at a time.
- Other mods that change pop demand or goods conflict with SOL's calibration unless a submod exists. Compatibility requests are welcome.
- SOL ships a unified location window based on Glorp UI with the SOL button inserted. Glorp UI and Construction Manager are not required; Construction Manager adds its controls when enabled. Other full location-window overrides conflict.
- Modders can make their own buildings affect living standard with `local_sol_living_standard` and `local_sol_living_standard_modifier`, in a submod that depends on SOL.

## Acknowledgements

SOL builds on two discontinued mods:

- [SoL Based Pop Demands](https://steamcommunity.com/sharedfiles/filedetails/?id=3618308174) by 1onepower
- [Anti Snowballing](https://steamcommunity.com/sharedfiles/filedetails/?id=3644897537) by Ethereal

## Feedback

Please report in the [Discord](https://discord.gg/Yy87G2hBHz), the QQ group (1070041687) or the Workshop comments, and include:

- Game version and SOL version.
- New campaign or old save.
- Country and year.
- Other enabled mods and changed CMF settings.
- Screenshots or `error.log` if available.

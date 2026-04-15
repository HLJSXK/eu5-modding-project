
[h2][b]Balance of Power[/b][/h2]

[quote]
[code]

Balance of Power is a gameplay rebalance mod designed to improve realism, pacing, and strategic depth.

The mod reduces the rate of cultural and religious change, slows urban growth, and makes control and stability more meaningful factors in governing your realm. Rural regions are now more resistant to rapid transformation, reflecting historical population patterns and the difficulty of enforcing central authority in sparsely populated areas.

War also carries heavier consequences. High war exhaustion weakens state legitimacy and stability, harsh winters reduce food output, and occupied or starving provinces suffer additional penalties to defense and prosperity. At the same time, provincial capitals receive modest defensive bonuses, making them more resilient during invasions.

Control has also been rebalanced. Extremely low control is less crippling to basic economic and military contributions, but it now slows the settlement of tribal populations and generates minor separatist pressure.

Overall, the goal of the mod is to create a world where growth is slower, governance is more challenging, and maintaining the balance of power requires careful strategy.
[/code]
[/quote]




- Adjusted the number of pops required to form towns and cities so there should be fewer of them in your game.

- Rural areas now experience 33% slower assimilation, conversion, and tribal promotion, reflecting their lower population density and historical resistance to rapid change.


- Added stability and legitimacy penalties at high war exhaustion

- Decreased food production in locations affected by sevre winter
- Added a food capacity penalty and increased the prosperity penalty in occupied provinces
- Added defensive and garrison size penalties to starving provinces

- Added a small garrison increase and a minor max control boost to province capitals
- Reduced country base assimilation and conversion by half.
- Reduced Cabinet assimilation actions by half.
- Adjusted very low control to be less punishing overall, allowing some levies, manpower, sailors, and pop promotion.
- At the same time, a tribal promotion malus has been added so regions without meaningful control will settle their tribal pops slower.
- Added a small amount of sepratism to very low control



# Balance changes

## Inverse Control

- local_tribal_promotion = -1.0 #br added
- local_levy_size_modifier = 0.50 #BR edit was -1
- local_manpower_modifier = 0.25 #BR edit was -1
- local_sailors_modifier = 0.25 #BR edit was -1

####
## Location ranks
### City
- population >= 45 # was 30
- local_max_control = 0.15 #br increased from 0.1

### Town
- local_max_control = 0.1 #br Increased from 0.05
- population >= 15 #was 5

### Rural
- local_pop_assimilation_speed_modifier = -0.25 #br added
- local_pop_conversion_speed_modifier = -0.25 #br added
- local_tribal_promotion = -0.25 #br added

####
## Cabinet 
### Promote Culture
- local_pop_assimilation_speed = 0.02 #br edited from 0.04

### Assimilate Area 
- local_pop_assimilation_speed = 0.01 #br edited from 0.02

####
## Country Base Values
- global_pop_assimilation_speed = 0.0005 #br edit from 0.001
- global_pop_conversion_speed = 0.001 #br edit from 0.002
- global_laborers_migration_allowed = yes #br enabled




[h2][b]BR: Balance Mod[/b][/h2]
A focused balance mod aimed at delivering a slower, more grounded, and simulation-driven gameplay experience.

[quote]
Adjusted control to be less punishing overall, allowing some levies, manpower, sailors, and pop promotion.
At the same time, a tribal promotion malus has been added so regions without meaningful control will settle their tribal pops slower.
[code]
Inverse Control (These are the values at 0% control)
- local_pop_promotion_speed_modifier = -0.75 #BR edit was -1 (75% less. base value is -100% less)
- local_tribal_promotion = -1.0 #br added 
- local_levy_size_modifier = -0.75 #BR edit was -1 (75% less base value is -100% less)
- local_manpower_modifier = -0.75 #BR edit was -1 (75% less base value is -100% less)
- local_sailors_modifier = -0.75 #BR edit was -1 (75% less base value is -100% less)
[/code]
[/quote]

[quote]
Adjusted the number of pops required to form towns and cities so there should be fewer of them in your game. Also increased the amount of control gained from towns and cities so they act as true administrative and economic hubs.

In addition, rural areas now experience 25% slower assimilation, conversion, and tribal promotion, reflecting their lower population density and historical resistance to rapid change.

1.1 Added a small proximity source and a minor max control boost to towns and cities.
[code]
Location ranks
City
- population >= 45 # was 30
- local_max_control = 0.15 #br increased from 0.1 (15% base control up from base of 10%)
- local_proximity_source = 5 #br added

Town
- local_max_control = 0.1 #br Increased from 0.05 (10% base control up from base of 5%)
- population >= 15 #was 5
- local_proximity_source = 2 #br added

Rural
- local_pop_assimilation_speed_modifier = -0.25 #br added (25% slower in rural locations)
- local_pop_conversion_speed_modifier = -0.25 #br added (25% slower in rural locations)
- local_tribal_promotion = -0.25 #br added (25% slower in rural locations)
[/code]
[/quote]

[quote]
Reduced Cabinet assimilation actions by 50%
Cabinet actions remain powerful tools, but now require sustained investment rather than acting as instant solutions.
[code]
Cabinet
Promote Culture
- local_pop_assimilation_speed = 0.02 #br edited from 0.04

Assimilate Area
- local_pop_assimilation_speed = 0.01 #br edited from 0.02
[/code]
[/quote]

[quote]
Reduced country base assimilation and conversion by 50%
Population change is now a long-term process, while laborer pops are allowed to migrate by default to improve internal demographic flow.
[code]
Country Base Values
- global_pop_assimilation_speed = 0.0005 #br edit from 0.001
- global_pop_conversion_speed = 0.001 #br edit from 0.002
- global_laborers_migration_allowed = yes #br enabled
[/code]
[/quote]

[h3]1.1 Additions[/h3]
[quote]
Added a small proximity source and a minor max control boost to province capitals
[code]
## Province Capital 
- local_proximity_source = 2 #BR added
- local_max_control = 0.05 #BR added
[/code]
Added defensive and garrison size penalties to starving provinces
[code]
## province_starving
- local_defensive = -0.25
- local_garrison_size_modifier = -0.25
[/code]
Added a food capacity penalty and increased the prosperity penalty in occupied provinces
[code]
## is_occupied
- local_food_capacity_modifier = -0.5
- local_monthly_prosperity = -0.04 # was: -0.025
[/code]

[code]
## Food
- Increased the demand for Fish to make it a more valuable food source
[/code]
Added stability and legitimacy penalties at high war exhaustion
[code]
## war_exhaustion_impact
- stability_decay = 0.0001 #br addition
- monthly_legitimacy = -0.01 #br addition
[/code]
Decreased food production in locations affected by winter
[code]
## Winter
### winter_mild
- local_monthly_food_modifier = -0.4 # was: -0.25

### winter_normal
- local_monthly_food_modifier = -0.85 # was: -0.5
[/code]
[/quote]


[b]Compatibility[/b]
[list]
[*]Primarily uses INJECT to only edit the listed variables and does not overwrite base-game files. Should be compatible with basically everything
[/list]

[code]
Intended addition to [url=https://steamcommunity.com/sharedfiles/filedetails/?id=3618199037]Basileía
 Romaíon 1337[/url].
[/code]


Join our [url=https://discord.gg/D4hpCn7DgP]Discord[/url] to follow the development of BR-1337 and discuss all things PDX and History. [url=https://discord.gg/D4hpCn7DgP][img]https://i.imgur.com/n5g35mo.png[/img][/url]


[url=https://www.buymeacoffee.com/Romaioi][img]https://i.imgur.com/uvoJixi.jpg[/img][/url]
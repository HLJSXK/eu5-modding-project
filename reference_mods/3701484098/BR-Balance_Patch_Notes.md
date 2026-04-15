
# Ver: 1.1


## Location ranks: 
Added a small proximity source to towns and cities
### City
- local_proximity_source = 5 #br added

### Town
- local_proximity_source = 2 #br added

Added a small proximity source and a minor max control boost to province capitals
## Province Capital 
- local_proximity_source = 2 #BR added
- local_max_control = 0.05 #BR added

Added defensive and garrison size penalties to starving provinces
## province_starving
- local_defensive = -0.25
- local_garrison_size_modifier = -0.25

Added a food capacity penalty and increased the prosperity penalty in occupied provinces
## is_occupied
- local_food_capacity_modifier = -0.5
- local_monthly_prosperity = -0.04 # was: -0.025

## Food
- Increased the demand for Fish to make it a more valuable food source

Added stability and legitimacy penalties at high war exhaustion
## war_exhaustion_impact
- stability_decay = 0.0001 #br addition
- monthly_legitimacy = -0.01 #br addition

Decreased food production in locations affected by winter
## Winter
### winter_mild
- local_monthly_food_modifier = -0.15 #br total value will be 0.4 was: -0.25

### winter_normal
- local_monthly_food_modifier = -0.35 #br total value will be -0.85 was: -0.5


# Ver 1.0

# Balance changes

## Inverse Control
- local_pop_promotion_speed_modifier = 0.25 #BR edit was -1
- local_tribal_promotion = -1.0 #br added
- local_levy_size_modifier = 0.25 #BR edit total is -0.75 was -1
- local_manpower_modifier = 0.25 #BR edit total is -0.75 was -1
- local_sailors_modifier = 0.25 #BR edit total is -0.75 was -1
- monthly_rebel_growth = 0.002 #BR added

####
## Location ranks
### City
- population >= 45 # was 30
- local_max_control = 0.15 #br increased from 0.1
- local_proximity_source = 5 #br added

### Town
- local_max_control = 0.1 #br Increased from 0.05
- population >= 15 #was 5
- local_proximity_source = 2 #br added

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


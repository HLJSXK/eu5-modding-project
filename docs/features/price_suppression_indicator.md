# Price Suppression Indicator Feature

## Overview

Added visual indication in the location GUI to show which goods have suppressed demand due to expensive market prices.

## Visual Indicators

When viewing the goods consumption section of a location's SOL tooltip, each good can display:

1. **Good icon** (always visible)
2. **Red down arrow (`@arrow_down!`)** - Displayed when:
   - The good is consumed in this location's market (`sol_market_consumes_X > 0`)
   - The market price exceeds the default price (`market_price > default_price`)
   - This indicates demand suppression: the SOL system uses `min(market_price, default_price)` for base spending calculations, so expensive goods do not inflate expenditure
3. **Gray X (`@trigger_no!`)** - Displayed when the good is not consumed in this market

## Implementation

### Data Collection (Annual, January refresh)

File: `scripts/gen_market_unit_consumption.py` → `sol_refresh_market_pop_demand_maps`

For each good with population demand:

```javascript
set_local_variable = { name = sol_market_actual_price_X value = "market_price(goods:X)" }
set_local_variable = {
    name = sol_market_effective_price_X
    value = {
        value = local_var:sol_market_actual_price_X
        max = "default_price(goods:X)"  // Caps at base price
    }
}
set_local_variable = { name = sol_market_price_suppressed_X value = 0 }
if = {
    limit = { local_var:sol_market_actual_price_X > "default_price(goods:X)" }
    set_local_variable = { name = sol_market_price_suppressed_X value = 1 }
}
// Store in global_variable_map keyed by market scope
add_to_global_variable_map = { 
    name = sol_market_price_suppressed_X 
    key = scope:sol_market_cache 
    value = local_var:sol_market_price_suppressed_X 
}
```

### GUI Display

Files:
- `src/stable/in_game/gui/SOL_economy_local.gui`
- `src/sol_standalone/in_game/gui/SOL_economy_local.gui`
- `src/sol_pp_compatibility_submod/in_game/gui/zz_SOL_economy_local.gui` (auto-generated)
- `src/sol_jtg_compatibility_submod/in_game/gui/zz_SOL_economy_local.gui` (auto-generated)

For each good widget:

```gui
widget = { 
    size = { 34 30 } 
    tooltip = "good_name"
    
    // Good icon (always visible)
    text_single = { 
        size = { 100% 100% } 
        align = center 
        raw_text = "@good_name!" 
    }
    
    // Red down arrow (suppressed demand indicator)
    text_single = { 
        size = { 100% 100% } 
        align = center 
        raw_text = "#R @arrow_down!#!" 
        visible = "[And(
            GreaterThan_CFixedPoint(GetVariableFromGlobalVariableMap('sol_market_consumes_good_name', Location.GetMarket.MakeScope).GetValue,'(CFixedPoint)0'), 
            GreaterThan_CFixedPoint(GetVariableFromGlobalVariableMap('sol_market_price_suppressed_good_name', Location.GetMarket.MakeScope).GetValue,'(CFixedPoint)0')
        )]" 
    }
    
    // Gray X (no consumption indicator)
    text_single = { 
        size = { 100% 100% } 
        align = center 
        raw_text = "@trigger_no!" 
        fontsize = 23 
        visible = "[Not(GreaterThan_CFixedPoint(GetVariableFromGlobalVariableMap('sol_market_consumes_good_name', Location.GetMarket.MakeScope).GetValue,'(CFixedPoint)0'))]" 
    }
}
```

## Engine Price Behavior

The SOL system captures EU5's asymmetric price response:

- **Expensive goods** (`market_price > default_price`):
  - Base spending uses `default_price` (capped)
  - Demand is **suppressed** (red arrow visible)
  - Prevents demand inflation from price spikes
  
- **Cheap goods** (`market_price < default_price`):
  - Base spending uses actual `market_price`
  - Demand scales with the lower price
  - No indicator shown (normal consumption)
  
- **No consumption** (`sol_market_consumes_X = 0`):
  - Gray X shown
  - Good not available or no population demand

## Refresh Frequency

Price suppression status is determined **once per year in January** during the global market refresh. The indicator reflects the price snapshot from that refresh, not real-time prices.

This matches the SOL system's annual cache of unit spending values, balancing accuracy with performance.

## User Interpretation

When a player sees a red down arrow on a good:

1. The market price for that good was above its base price as of the last January refresh
2. Population demand for that good is being calculated using the base price, not the inflated market price
3. If market conditions improve (price falls below base), the indicator will update next January
4. The suppression prevents the solver from overestimating how much pops "should" be spending on expensive luxuries

## Files Modified

### Generator Scripts
- `scripts/gen_market_unit_consumption.py` - Added price suppression flag logic
- `scripts/gen_sol_jtg_compat.py` - Modified `_goods_widget()` to include suppression overlay
- `scripts/add_all_price_suppression.py` - Utility to batch-apply GUI changes (one-time use)

### Generated Files (via gen_sol_chain.py)
- All `A_SOL_economy_effects.txt` files (stable, standalone, PP, JTG)
- All `SOL_market_unit_consumption_values.txt` files
- All `SOL_economy_local.gui` files

## Testing

To verify the feature works:

1. Find a market with a good where `market_price > default_price`
2. Open the location tooltip for a location in that market
3. Scroll to the goods consumption section
4. The expensive good should show a red down arrow if it's being consumed
5. Goods with `market_price <= default_price` show only their icon (no arrow)
6. Goods not consumed in the market show a gray X

## Performance Impact

- **January tick**: Adds one price comparison and one global_variable_map write per consumed good per market
  - ~55 goods × ~20-50 markets = ~1000-2500 extra operations once per year
  - Negligible impact
  
- **GUI rendering**: Adds one conditional overlay widget per good (55-77 depending on target)
  - Evaluated client-side only when tooltip is open
  - Negligible impact

## Future Considerations

- If real-time price response is desired, the suppression flag could be updated monthly rather than annually
- The threshold could be made configurable (e.g., only suppress when price is >120% of base)
- A similar indicator could be added for extremely cheap goods to show demand boost

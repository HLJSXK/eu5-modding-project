import colorsys
import re

from data import Unknown

from scenarios import COMMON


def _hsv360(h, s, v):
    return colorsys.hsv_to_rgb(h / 360, s / 100, v / 100)


# main_menu/common/named_colors/02_map.txt:4245-4252 (pop_nobles ... pop_tribes)
POP_COLORS = {
    "nobles": _hsv360(224, 59, 80), "clergy": _hsv360(217, 13, 90), "burghers": _hsv360(40, 87, 79),
    "laborers": colorsys.hsv_to_rgb(0.6, 0.3, 0.2), "peasants": _hsv360(78, 44, 47),
    "soldiers": _hsv360(0, 74, 88), "tribesmen": _hsv360(20, 44, 47),
}

POPS = [  # type, name, color, power, literacy, size, total, growth  (format copied from the 1080p screenshot)
    ("nobles", "贵族", (0.62, 0.45, 0.80), 48, 0.35, 0.013, "476", "#G +3#!"),
    ("clergy", "教士", (0.93, 0.89, 0.74), 17, 0.55, 0.033, "1,134", "#G +3#!"),
    ("burghers", "市民", (0.86, 0.60, 0.25), 14, 0.10, 0.046, "1,600", ""),
    ("laborers", "劳工", (0.55, 0.65, 0.75), 1, 0.10, 0.103, "3,550", "#G +1#!"),
    ("soldiers", "士兵", (0.75, 0.38, 0.38), 1, 0.10, 0.036, "1,250", ""),
    ("peasants", "农民", (0.50, 0.75, 0.40), 1, 0.09, 0.766, "26,264", ""),
    ("tribesmen", "部落民", (0.70, 0.50, 0.35), 0, 0.0, 0.0, "0", ""),  # game lists zero-size pop types too
]
CULTURES = [("奥地利人", 0.81, "25.60K"), ("波希米亚人", 0.12, "3.79K"), ("匈牙利人", 0.07, "2.21K")]
RELIGIONS = [("天主教", 0.96, "30.34K"), ("东正教", 0.04, "1.26K")]


def location(tab="demography"):
    pops = [{"__type__": "LocationPopItem", "GetType.GetNameWithNoTooltip": n, "GetColor": POP_COLORS[t], "GetPoliticalPower": pw,
             "GetLiteracy": lit * 100, "GetSize": sz, "GetTotalSize": tot, "GetGrowthForUI": g, "GetType": t,
             "PopType.Self": t, "PopType.GetNameWithNoTooltip": n}
            for (t, n, c, pw, lit, sz, tot, g) in POPS]
    poptypes = [{"__type__": "PopTypeItem", "GetPercentage": p["GetSize"], "GetColor": POP_COLORS[p["GetType"]]} for p in pops]
    politics = [{"__type__": "PopPoliticsItem", "GetPercentage": v, "GetColor": c} for v, c in
                ((0.38, (0.62, 0.45, 0.80)), (0.12, (0.93, 0.89, 0.74)), (0.21, (0.86, 0.60, 0.25)), (0.29, (0.50, 0.75, 0.40)))]
    cultures = [{"__type__": "PopCultureItem", "GetNameWithNoTooltip": n, "GetPercentage": p, "GetAbsoluteSize": a,
                 "GetCulture": n, "GetColor": c} for (n, p, a), c in zip(CULTURES, [(0.8, 0.1, 0.1), (0.3, 0.5, 0.8), (0.85, 0.72, 0.3)])]
    religions = [{"__type__": "PopReligionItem", "GetNameWithNoTooltip": n, "GetPercentage": p, "GetAbsoluteSize": a,
                  "GetReligion": n, "GetColor": c, "GetReligion.GetIcon": ""}
                 for i, ((n, p, a), c) in enumerate(zip(RELIGIONS, [(0.9, 0.82, 0.48), (0.48, 0.55, 0.84)]))]
    true_ = (r"Location\.(GetOwner\.IsPlayer|HasOwner|IsProvinceCapital|GetProvince\.GetCapital\.IsCapital|HasFort|"
             r"GetController\.IsPlayer|IsIntegrated|IsColonized|HasRiver|HasWinter|GetProvince\.GetCountry\.IsValid|"
             r"HasRawMaterial|IsCapital|CanUpgradeRank)")
    false_ = (r"Location\.(IsOccupied|HasSiege|IsCurrentlyBeingIntegrated|IsCoastal|IsCanalOpen|HasCombat|HasImports|"
              r"HasExports|IsBlockadedByEnemies|IsBlockadedByIce|IsSoundTollLand|HasVolcano|HasEarthquakes|HasRaisedLevies|"
              r"HasSpecificBaseModifier|GetSiege\.GetBesieger\.IsValid|GetOwner\.IsAllied|"
              r"GetOwner\.GetDiplomacy\.IsSubjectOf\(GetPlayer\)|GetController\.GetDiplomacy\.IsSubjectOf\(GetPlayer\)|"
              r"GetRank\.IsDefault|CanDowngradeRank)")
    mocks = COMMON + [
        (r"LocationView\.Vars\.HasValue\('tab','(\w+)'\)", lambda m: m.group(1) == tab),
        (r"LocationView\.Vars\.NotExistOrHasValue\('tab','(\w+)'\)", lambda m: m.group(1) == tab),
        (r"LocationView\.Vars\..*", False),
        (true_, True), (false_, False),
        (r"Location\.Self|Location", "LOC_VIENNA"),
        (r"Location\.GetAverageSatisfaction", 0.64),
        (r"Location\.GetRank\.GetFrameTier", 3.0),
        (r"Location\.GetFortLevel", 2.0),
        (r"Location\.GetNameWithNoTooltip", "维也纳"),
        (r"Location\.GetRankAndName", "维也纳城市"),
        (r"Location\.GetRankIcon", "gfx/interface/icons/location_icons/city.dds"),
        (r"Location\.GetControl", 0.85),
        (r"Location\.GetTotalPopulation", "31.6K"),
        (r"Location\.GetTotalPossibleTaxBase", 28.4),
        (r"Location\.GetMarketAccess", 0.92),
        (r"Location\.GetPopGrowth", 0.0035),
        (r"Location\.GetPopulationChangeLabel", "+110"),
        (r"Location\.GetLocalMigrationAttraction", 1.25),
        (r"Location\.GetMigrationChange", "+40"),
        (r"Location\.GetMigrationInformation", "x"),
        (r"Location\.GetPromote", 28.0), (r"Location\.GetDemote", 9.0),
        (r"Location\.GetAssimilate", 14.0), (r"Location\.GetConvert", 3.0),
        (r"Location\.GetMaxRGOWorkers", 3.0), (r"Location\.GetMaximumMaxRGOWorkersValueForUI", 5.0),
        (r"Location\.GetMaxRGOWorkersUnderConstruction", 0.0),
        (r"Location\.GetTownRights", []),
        (r"Location\.(GetHolySites|GetReligiousOrders|GetTimedModifiers|GetProvince\.GetTimedModifiers|"
         r"GetInternationalOrganizations|GetCivilConstructions)", []),
        (r"Location\.GetAppliedAttritionPercentage", 0.0),
        (r"Location\.GetModifierValueFixed\('harbor_suitability'\)", 0.0),
        (r"Location\.GetController\.GetLongNameWithFlag", "奥地利"),
        (r"Location\.GetCultureStatusShortLabelForLocation\(.*\)", "主流文化"),
        (r"Location\.GetMonthlyAssimilationForCulture\(.*\)", ""),
        (r"Location\.GetMonthlyChangeForReligion\(.*\)", ""),
        (r"Location\.GetMarket\.MakeScope|Location\.MakeScope", "SCOPE"),
        (r"Province\.GetNameWithNoTooltip|ProvinceDefinition\.GetNameWithNoTooltip", "下奥地利"),
        (r"Province\.GetMonthlyFood", 12.5), (r"Province\.GetFoodCapacityPercent", 0.64),
        (r"Province\.GetFoodFromMarket", 0.0),
        (r"Market\.GetNameWithNoTooltip", "维也纳"),
        (r"Siege\..*", False),
        (r"EcsSceneViewer\..*", False),
        (r"IsLateralViewOpened\(.*\)", False),
        (r"IsInDiplomaticRange\(.*\)", True),
        (r"GetPlayer\.IsEnemy\(.*\)", False),
        (r"IsLocationFaved\(.*\)", False),
        (r"Has\w+IntelOn\(.*\)", True),
        (r"GetClimateFrame\(.*\)", "gfx/interface/icons/climate/continental_frame.dds"),
        (r"GetTopographyIcon\(.*\)", "gfx/interface/topography/flatland.dds"),
        (r"GetClimateIcon\(.*\)", "gfx/interface/icons/climate/continental.dds"),
        (r"GetVegetationIcon\(.*\)", "gfx/interface/vegetation/farmland.dds"),
        (r"GetWinterIcon\(.*\)", "gfx/interface/icons/winter/normal.dds"),
        (r"GetQuickMovements\(.*\)\.GetMovements", []),
        (r"LocationView\.GetConstructionQueueCount\('\(int32\)(\d)'\)", lambda m: 2.0 if m.group(1) == "3" else 0.0),
        (r"LocationView\.GetRenameUIClickAction\.IsVisible", True),
        (r"LocationView\.GetPlayer\.GetInternationalOrganizations", []),
        (r"LocationView\.ShowDisease", False),
        (r"LocationView\.GetPops", pops),
        (r"LocationView\.GetProvincePopTypes", poptypes),
        (r"LocationView\.GetProvincePolitics", politics),
        (r"LocationView\.GetProvinceCultures", cultures),
        (r"LocationView\.GetProvinceReligions", religions),
        (r"GetGraphicalCultureTextureForLocationPopType\(.*'(\w+)'\)",
         lambda m: f"gfx/interface/graphical_cultures/european_gfx/pops/{m.group(1)}.dds"),
        (r"Player\.GetCapital\.Self", "LOC_VIENNA"),
        (r"Location\.CanAssimilate|Location\.CanConvert", True),
        (r"Location\.GetReligionStatusInt\('天主教'\)", 0.0),
        (r"Location\.GetReligionStatusInt\('东正教'\)", 1.0),
        (r"Location\.IsAssimilatingToCulture\('(波希米亚人|匈牙利人)'\)", True),
        (r"Location\.IsAssimilatingToCulture\(.*\)", False),
        (r"Location\.IsConvertingToReligion\('东正教'\)", True),
        (r"Location\.IsConvertingToReligion\(.*\)", False),
        (r"Location\.GetCultureStatusIcon\('奥地利人'\)", "gfx/interface/icons/culture/primary_culture.dds"),
        (r"Location\.GetCultureStatusIcon\(.*\)", "gfx/interface/icons/culture/accepted_culture.dds"),
        (r"Location\.GetGarrisonPercentage", 1.0),
        (r"Location\.GetPossibleTownRights", 2.0),
        (r"Location\.GetRomanFortLevel", "II"),
        (r"GetIntegrationLevelIcon\(.*\)", "gfx/interface/icons/integration_levels/core.dds"),
        (r"CoatOfArmsWrapper\.GetTexture\(.*\)", "gfx/interface/icons/flat_icons/country.dds"),
    ]
    return mocks


def tooltip():
    from scenarios import NOT_CONSUMED, SUPPRESSED, substitution_mocks
    v = {
        "local_wealth_display": 18.40, "local_effective_control": 0.64, "local_tax_base_display": 11.78,
        "local_noble_pop_display": 2, "local_clergy_pop_display": 3, "local_burghers_pop_display": 14,
        "local_commoner_pop_display": 96, "local_tribesmen_pop_display": 0,
        "local_nobles_tax_share": 38, "local_clergy_tax_share": 12, "local_burghers_tax_share": 21,
        "local_commoner_tax_share": 29, "local_tribesmen_tax_share": 0,
        "local_nobles_effective_tax_share": 44, "local_commoner_effective_tax_share": 23,
        "local_total_tax_share": 100,
        "local_commoner_share_transferred_to_nobles": 0.06, "local_commoner_share_lost_to_nobles": 0.06,
        "local_nobles_tax_rate": 0.18, "local_clergy_tax_rate": 0.10, "local_burghers_tax_rate": 0.22,
        "local_commoner_tax_rate": 0.08, "local_tribesmen_tax_rate": 0,
        "local_sol_nobles_income_display": 4.12, "local_sol_clergy_income_display": 1.33,
        "local_sol_burghers_income_display": 2.47, "local_sol_commoners_income_display": 1.86,
        "local_sol_tribesmen_income_display": 0,
        "local_sol_nobles_building_maintenance_display": 1, "local_sol_clergy_building_maintenance_display": 0,
        "local_sol_burghers_building_maintenance_display": 1, "local_sol_commoners_building_maintenance_display": 0,
        "local_sol_tribesmen_building_maintenance_display": 0, "local_sol_total_income": 7.78,
        "local_nobles_savings": 45, "local_clergy_savings": 12, "local_burghers_savings": 30, "local_commoner_savings": 8,
        "local_tribesmen_savings": 0, "local_nobles_savings_target": 50, "local_clergy_savings_target": 15,
        "local_burghers_savings_target": 28, "local_commoner_savings_target": 14, "local_tribesmen_savings_target": 0,
        "local_total_savings_target": 107, "local_total_savings": 95, "local_savings_pressure_adjustment": -0.028,
        "local_sol_liquid_funds_display": 7.51, "local_sol_base_spending_display": 8.40,
        "local_sol_nobles_liquid_display": 3.4, "local_sol_nobles_base_display": 3.0,
        "local_sol_clergy_liquid_display": 1.2, "local_sol_clergy_base_display": 1.2,
        "local_sol_burghers_liquid_display": 1.9, "local_sol_burghers_base_display": 2.2,
        "local_sol_commoners_liquid_display": 1.01, "local_sol_commoners_base_display": 2.0,
        "local_sol_tribesmen_liquid_display": 0, "local_sol_tribesmen_base_display": 0,
        "local_sol_raw_demand_modifier_size": -0.106, "local_sol_pop_demand_modifier_size": -0.079,
    }
    return location() + substitution_mocks("Location.GetOwner.MakeScope") + [
        (r"Location\.MakeScope\.ScriptValue\('(\w+)'\)", lambda m: v.get(m.group(1), Unknown(m.group(0)))),
        (r"GetVariableFromGlobalVariableMap\('sol_market_consumes_(\w+)',.*\)\.GetValue",
         lambda m: 0 if m.group(1) in NOT_CONSUMED else 1),
        (r"GetVariableFromGlobalVariableMap\('sol_market_price_suppressed_(\w+)',.*\)\.GetValue",
         lambda m: 1 if m.group(1) in SUPPRESSED else 0),
        (r"GetVariableFromGlobalVariableMap\('sol_market_substitute_weight_(\w+)',.*\)\.GetValue",
         lambda m: .5 if m.group(1) in SUPPRESSED else 1),
        (r"GetVariableFromGlobalVariableMap\('sol_market_(?:consumes|substitute_weight)_(\w+)',.*\)\.IsSet", True),
    ]


def goods_tooltip(good="wine"):
    """The goods tooltip for one good, to check the SOL substitute-group section.

    `Goods.GetKey` returns the good's own key, so the section's
    Localize(Concatenate('SOL_GOOD_SUB_', Goods.GetKey)) resolves to that good's real
    generated localization - the same string the game prints.
    """
    goods = {
        "Goods.GetKey": good,
        "Goods.GetName": good,
        "Goods.GetNameWithNoTooltip": good,
        "Goods.GetDefaultMarketPrice": 3.2,
        "Goods.GetFlavorText": "GOODS_FLAVOR_TEXT",
        "Goods.IsRawMaterial": good in {"wheat", "rice", "millet", "maize", "potato", "legumes"},
        "Goods.GetNumSources": 4,
        "Goods.GetNumDemands": 7,
        "Goods.GetTransportWeight": 1.5,
        "Goods.GetFoodOutput": 8.0,
        "Goods.HasPopsDemandInfo": True,
        "Goods.GetRawMaterialMethodInfo": "",
        "Goods.GetPopsDemandInfo": "",
        "Goods.GetDemandsInfo": "",
        "Goods.GetDemandsForBuildings": "",
    }
    return location() + [(re.escape(key), value) for key, value in goods.items()]


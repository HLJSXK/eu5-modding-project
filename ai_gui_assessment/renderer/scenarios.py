"""Mock data scenarios (invented sample values) for the renderer."""
GC = "gfx/interface/graphical_cultures/european_gfx/{}.dds"

GOODS = ["amber", "beer", "beeswax", "books", "camels", "chili", "cloth", "cloves", "coal", "cocoa",
         "coffee", "elephants", "fine_cloth", "firearms", "fish", "fruit", "fur", "furniture", "gems", "glass",
         "goods_gold", "horses", "incense", "ivory", "jewelry", "lacquerware", "leather", "legumes", "liquor", "livestock",
         "lumber", "maize", "marble", "masonry", "medicaments", "mercury", "millet", "olives", "paper", "pearls",
         "pepper", "porcelain", "potato", "pottery", "rice", "saffron", "salt", "silver", "sugar", "tea",
         "tobacco", "tools", "weaponry", "wheat", "wild_game", "wine"]
NOT_CONSUMED = {"camels", "chili", "cocoa", "coffee", "elephants", "ivory", "lacquerware", "maize", "potato",
                "porcelain", "saffron", "tea", "tobacco", "cloves"}
SUPPRESSED = {"wheat", "fish", "salt", "beer", "cloth", "legumes", "wine"}

COMMON = [
    (r"GetGraphicalCultureTexture\('(\w+)'\)", lambda m: GC.format(m.group(1))),
    (r"GetGraphicalCultureTextureForCountry\('(\w+)',.*\)", lambda m: GC.format(m.group(1))),
    (r"LateralView\.IsRightPanel", False),
    (r"LateralView\.IsLeftPanel", True),
    (r"LateralView\.Vars\..*", False),
    (r"TutorialIsRunning", False),
    (r"IsPlayerValid", True),
    (r"GetVariableSystem\..*", False),
    (r"PdxGuiWidget\.HasTooltipMetaTitle", False),
    (r"PdxGuiWidget\.HasTooltipMetaGameConcept", False),
    (r"PdxGuiWidget\.IsTooltipLocked", False),
    (r"PdxGuiWidget\.IsUberButtonVisible", True),
    (r"PdxGuiWidget\.IsUberButtonEnabled", True),
    (r"ExtraTooltipInfo\.HasUIAction", False),
    (r"ExtraTooltipInfo\.GetTintColor", None),
    (r"GetDebugFontColor", None),
    (r"GetPlayer\.IsValid|Player\.IsValid|Country\.IsValid", True),
]


def situation():
    pv = {
        "gls_pop_nobles_display": 12, "gls_pop_clergy_display": 18, "gls_pop_burghers_display": 95,
        "gls_pop_commoners_display": 1240, "gls_pop_tribesmen_display": 0,
        "gls_income_nobles_display": 85.40, "gls_income_clergy_display": 41.25, "gls_income_burghers_display": 66.90,
        "gls_income_commoners_display": 52.10, "gls_income_tribesmen_display": 0,
        "gls_building_maintenance_nobles_display": 6, "gls_building_maintenance_clergy_display": 3,
        "gls_building_maintenance_burghers_display": 4, "gls_building_maintenance_commoners_display": 0,
        "gls_building_maintenance_tribesmen_display": 0, "gls_total_income_display": 232.65,
        "gls_nobles_savings_display": 812, "gls_clergy_savings_display": 305, "gls_burghers_savings_display": 640,
        "gls_commoner_savings_display": 210, "gls_tribesmen_savings_display": 0,
        "gls_nobles_savings_target_display": 900, "gls_clergy_savings_target_display": 350,
        "gls_burghers_savings_target_display": 700, "gls_commoner_savings_target_display": 400,
        "gls_tribesmen_savings_target_display": 0, "gls_total_savings_target_display": 2350,
        "gls_total_savings_display": 1967, "gls_savings_pressure_adjustment_display": -0.041,
        "gls_country_liquid_funds_display": 223.18, "gls_country_base_spending_display": 251.40,
        "gls_country_final_demand_scale_deviation_display": -0.112,
    }
    mocks = COMMON + [
        (r"Situation\.GetIcon", "gfx/interface/icons/situations/global_living_standard.dds"),
        (r"Situation\.GetName", "SOL-生活水平"),
        (r"Situation\.HasEnded", False),
        (r"Situation\.GetStartDate", "1337年4月1日"),
        (r"Situation\.GetSituation\.GetKey", "global_living_standard"),
        (r"Situation\.GetSituation\.GetOutcomes", []),
        (r"SituationView\.Vars\.NotExistOrHasValue\(.*\)", True),
        (r"SituationView\.Vars\..*", False),
        (r"SituationView\.GetActionGroups", []),
        (r"SituationView\.HasActiveResolution", False),
        (r"Player\.MakeScope\.ScriptValue\('(\w+)'\)", lambda m: pv.get(m.group(1), 0)),
        (r"GetVariableFromGlobalVariableMap\('gls_country_consumes_(\w+)',Player\.MakeScope\)\.GetValue",
         lambda m: 0 if m.group(1) in NOT_CONSUMED else 1),
    ]
    return mocks


from scen_location import location, tooltip  # noqa: E402,F401


def ui_library(tab="cards", sub=None):
    """Vanilla UI library window (in_game/gui/ui_library.gui): no game data, ideal for engine calibration."""
    sel = {"ui_library_tabs": tab}
    if sub:
        sel.update(sub)
    def hv(m):
        return sel.get(m.group(1)) == m.group(2)
    def nev(m):
        return m.group(1) not in sel or sel.get(m.group(1)) == m.group(2)
    return [
        (r"GetVariableSystem\.HasValue\('(\w+)','(\w+)'\)", hv),
        (r"GetVariableSystem\.NotExistOrHasValue\('(\w+)','(\w+)'\)", nev),
        (r"GetVariableSystem\.Exists\('(\w+)'\)", lambda m: m.group(1) in sel),
    ] + COMMON

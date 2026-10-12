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
    (r"ExtraTooltipInfo\.TooltipIsReady", False),
    (r"UsesTimerLocking", False),
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


from scen_location import goods_tooltip, location, tooltip  # noqa: E402,F401


def ui_library(tab="cards", sub=None):
    """Vanilla UI library window (in_game/gui/ui_library.gui): no game data, ideal for engine calibration."""
    sel = {"ui_library_tabs": tab}
    if sub:
        sel.update(sub)
    def hv(m):
        return sel.get(m.group(1)) == m.group(2)
    def nev(m):
        return m.group(1) not in sel or sel.get(m.group(1)) == m.group(2)
    # The UI Library's dropdown needs a non-empty data model to be created.
    # Its open list is not shown in the reference capture, so one representative
    # province is enough for the control's active-item state.
    provinces = [{"__type__": "Province", "GetName": "默认", "GetNameWithNoTooltip": "默认"}]
    estates = [
        {"__type__": "Estate", "GetType": key, "GetType.GetNameWithNoTooltip": name,
         "GetNameWithNoTooltip": name, "GetSatisfaction": satisfaction,
         "GetRelativePower": power}
        for key, name, satisfaction, power in (
            ("nobles_estate", "贵族", 0.78, 0.52),
            ("clergy_estate", "教士", 0.79, 0.18),
            ("burghers_estate", "市民", 0.49, 0.04),
        )
    ]
    card_mocks = [
        (r"Character\.GetAgeInYears", 49),
        (r"Character\.GetAbility\('(adm|dip|mil)'\)", 66),
        (r"Character\.GetArtistSkill|Character\.GetArtProgress", 0),
        (r"Character\.GetWorksOfArt|Character\.GetTraits", []),
        (r"Character\.GetPortraitBg", None),
        (r"Character\.IsValid|Character\.IsAlive|Character\.IsRuler", True),
        (r"Character\.(Has.*|Is.*|Holds.*)", False),
        (r"CharacterRoleMask\.HasAnyRole", False),
        (r"CharacterRoleMask\.GetRolesCount", 0),
        (r"Country\.Self|InternationalOrganizationsView\.GetPlayer\.GetCapital\.GetOwner\.Self", "sample_country"),
        (r"Country\.GetNameWithNoTooltip", "匈牙利"),
        (r"Country\.GetGreatPowerRank", 8),
        (r"Country\.IsGreatPower|Country\.IsRegionalPower", False),
        (r"Country\.GetFixedPointCurrencyValue\('(stability|legitimacy)'\)", 0.29),
        (r"Country\.GetCurrencyValue\('(stability|legitimacy)'\)", 29),
        (r"Country\.GetDiplomacy\.GetOpinionOf\(.*\)", 96),
        (r"Country\.MakeScope\.GetVariable\('integrated_in_union'\)\.GetValue", 0),
        (r"ResolutionGlue\.GetEnactResolution\.GetNameWithNoTooltip", ""),
        (r"ResolutionGlue\.EnactResolutionIsActive", False),
        (r"DisasterView\.GetDisaster\.GetOwner\.HasActiveRebels", False),
        (r"DisasterView\.GetActions", []),
        (r"DisasterView\.GetDisaster\.GetOwner\.GetGovernment\.GetEstateFromKey\('.*'\)\.ExistsForCountry", False),
        (r"DisasterView\.GetDisaster\.GetOwner\.GetGovernment\.GetEstateFromKey\('.*'\)\.GetRelativePower", 0.0),
        (r"Culture\.Is(Primary|Accepted|Tolerated|Discriminated)\(.*\)", False),
        (r"LawCategory\.IsExpanded|PdxGuiWidget\.IsKeyHoveredByWidgetName", False),
        (r"FilteredSortedList\.IsKeyHoveredByWidgetName\(.*\)", False),
        (r"IsLateralViewOpened\('.*'\)|InternationalOrganizationsView\.ShouldShowRulingHistory", False),
        (r"CoatOfArmsWrapper\.GetTexture\(.*\)", "gfx/interface/icons/flat_icons/country.dds"),
        (r"GetLegitimacyIcon\(.*\)|GetReligionIcon\(.*\)|GetEstateIcon\(Character\.GetEstateType\)|GetReligiousOrderIcon\(.*\)", "gfx/interface/icons/flat_icons/star.dds"),
        (r"IsCharacterFaved\(.*\)", False),
    ] if tab == "cards" else []
    # The tooltip sample in the reference capture carries a two-button action
    # and three available click modifiers.  These are UI-owned values rather
    # than save data, so keep them in this calibration scenario only.
    action_mocks = [
        (r"ExtraTooltipInfo\.HasUIAction", True),
        (r"ExtraTooltipInfo\.GetUIAction", {}),
        (r"IsActionConfirmAndHoldMode|IsActionDialogMode", False),
        (r"StringToConditionListOnlyFail\(UIAction\.Get(?:Left|Right)Click(?:AndConfirm)?Tooltip\)\.GetOutput", ""),
        (r"PdxGuiWidget\.GetTooltipMetaTexture", "gfx/interface/icons/flat_icons/star.dds"),
        (r"UIAction\.HasAnyClickModifierAvailable", True),
        (r"UIAction\.HasClickModifierAvailable\('(shift|ctrl|alt)'\)", True),
        # The vanilla modifier sprites already contain their Shift/Ctrl/Alt
        # labels; the optional description text is not visible in this sample.
        (r"UIAction\.HasClickModifierDescription\('(shift|ctrl|alt)'\)", False),
        (r"UIAction\.GetClickModifierDescription\('shift'\)", "Shift"),
        (r"UIAction\.GetClickModifierDescription\('ctrl'\)", "Ctrl"),
        (r"UIAction\.GetClickModifierDescription\('alt'\)", "Alt"),
        (r"UIAction\.IsClickModifierEnabled\('(shift|ctrl|alt)'\)", False),
        (r"UIAction\.IsLeftClickVisible", True),
        (r"UIAction\.IsRightClickVisible", True),
        # This card demonstrates ordinary left/right actions. Confirm-mode
        # icons are a separate hold/dialog presentation and are hidden here.
        (r"UIAction\.IsLeftClickAndConfirmVisible", False),
        (r"UIAction\.IsRightClickAndConfirmVisible", False),
        (r"UIAction\.IsLeftClickEnabled", True),
        (r"UIAction\.IsRightClickEnabled", True),
        (r"UIAction\.IsLeftClickAndConfirmEnabled", True),
        (r"UIAction\.IsRightClickAndConfirmEnabled", True),
        (r"UIAction\.IsLeftClickModifierEnabled\('(shift|ctrl|alt)'\)", False),
        (r"UIAction\.IsRightClickModifierEnabled\('(shift|ctrl|alt)'\)", False),
        (r"UIAction\.GetLeftClickName|UIAction\.GetRightClickName|UIAction\.GetLeftClickCost|UIAction\.GetRightClickCost|"
         r"UIAction\.GetLeftClickAndConfirmName|UIAction\.GetLeftClickAndConfirmCost|"
         r"UIAction\.GetRightClickAndConfirmName|UIAction\.GetRightClickAndConfirmCost", ""),
    ]
    return [
        (r"GetVariableSystem\.HasValue\('(\w+)','(\w+)'\)", hv),
        (r"GetVariableSystem\.NotExistOrHasValue\('(\w+)','(\w+)'\)", nev),
        (r"GetVariableSystem\.Exists\('(\w+)'\)", lambda m: m.group(1) in sel),
        (r"Player\.GetProvinces", provinces),
        (r"Country\.GetGovernment\.GetEstates", estates),
        (r"Character\.GetNameToFit\(.*\)|Character\.GetNameToFitWithNoTooltip\(.*\)", "默认"),
        (r"Character\.GetAge", 49),
        (r"GetEstateIcon\(.*'(\w+_estate)'\)", lambda m: f"gfx/interface/icons/estates/{m.group(1)}.dds"),
        (r"BlockList\.GetTitle\.IsStringViewNotEmptyOrNull", False),
        (r"BlockList\.GetTitle\.GetStringView", ""),
        (r"BlockList\.GetBlocks", _tooltip_table_blocks()),
        (r"RowList\.GetRows", [
            {"__type__": "CPdxStringView", "GetStringView": "Aristocracy / Plutocracy"},
            {"__type__": "CPdxStringView", "GetStringView": "Traditionalism / Innovation"},
        ]),
        (r"PdxGuiWidget\.GetIndexInParent", 0),
    ] + card_mocks + action_mocks + COMMON


def _tooltip_table_blocks():
    """Representative BlockList data matching TOOLTIP_TABLE_TEST localization."""
    def condition(text):
        return {
            "__type__": "ConditionLine", "GetText": text, "GetIndent": 0,
            "HasPassed": False, "HasFailed": False, "IsNeutral": False,
            "IsWarning": False, "HasCollapsedText": False,
        }

    def pair(left, right):
        return {
            "__type__": "StringViewPair", "GetLeft.GetStringView": left,
            "GetRight.GetStringView": right, "GetIndent": 0,
        }

    def column(title, values, align="left|nobaseline"):
        return {
            "__type__": "TableColumn", "GetTitle.IsStringViewNotEmptyOrNull": bool(title),
            "GetTitle.GetStringView": title, "GetRows": [
                {"__type__": "CPdxStringView", "GetStringView": v} for v in values
            ],
            "GetHorizontalLayoutPolicy": "expanding", "GetTextAlignment": align,
            "IsTextRight": align.startswith("right"), "IsTextLeft": not align.startswith("right"),
        }

    first_columns = [
        column("Title 1", ["Value 1", "Another 1", "Another 1", "Another 1", "Another 1", "Another 1"], "left|nobaseline"),
        column("Title 2", ["Value 2", "Another 2", "Another 2", "Another 2", "Another 2", "Another 2"], "right|nobaseline"),
        column("Title 3", ["Value 3", "Another 3", "Another 3", "Another 3", "Another 3", "Another 3"], "right|nobaseline"),
        column("Title 4", ["Value 4", "Another 4", "Another 4", "Another 4", "Another 4", "Another 4"], "right|nobaseline"),
    ]
    second_columns = [
        column("Title 1", ["Value 1", "Another 1"], "left|nobaseline"),
        column("Title 2", ["Value 2", "Another 2"], "right|nobaseline"),
        column("Title 3", ["Value 3", "Another 3"], "right|nobaseline"),
    ]
    blocks = [
        {"__type__": "BlockListBlock", "IsSingle": True, "IsPair": False, "IsColumns": False,
         "IsRequirements": False, "GetSingleRows": [condition("Main Title"), condition(
             "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Fusce vulputate magna eu lobortis consequat. Vestibulum rhoncus ipsum urna, quis sollicitudin eros venenatis non.")],
         "GetAccumCount": 0},
        {"__type__": "BlockListBlock", "IsSingle": False, "IsPair": True, "IsColumns": False,
         "IsRequirements": False, "GetPairRows": [pair("Modifier 0", "#R -1#!"), pair("Modifier 1", "#G +1.00%#!"), pair("Modifier 2", "#G +5#!")],
         "GetAccumCount": 2},
        {"__type__": "BlockListBlock", "IsSingle": False, "IsPair": False, "IsColumns": True,
         "IsRequirements": False, "GetColumns": first_columns, "GetAccumCount": 5},
        {"__type__": "BlockListBlock", "IsSingle": False, "IsPair": False, "IsColumns": True,
         "IsRequirements": False, "GetColumns": second_columns, "GetAccumCount": 11},
    ]
    return blocks


# ------------------------------------------------------------------ original game screens
def _screen_common():
    """Shared state for standalone captures of data-heavy vanilla views."""
    return COMMON + [
        (r"ShouldShowMessages", True),
        (r"IsLateralViewOpened\('.*'\)", True),
        (r"IsBuildDebug|IsDebugMode", False),
        (r"GameIsMultiplayer", False),
        (r"IsPlayerValid|Player\.IsValid|Country\.IsValid", True),
        (r"PdxGuiWidget\.GetAlpha", 1.0),
        (r"PdxGuiWidget\.GetIndexInDataModel|PdxGuiWidget\.GetIndexInParent", 0),
        (r"IsDataModelEmpty", False),
        (r"Player\.GetGovernment\.GetRulerOrRegent", {"__type__": "Character"}),
        (r"Character\.GetReligiousOrderRef", {"__type__": "ReligiousOrder"}),
    ]


def _option(key, text, tooltip_text, historical=False, high_risk=False):
    return {
        "__type__": "EventOption",
        "EventOption.GetText": text,
        "EventOption.GetTooltip": tooltip_text,
        "EventOption.IsHistorical": historical,
        "EventOption.IsHighRisk": high_risk,
        "EventOption.IsTooltipEmpty": False,
        "GetText": text,
        "GetTooltip": tooltip_text,
        "IsHistorical": historical,
        "IsHighRisk": high_risk,
        "IsTooltipEmpty": False,
    }


def event():
    opts = [_option("", "We face an unsettled age.", "A new chapter begins for the realm.")]
    return _screen_common() + [
        (r"Player", {"__type__": "Country"}),
        (r"Player\.GetGovernment\.GetRuler", {"__type__": "Character"}),
        (r"EventWindow\.GetFirstCharacter", {"__type__": "Character"}),
        (r"EventWindow\.GetTitle", "A New Age Begins"),
        (r"EventWindow\.GetDescription", "Our people stand at a turning point. The old order gives way to new ideas, and every choice will shape the years ahead. We must decide how to meet this changing world."),
        (r"EventWindow\.GetHistoricalInfo", "The chronicles will remember this day."),
        (r"EventWindow\.GetDebugInfo", ""),
        (r"EventWindow\.HasUniqueImage", True),
        (r"EventWindow\.GetUniqueImage", "gfx/interface/illustrations/advances/focus/adm_focus.dds"),
        (r"EventWindow\.HasEventCategoryIcon", False),
        (r"EventWindow\.IsDynamicHistoricalEvent|EventWindow\.IsExpeditionEvent", False),
        (r"EventWindow\.IsSingleOptionEvent", True),
        (r"EventWindow\.GetFirstCharacter\.IsValid|EventWindow\.GetSecondCharacter\.IsValid", False),
        (r"EventWindow\.ShouldShowScrollBar", False),
        (r"EventWindow\.GetOptions", opts),
        (r"GetCurrentAgeAdvancesList\('(adm|dip|mil)'\)", opts[:1]),
        (r"EventWindow\.AccessOptionItemWithKey\('(adm|dip|mil)'\)", opts[0]),
        (r"EventWindow\.GetLockableInfo\.IsUnlocked", True),
        (r"EventOption\.GetText", "Choose an approach"),
        (r"EventOption\.GetTooltip", "Consider the consequences before deciding."),
        (r"AdvanceDefinition\.GetName", "A promising advance"),
        (r"IsInmersionModeDisabled", True),
    ]


def _market_entry(name, price, diff, icon):
    return {
        "__type__": "GoodsMarketEntry",
        "MarketEntry.GetGood.GetName": name,
        "MarketEntry.GetGood.GetIcon": icon,
        "MarketEntry.GetName": name,
        "MarketEntry.GetPrice": price,
        "MarketEntry.GetPriceChange": diff,
        "MarketEntry.GetGood.GetKey": icon.rsplit("_", 1)[-1].replace(".dds", ""),
        "GetGood.GetName": name, "GetGood.GetIcon": icon,
        "GetPrice": price, "GetPriceChange": diff,
        "GoodsMarketEntry.GetGoods.GetName": name,
        "GoodsMarketEntry.GetGoods.GetIcon": icon,
        "GoodsMarketEntry.GetGoods.GetPriceDifferenceIconName": "down" if diff < 0 else "up",
        "GetGoodsIcon(GoodsMarketEntry.GetGoods)": icon,
        "Market.GetBalanceWithoutTrades(Goods.Self)": round(diff * 0.6, 2),
        "Market.GetSupplyImportOnly(Goods.Self)": round(max(-diff, 0), 2),
        "Market.GetDemandExportOnly(Goods.Self)": round(max(diff, 0) * 0.25, 2),
        "Market.GetSurplus(Goods.Self)": round(diff * 0.35, 2),
        "GoodsMarketEntry.GetPrice": price,
        "GoodsMarketEntry.GetStockpile": 68,
        "GoodsMarketEntry.GetMarket.GetCenterLocation.GetModifierValueFixed('maximum_stockpile_capacity')": 150,
        "GoodsMarketEntry.GetGoods": {"__type__": "Goods", "Goods.GetName": name, "Goods.GetIcon": icon},
        "Trade.GetGoods": {"__type__": "Goods", "Goods.GetName": name, "Goods.GetIcon": icon},
    }


def market():
    goods = [
        _market_entry("Wheat", 0.46, 37.05, "gfx/interface/icons/trade_goods/icon_goods_wheat.dds"),
        _market_entry("Lumber", 0.79, 30.47, "gfx/interface/icons/trade_goods/icon_goods_lumber.dds"),
        _market_entry("Wine", 0.99, 26.23, "gfx/interface/icons/trade_goods/icon_goods_wine.dds"),
        _market_entry("Cloth", 1.13, 18.40, "gfx/interface/icons/trade_goods/icon_goods_cloth.dds"),
    ]
    short = [
        _market_entry("Stone", 1.02, -4.83, "gfx/interface/icons/trade_goods/icon_goods_stone.dds"),
        _market_entry("Glass", 4.79, -1.83, "gfx/interface/icons/trade_goods/icon_goods_glass.dds"),
        _market_entry("Salt", 2.01, -1.73, "gfx/interface/icons/trade_goods/icon_goods_salt.dds"),
    ]
    merchants = [
        {"__type__": "Merchant", "Merchant.GetCountry.GetLongNameWithNoTooltip": "Kingdom of Aragon", "Merchant.GetPowerWithLabel": "37.30", "Merchant.GetTotalCapacity": 1.68, "Merchant.GetTradePower": 37.30, "Merchant.GetTradeCapacity": 1.68, "Merchant.GetTradeProfit": 75.51, "GetPowerWithLabel": "37.30", "GetTotalCapacity": 1.68},
        {"__type__": "Merchant", "Merchant.GetCountry.GetLongNameWithNoTooltip": "County of Provence", "Merchant.GetPowerWithLabel": "0.30", "Merchant.GetTotalCapacity": 0.31, "Merchant.GetTradePower": 0.30, "Merchant.GetTradeCapacity": 0.31, "Merchant.GetTradeProfit": -0.98, "GetPowerWithLabel": "0.30", "GetTotalCapacity": 0.31},
    ]
    return _screen_common() + [
        (r"SelectedMarketLateralView\.Vars\.NotExistOrHasValue\(\s*'low_tab',\s*'goods'\s*\)", True),
        (r"SelectedMarketLateralView\.GetMarket\.GetNameWithNoTooltip|Market\.GetNameWithNoTooltip", "Pest Market"),
        (r"SelectedMarketLateralView\.GetMarket\.GetTotalValueTraded", 167.8),
        (r"SelectedMarketLateralView\.GetMarket\.GetMonthlyFoodBalance", 481),
        (r"SelectedMarketLateralView\.GetMarket\.GetFoodStockpile", 84),
        (r"SelectedMarketLateralView\.GetMarket\.GetMaxFoodStockpile", 150),
        (r"SelectedMarketLateralView\.GetMarket\.GetTemporaryDemands", []),
        (r"SelectedMarketLateralView\.GetMarketValuePieChart\.HasData", False),
        (r"SelectedMarketLateralView\.GetMarketValuePieChart\.GetContributions", []),
        (r"Market\.GetCountryPopulation\(Player\.Self\)", 125000),
        (r"Market\.GetUnemployedSlavePopsInMarketText", "0"),
        (r"Market\.GetSlaveTradeNetChangeText", "0"),
        (r"Market\.GetMerchantRanking\(Player\.Self\)", merchants),
        (r"Market\.GetTotalValueTraded", 167.8),
        (r"SelectedMarketLateralView\.GetMarket\.GetCenterLocation\.GetOwner\.GetLongNameWithNoTooltip", "Kingdom of Aragon"),
        (r"SelectedMarketLateralView\.GetMarket\.GetBurgherTradeCapacity", 19.69),
        (r"SelectedMarketLateralView\.GetMarket\.GetCenterLocation\.GetModifierValueWithCountryNoFormat\('local_trade_center_power','global_trade_center_power'\)", 9.8),
        (r"SelectedMarketLateralView\.GetMarket\.GetCenterLocation\.GetModifierValueFixed\('maximum_stockpile_capacity'\)", 150),
        (r"SelectedMarketLateralView\.GetTradeMarketEntries", goods),
        (r"SelectedMarketLateralView\.GetFoodSources", short),
        (r"SelectedMarketLateralView\.GetMerchants", merchants),
        (r"Market\.GetMerchants", merchants),
        (r"Market\.GetMonthlyFoodBalance", 481),
        (r"SelectedMarketLateralView\.GetGoodsMarketEntries", goods),
        (r"SelectedMarketLateralView\.GetInRangeGoodsEntries", short),
        (r"SelectedMarketLateralView\.GetBannedImports|SelectedMarketLateralView\.GetBannedExports", []),
        (r"GetCountryCoatOfArms\(Country\.Self\)", "gfx/interface/icons/flat_icons/country.dds"),
        (r"Country\.GetLongNameWithNoTooltip|Market\.GetOwner\.GetLongNameWithNoTooltip", "Kingdom of Aragon"),
        (r"GetDataModelSize\(.*\)", 0),
        (r"GetGoodsIcon\(.*\)", "gfx/interface/icons/trade_goods/icon_goods_wheat.dds"),
        (r"SelectedMarketLateralView\.GetGoodsTexture", "gfx/interface/illustrations/bg/bg_markets.dds"),
        (r"CoatOfArmsWrapper\.GetTexture\(.*\)", "gfx/interface/icons/flat_icons/country.dds"),
        (r"GoodsMarketEntry\.GetPrice", 0.46),
        (r"GoodsMarketEntry\.GetGoods\.GetPriceDifferenceIconName\(.*\)", "price_increase"),
        (r"Market\.(GetTotalMerchantCapacity|GetAvailableTradeCapacity|GetFoodStockpile|GetMaxFoodStockpile|GetFoodPrice|GetSupplyImportOnly|GetDemandExportOnly|GetSurplus|GetBalanceWithoutTrades)\(?.*", 0),
        (r"Market\.(Has.*|WillRunOutOfFoodStockpile|HasStarvingProvinces)", False),
        (r"Trade\.(Get.*|Is.*|Has.*)", 0),
        (r"Merchant\.GetTotalCapacity", 1.68),
        (r"SearchBar\.HasTextSearchFilters", True),
        (r"SearchBar\.HasSearchFilterCategories", True),
        (r"SearchBar\.IsTextFilterEmpty", True),
        (r"SearchBar\.Manager\.IsLeftPanel", True),
        (r"SearchBar\.HasVisibleEnabledSearchFilters", True),
        (r"SearchBar\.GetEnabledFilters", [{"__type__": "SearchFilter", "GetName": "市场上的有关商品", "IsCustomFilter": False}]),
        (r"SearchBar\.GetCustomEnabledFilters|SearchBar\.GetAutocompleteEntries", []),
        (r"SearchBar\.HasPin", False),
        (r"IconAndText\.GetIcon", ""),
        (r"IconAndText\.GetText", "市场上的有关商品"),
        (r"FilteredSortedList\.GetSortKeys", [{}]),
        (r"FilteredSortedList\.ToggleAllEnabled", False),
        (r"SortKey\.IsSortedBy", False),
        (r"SortKey\.IsSortedInDescending", False),
        (r"SortKey\.GetIcon", "gfx/interface/icons/flat_icons/arrow_sortby.dds"),
        (r"FilteredSortedList\..*|SearchBar\..*", False),
        (r"SelectedMarketLateralView\.Vars\..*", False),
        (r"IsMarket.*|IsFocusMarketSelected|IsLateralViewOpenedWithParams\(.*\)", False),
        (r"Province\..*|MarketCountryNeeds\..*", 0),
    ]


def government():
    def estate(key, name, power, population, satisfaction):
        return {"__type__": "EstatesItem", "Estate.GetType": key,
                "Estate.GetNameWithNoTooltip": name, "Estate.GetLongNameWithNoTooltip": name,
                "Estate.GetName": name, "Estate.GetRelativePower": power,
                "Estate.GetTotalPopulation": population, "Estate.GetSatisfaction": satisfaction,
                "Estate.GetMonthlySatisfactionChange": 0.01, "EstatesItem.GetPrivileges": [],
                "GetEstateIcon(Estate.GetType)": f"gfx/interface/icons/estates/{key}.dds"}

    estates = [estate("nobles_estate", "Nobles", 0.34, 16000, 0.72),
               estate("clergy_estate", "Clergy", 0.28, 18000, 0.64),
               estate("burghers_estate", "Burghers", 0.38, 24000, 0.81)]
    return _screen_common() + [
        (r"GovernmentView\.IsLowerTabEstates", True),
        (r"GovernmentView\.GetSortedEstates", estates),
        (r"Player\.GetGovernment\.GetEstateFromKey\('(\w+)'\)\.GetType", lambda m: m.group(1)),
        (r"GovernmentView\.GetTraits|GovernmentView\.GetReforms|GovernmentView\.GetCabinets|GovernmentView\.GetParliamentActions|GovernmentView\.GetAgendas", []),
        (r"GovernmentView\.GetPlayer\.GetModifierCappedValueWithNoTooltip\('government_size'\)", 49),
        (r"Player\.GetModifierValueNoFormat\('country_cabinet_efficiency'\)", 0.78),
        (r"GovernmentView\.GetPlayer\.GetGovernment\.GetRuler", {"__type__": "Character", "Character.GetNameToFit": "King Alfonso", "Character.GetAge": 49}),
        (r"GovernmentView\.GetPlayer\.GetGovernment\.HasRuler|GovernmentView\.GetPlayer\.GetGovernment\.HasRulerOrRegent", True),
        (r"Country\.GetGovernment\.HasRulerOrRegent|Country\.GetGovernment\.CareAboutProducingHeirs", True),
        (r"Player\.GetGovernment\.HasRuler|Player\.GetGovernment\.HasRulerOrRegent", True),
        (r"HeirSelectionCandidate\.GetHeirSelection\.ShouldShowCandidates", False),
        (r"Country\.GetCapital\.GetNameWithNoTooltip", "Pest"),
        (r"Country\.GetCapital\.GetRankIcon", "gfx/interface/icons/flat_icons/star.dds"),
        (r"Character\.GetNameToFit\('(int32)-1', '(bool)yes'\)", "King Alfonso"),
        (r"Character\.GetAge", 49),
        (r"Character\.GetAbility\('(adm|dip|mil)'\)", 66),
        (r"GovernmentView\.GetHeirSelection\.GetHeirCandidatesCount", 1),
        (r"Player\.GetAverageControl", 0.8),
        (r"Estate\.GetType\.IsAlwaysLoyal", False),
        (r"Estate\.GetTargetSatisfactionTooltipWrapper", "75%"),
        (r"Estate\.GetCultureStatusIcon", "gfx/interface/icons/flat_icons/star.dds"),
        (r"GetAutomatedSystemItem.*", False),
        (r"Player\.IsMovingCapital|GovernmentView\.CanMoveCapital|GovernmentView\.CanCancelMoveCapital", False),
        (r"Estate\.(GetRelativePower|GetSatisfaction|GetMonthlySatisfactionChange|GetTotalPopulation|GetAvgEnfranchisment)", 0.5),
        (r"Estate\.(Has.*|Is.*)", False),
        (r"Estate\.GetNameWithNoTooltip", "Nobles"),
        (r"Character\.(Has.*|Is.*|Holds.*)", False),
        (r"Government\.(Has.*|CareAbout.*)", False),
        (r"Country\.(Has.*|Is.*|CareAbout.*)", False),
        (r"Player\.GetDiplomacy\.GetOverlord\.IsValid", False),
        (r"GetEstateIcon\(.*'(\w+_estate)'\)", lambda m: f"gfx/interface/icons/estates/{m.group(1)}.dds"),
        (r"GetEstate.*|Get.*Icon\(.*\)|CoatOfArmsWrapper\.GetTexture\(.*\)", "gfx/interface/icons/flat_icons/star.dds"),
        (r"GovernmentView\.IsLowerTab.*", False),
        (r"TimedModifierOwner\.GetModifiers|Country\.GetHegemons", []),
        (r"Automated.*\.IsEnabled|AuxVars\.Exists\(.*\)", False),
        (r"EcsSceneViewer\..*|UseDynamicParliamentName|PlayerHasBureaucracies", False),
        (r"IsInmersionModeDisabled", True),
    ]


def _unit(name, strength, size):
    return {"__type__": "CombatSubUnit", "CombatSubUnitArray.GetName": name, "CombatSubUnit.GetName": name, "CombatSubUnitArray.GetEngagedStrength": strength,
            "CombatSubUnitArray.GetNonEngagedStrength": strength, "CombatSubUnitArray.GetEngagedSize": size,
            "CombatSubUnitArray.GetNonEngagedSize": size, "GetEngagedStrength": strength, "GetNonEngagedStrength": strength,
            "GetEngagedSize": size, "GetNonEngagedSize": size, "CombatSubUnitArray.GetSize": size, "GetSize": size,
            "CombatSubUnitArray.GetMoralePercentage": 0.82, "GetMoralePercentage": 0.82}


def _flank(strength, waiting=0):
    return {
        "__type__": "CombatSubUnitArray", "GetEngagedStrength": strength,
        "GetNonEngagedStrength": waiting, "GetEngagedSize": int(strength > 0),
        "GetNonEngagedSize": int(waiting > 0), "GetSize": int(strength > 0) + int(waiting > 0),
        "GetEngagedFrontage": float(strength > 0), "GetNonEngagedFrontage": float(waiting > 0),
        "GetMoralePercentage": 0.82, "GetCombatSide.GetPossibleFrontage": 20,
        "GetEngaged": [_unit("Regiment", strength, 1)] if strength else [],
        "GetNonEngaged": [_unit("Reserve", waiting, 1)] if waiting else [],
        "GetCanBombard": [],
    }


def battle():
    def side(strength, flanks, waiting, losses, player):
        return {
            "__type__": "CombatSide", "GetEngagedUnitsStrength": strength,
            "GetVisualStrength": f"{strength:,}", "GetPossibleFrontage": 20,
            "GetMoralePercent": 0.82, "GetMaxMorale": 3.8,
            "GetCombinedArmsBonus": 0.08, "GetCountry": {"__type__": "Country", "IsPlayer": player},
            "GetBattleSide.GetTotalImprisoned": 0, "GetBattleSide.GetLosses": losses,
            "GetRetreated": _flank(0),
            **{f"Get{key}": _flank(value, waiting[key]) for key, value in flanks.items()},
            "GetReserves": _flank(0),
        }

    sides = {
        "Attacker": side(871, {"Left": 460, "Center": 0, "Right": 327},
                         {"Left": 1, "Center": 83, "Right": 0}, 284, False),
        "Defender": side(4802, {"Left": 1308, "Center": 2322, "Right": 578},
                         {"Left": 44, "Center": 0, "Right": 549}, 0, True),
    }
    return _screen_common() + [
        (r"BattleView\.GetCombat", {"__type__": "Combat"}),
        (r"BattleView\.GetCombat\.GetName|Combat\.GetName", "Battle of Pest"),
        (r"Combat\.IsActive|BattleView\.GetCombat\.IsActive", True),
        (r"Combat\.IsInBombardPhase|Combat\.IsNavalCombat", False),
        (r"CombatSide\.IsNaval", False),
        (r"EcsSceneViewer\.Is2DScene|EcsSceneViewer\.IsUltraWide", False),
        (r"HasBattleFiredAtHover\(SubUnit\.Self\)", False),
        (r"GetBattleUnitIcon\(SubUnit\.GetDefinition\)", "gfx/interface/icons/flat_icons/star.dds"),
        (r"Combat\.Get(Attacker|Defender)", lambda m: sides[m.group(1)]),
        (r"Combat\.Get(Attacker|Defender)\.Get(Left|Center|Right|Reserves)\.GetEngagedFrontage",
         lambda m: sides[m.group(1)]["Get" + m.group(2)]["GetEngagedFrontage"]),
        (r"Combat\.GetAttacker\.GetCombatModifiers|Combat\.GetDefender\.GetCombatModifiers|CombatSide\.GetCombatModifiers", []),
        (r"CombatSubUnitArray\.GetEngaged|CombatSubUnitArray\.GetNonEngaged|CombatSubUnitArray\.GetCanBombard", []),
        (r"DataModelFirst\(.*\)|DataModelSkipFirst\(.*\)", []),
        (r"CombatSide\.GetEngagedUnitsStrength", 4802),
        (r"CombatSide\.GetVisualStrength", "4,802"),
        (r"CombatSide\.GetMoralePercent|Combat\.GetAttacker\.GetMoralePercent|Combat\.GetDefender\.GetMoralePercent", 0.82),
        (r"CombatSide\.GetMaxMorale", 3.8),
        (r"CombatSide\.GetCombinedArmsBonus", 0.08),
        (r"CombatSide\.GetPossibleFrontage|CombatSubUnitArray\.GetCombatSide\.GetPossibleFrontage", 20),
        (r"CombatSubUnitArray\.GetEngagedStrength", 4802),
        (r"CombatSubUnitArray\.GetNonEngagedStrength", 1220),
        (r"CombatSubUnitArray\.GetEngagedSize|CombatSubUnitArray\.GetNonEngagedSize|CombatSubUnitArray\.GetSize", 12),
        (r"CombatSubUnitArray\.GetMoralePercentage", 0.82),
        (r"CombatSide\.Get.*|CombatSubUnitArray\.Get.*", 0),
        (r"CombatSide\.CanEngage.*", True),
        (r"Combat\.GenerateBattlefield.*", ""),
        (r"CombatSide\.(Get.*|CanEngage.*)", 0),
        (r"CombatSubUnitArray\.Get.*", 0),
        (r"Character\.(Has.*|Is.*)", False),
        (r"Character\.HoldsCabinetPosition", False),
        (r"GetCountryCoatOfArms\(.*\)|CoatOfArmsWrapper\.GetTexture\(.*\)", "gfx/interface/icons/flat_icons/country.dds"),
        (r"BattleView\.GetCombat\.Get.*|Combat\.Get.*", 0),
    ]

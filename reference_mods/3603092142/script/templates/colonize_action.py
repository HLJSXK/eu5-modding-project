from dataclasses import dataclass

@dataclass(frozen=True)
class ColonizeAction:
    TEMPLATE_TOP ='''REPLACE:create_colonial_charter = {
    type = owncountry
    
    potential = {
        scope:actor = {
            num_provinces > 0
            is_rebel_country = no
            NOT = { country_type = building }
            modifier:can_colonize = yes
            OR = {
                is_ai = no 
                ai_country_should_colonize = yes
            }
        }
    }

    allow = {
        scope:actor = {
            total_population >= 5
        }
    }

    ai_tick = monthly
    ai_tick_frequency = 6
    automation_tick = monthly
    automation_tick_frequency = 1

    player_automated_category = colonies
    
    price = price:create_colonial_charter
    
    select_trigger = {
        top_widget = colony_item_card_at_province_select
        looking_for_a = province_definition
        source = actor
        source_flags = possible_colonial_charters
        target_flag = target
        cache_targets = yes #these are the same no matter where we're coming from
        name = "create_colonial_charter_select_province_definition"
        none_available_msg_key = "create_colonial_charter_no_provinces"
        column = {
            data = colonial_charter
        }
        # no trigger, possible_colonial_charters does this for us in code
        # scope:actor = colonizer, root = province_definition
        enabled = {
            scope:actor = {
                is_valid_colonial_charter = prev
                custom_tooltip = {
                    text = settle_the_frontier_ct
                    not = {
                        any_cabinet = {
                            has_cabinet_action = yes
                            cabinet_action = cabinet_action:settle_the_frontier
                            interaction_target:target = root
                        }
                    }
                }
            }
            ### check if player & no player restrictions is on
            trigger_if = {
                limit = {
                    scope:actor = { is_ai = no }
                    has_game_rule = htc_player_no_restrictions
                }
                has_game_rule = htc_player_no_restrictions
            }
            ### strict AI limits, can't use year unlocks
            trigger_else_if = {
                limit = {
                    scope:actor = {
                        is_ai = yes
                        or = {
                            has_or_had_tag = ZAN
                            has_or_had_tag = ZMW
                        }
                    }
                }
                and = {
                    current_year >= 1600
                    region = scope:actor.capital.region
                }
            }
            trigger_else_if = {
                limit = {
                    scope:actor = {
                        is_ai = yes
                        is_subject_type = colonial_nation
                    }
                }
                and = {
                    region = scope:actor.capital.region
                    or = {
                        is_ai = no
                        tax_base >= 100
                        monthly_balance >= 50
                    }
                }
            }
            trigger_else_if = {
                limit = {
                    scope:actor = {
                        or = {
                            is_ai = no
                            # europeans
                            capital ?= { sub_continent = sub_continent:western_europe }
                            culture = { has_culture_group = culture_group:russian_group }
                            # other possible colonial powers
                            has_or_had_tag = MAL
                            has_or_had_tag = TUR
                            has_or_had_tag = OMA
                            has_or_had_tag = CHI
                            culture = { has_culture_group = culture_group:japanese_group }
                            # natives
                            religion.group = religion_group:tonal_group
                            religion = religion:inti
                            culture.language = language:kongo_language
                            has_or_had_tag = ZAN
                            has_or_had_tag = ZMW
                        }
                    }
                }
                or = {
                    # game rule tooltip, not check
                    custom_tooltip = {
                        text = htc_player_no_restrictions_why
                        and = {
                            scope:actor = { is_ai = no }
                            has_game_rule = htc_player_no_restrictions
                        }
                    }
                    ### early colonies for natives
                    trigger_if = {
                        limit = { region = region:kongo_region }
                        scope:actor.culture.language = language:kongo_language
                    }
                    trigger_else_if = {
                        limit = {
                            or = {
                                region = region:aridoamerica_region
                                region = region:mesoamerica_region
                                region = region:central_america_region
                            }
                        }
                        and = {
                            scope:actor.religion.group = religion_group:tonal_group
                            any_location_in_province_definition = {
                                adjacent_to_owned_by = scope:actor
                            }
                        }
                    }
                    trigger_else_if = {
                        limit = { region = region:andes_region }
                        scope:actor.religion = religion:inti
                    }
                    trigger_else_if = {
                        limit = { region = region:japan_region }
                        scope:actor.culture = { has_culture_group = culture_group:japanese_group }
                    }
                    trigger_else_if = {
                        limit = { region = region:scandinavian_region }
                        scope:actor.culture = { has_culture_group = culture_group:scandinavian_group }
                    }
                    trigger_else_if = {
                        limit = {
                            or = {
                                this = province_definition:madeira_province
                                this = province_definition:azores_province
                            }
                        }
                        scope:actor = { has_or_had_tag = POR }
                    }
                    trigger_else_if = {
                        limit = { this = province_definition:canary_islands_province }
                        scope:actor = {
                            or = {
                                has_or_had_tag = CAS
                                has_or_had_tag = SPA
                            }
                        }
                    }
                    ### year restrictions
                    ## siberia
                    trigger_if = {
                        limit = { region = region:west_siberia_region }
                        and = {
                            current_year >= 1560
                            trigger_if = {
                                limit = { is_ai = yes }
                                culture = { has_culture_group = culture_group:russian_group }
                            }
                        }
                    }
                    trigger_else_if = {
                        limit = { sub_continent = sub_continent:north_asia }
                        and = {
                            current_year >= 1600
                            trigger_if = {
                                limit = { is_ai = yes }
                                culture = { has_culture_group = culture_group:russian_group }
                            }
                        }
                    }
                    ## autogenerated restrictions
                    '''

    TEMPLATE_BOTTOM = '''
                }
            }
        }
    }

    effect = {
        scope:actor = {
            if = {
                limit = {
                    exists = scope:target
                }
                create_colonial_charter = {
                    target = scope:target
                }
            }
        }
    }

    ai_will_do = {
        if = {
            limit = {
                scope:actor = {
				    monthly_balance > 1
                    or = {
                        has_colonial_charters = yes
                        is_colonial_top_overlord = yes
                        scope:target = {
                            any_location_in_province_definition = {
                                adjacent_to_owned_by = scope:actor
                            }
                        }
                    }
                }
            }
            add = "scope:actor.colonial_charter_utility(scope:target)"
        }
        else = {
            add = -1000
        }
    }
}
'''
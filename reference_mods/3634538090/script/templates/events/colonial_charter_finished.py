from dataclasses import dataclass
from templates import TemplateData

@dataclass(frozen=True)
class ColonialCharterFinishedTemplate(TemplateData):
    NAMESPACE = 'colonial_charter'

    FORM_TRIGGERS_JOIN = '''
                            '''

    UNIQUE_COLONY_FORM_TEMPLATE = '''
                    {IF_OR_ELSE_IF} = {{
                        limit = {{
                            NOT = {{ country_exists = c:{TAG} }}
                            {TRIGGERS}
                        }}
                        name = {{
                            name = {TAG}
                        }}
                        define_unique_country_tag = {TAG}
                        change_country_name = {TAG}
                        change_country_adjective = {TAG}_ADJ
                        set_variable = {{ name = htc_unique_colony value = yes }}
                    }}
'''

    JOIN_TRIGGERS_JOIN = '''
                '''

    UNIQUE_COLONY_JOIN_TEMPLATE = '''
        {IF_OR_ELSE_IF} = {{
            limit = {{
                {TRIGGERS}
            }}
            if = {{
                limit = {{
                    country_exists = c:{TAG}
                    c:{TAG} ?= {{
                        is_subject = yes
                        is_subject_of = scope:actor
                    }}
                }}
                c:{TAG} = {{ save_scope_as = unique_colony }}
            }}
            else = {{
                set_local_variable = {{ name = can_be_unique_colony value = yes }}
            }}
        }}
'''

    EVENT_TEMPLATE = '''colonial_charter.100 = {{
    hide_portraits = yes
    type = country_event	

    title = colonial_charter.100.title
    desc = colonial_charter.100.desc
    outcome = neutral

    immediate = {{
        save_scope_as = actor
        #Select the best location for a capital
        if = {{
            limit = {{
                scope:target = {{
                    any_location_in_province = {{
                        is_city = yes
                        count = 0
                    }}
                }}
            }}
            scope:target = {{
                ordered_location_in_province = {{
                    max = 1
                    order_by = best_capital_for_colony
                    
                    save_scope_as = new_town
                }}
            }}       
        }}

{UNIQUE_COLONY_JOIN_CHECKS}
        
        #Get a colonial nation vassal neighboring the target province
        if = {{
            limit = {{
                scope:target = {{
                    any_location_in_province = {{
                        any_coast_border_location = {{
                            has_owner = yes
                            owner = {{
                                is_subject_of = ROOT
                                is_subject_type = colonial_nation
                                NOT = {{ has_variable = htc_unique_colony }}
                                NAND = {{ exists = scope:unique_colony this = scope:unique_colony }}
                            }}
                        }}
                    }}
                }}
            }}
            scope:target = {{
                random_location_in_province = {{
                    limit = {{
                        any_coast_border_location = {{
                            has_owner = yes
                            owner = {{
                                is_subject_of = ROOT
                                is_subject_type = colonial_nation
                                NOT = {{ has_variable = htc_unique_colony }}
                                NAND = {{ exists = scope:unique_colony this = scope:unique_colony }}
                            }}
                        }}
                    }}
                    random_coast_border_location = {{
                        limit = {{
                            has_owner = yes
                            owner = {{
                                is_subject_of = ROOT
                                is_subject_type = colonial_nation
                                NOT = {{ has_variable = htc_unique_colony }}
                                NAND = {{ exists = scope:unique_colony this = scope:unique_colony }}
                            }}
                        }}
                        owner = {{ save_scope_as = scope_adjacent_area_subject }}
                    }}
                }}
            }}
        }}

        #Get the most populous colonial nation vassal with capital in the same region
        ordered_subject = {{
            limit = {{
                is_subject_type = colonial_nation
                capital = {{ region = scope:target.region }}
                NOT = {{ has_variable = htc_unique_colony }}
                NAND = {{ exists = scope:unique_colony this = scope:unique_colony }}
                NAND = {{ exists = scope:scope_adjacent_area_subject this = scope:scope_adjacent_area_subject }}
            }}
            order_by = total_population
            max = 1
            save_scope_as = regional_subject
        }}

        #Save the Province Capital for the event image
        scope:target = {{
            capital = {{ save_scope_as = target_location }}
        }}
    }}
    
    option = {{ # Form a unique Colonial Subject
        name = htc_unique_colonies.a
        high_risk_option = yes

        trigger = {{
            scope:target = {{ is_overseas_for_owner = yes }}
            has_local_variable = can_be_unique_colony
        }}
        
        if = {{
            limit = {{
                exists = scope:new_town
            }}
            scope:new_town = {{
                change_location_rank_effect = {{ location_rank = location_rank:town }}
            }}
        }}
        
        scope:target = {{ 
            create_location_country_from_province = {{
                subject_type = subject_type:colonial_nation
            
                hidden_effect = {{
                    setup_colonial_nation = yes

{UNIQUE_COLONY_FORM_CHECKS}

                }}
            }}
        }}
        
        ai_will_select = {{
            value = 9999
        }}
    }}
    
    option = {{ # Join it to unique_colony
        name = htc_unique_colonies.b
        high_risk_option = yes

        trigger = {{
            exists = scope:unique_colony
        }}
        
        scope:target = {{
            change_province_owner = scope:unique_colony
        }}

        ai_will_select = {{
            value = 4000
        }}
    }}

    option = {{
        name = colonial_charter.100.a
        trigger = {{
            scope:target = {{ is_overseas_for_owner = yes }}
            or = {{
                is_ai = no
                and = {{
                    is_ai = yes
                    not = {{ exists = scope:unique_colony }}
                }}
            }}
        }}
        
        if = {{
            limit = {{
                exists = scope:new_town
            }}
            scope:new_town = {{
                change_location_rank_effect = {{ location_rank = location_rank:town }}
            }}
        }}
        
        scope:target = {{ 
            create_location_country_from_province = {{
                subject_type = subject_type:colonial_nation
            
                hidden_effect = {{
                    setup_colonial_nation = yes
                }}
            }}
        }}
        
        ai_will_select = {{
            value = 50
        }}
    }}

    option = {{ # Join it to scope_adjacent_area_subject
        name = colonial_charter.100.g

        trigger = {{
            exists = scope:scope_adjacent_area_subject
        }}

        if = {{
            limit = {{
                exists = scope:new_town
            }}
            scope:new_town = {{
                change_location_rank_effect = {{ location_rank = location_rank:town }}
                cc_setup_new_town = yes
            }}
        }}

        scope:target = {{
            change_province_owner = scope:scope_adjacent_area_subject
        }}

        ai_will_select = {{
            value = 1000
        }}
    }}

    option = {{ # Join it to regional_subject
        name = colonial_charter.100.f

        trigger = {{
            exists = scope:regional_subject
        }}

        if = {{
            limit = {{
                exists = scope:new_town
            }}
            scope:new_town = {{
                change_location_rank_effect = {{ location_rank = location_rank:town }}
                cc_setup_new_town = yes
            }}
        }}

        scope:target = {{
            change_province_owner = scope:regional_subject
        }}

        ai_will_select = {{
            value = 2000
        }}
    }}

    option = {{ #Keep it as part of the Metropolis
        name = colonial_charter.100.d
        
        trigger = {{
            or = {{
                is_ai = no
                scope:target = {{ is_overseas_for_owner = no }}
            }}
        }}

        scope:target = {{ 
            every_location_in_province = {{
                limit = {{ integration_level = colonized }}
                change_integration_level = integrated
            }}
        }}

        ai_chance = {{
            value = 100
        }}
    }}

    option = {{ #Play as the Colony
        name = colonial_charter.100.e
        high_risk_option = yes
        trigger = {{
            is_human = yes
            scope:target = {{ is_overseas_for_owner = yes }}
        }}
        if = {{
            limit = {{
                exists = scope:new_town
            }}
            scope:new_town = {{
                change_location_rank_effect = {{ location_rank = location_rank:town }}
            }}
        }}
        scope:target = {{ 
            create_location_country_from_province = {{
                subject_type = subject_type:colonial_nation
                hidden_effect = {{
                    setup_colonial_nation = yes
                }}
                save_scope_as = target_country
            }}
        }}
        custom_tooltip = {{
            text = colonial_charter.100.e.tt
            change_player = scope:target_country
        }}

        # needed when ai and human is playing together
        ai_chance = {{
            value = -1000
        }}
    }}

    after = {{
        trigger_event_silently = treaty_of_tordesillas.1
    }}
}}
'''

    
    UNIQUE_COLONY_LOCALIZATION_TEMPLATE = '''
  {TAG}: "{NAME}"
  {TAG}_ADJ: "{ADJECTIVE}"
'''
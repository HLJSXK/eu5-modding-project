import os

def enable_charters():
    from lib.enable_generator import CharterFilterGenerator
    from templates.create_colonial_charter.colonize_action import ColonizeAction

    for dirpath, dirnames, filenames in os.walk('colonies/enable'):
        filters = []
        for file in filenames:
            g = CharterFilterGenerator(os.path.join(dirpath, file))
            filters.append(g.get_enabled_filter())

        with open(os.path.join('../in_game/common/generic_actions/htc_colonial_charters_generated.txt'), 'w', encoding='utf-8-sig') as file:
            file.write(
                ColonizeAction.TEMPLATE_TOP +
                ''.join(filters).rstrip() +
                ColonizeAction.TEMPLATE_BOTTOM)

def charter_events():
    from lib.events_generator import ColonyEventGenerator
    from lib.monthly_event_generator import MonthlyPulseGenerator

    events = []
    for dirpath, dirnames, filenames in os.walk('colonies/events'):
        filters = []
        for file in filenames:
            g = ColonyEventGenerator(os.path.join(dirpath, file))
            events += g.write_all('../in_game/events/generated')
    p = MonthlyPulseGenerator(events)
    p.write_on_action('../in_game/common/on_action/htc_ai_pulse.txt')

def colonial_tags():
    # OUT = './output/htc_colonial_charter_overrides.txt'
    # OUT_LOCALIZATION = './output/htc_colonial_countries_l_english.yml'
    OUT = '../in_game/events/colonization/0_htc_colonial_charter_overrides.txt'
    OUT_LOCALIZATION = '../main_menu/localization/english/countries/htc_colonial_nations_l_english.yml'
    from lib.colonial_charter_finished_generator import ColonialCharterFinishedGenerator
    from templates.events.colonial_charter_finished import ColonialCharterFinishedTemplate

    unique_cns = {}

    for dirpath, dirnames, filenames in os.walk('colonies/tags'):
        for file in filenames:
            g = ColonialCharterFinishedGenerator(os.path.join(dirpath, file))
            unique_cns.update(g.get_unique_colonial_nations())
    with open(OUT, 'w', encoding='utf-8-sig') as file:
        file.write(
            f'namespace = {ColonialCharterFinishedTemplate.NAMESPACE}\n\n' +
            ColonialCharterFinishedTemplate.EVENT_TEMPLATE.format(
                UNIQUE_COLONY_JOIN_CHECKS = "\n".join(unique_cns["join_checks"]),
                UNIQUE_COLONY_FORM_CHECKS = "\n".join(unique_cns["form_checks"])
            )
        )
    with open(OUT_LOCALIZATION, 'w', encoding='utf-8-sig') as file:
        file.write(
            f'l_english:\n' + '\n'.join(unique_cns["localization"])
        )

enable_charters()
charter_events()
colonial_tags()
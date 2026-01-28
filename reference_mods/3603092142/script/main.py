from lib.enable_generator import CharterFilterGenerator
from lib.events_generator import ColonyEventGenerator
from lib.scripted_names_generator import ScriptedNamesGenerator
from templates.colonize_action import ColonizeAction
import os

def enable_charters():
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
    for dirpath, dirnames, filenames in os.walk('colonies/events'):
        filters = []
        for file in filenames:
            g = ColonyEventGenerator(os.path.join(dirpath, file))
            g.write_all('../in_game/events/generated')

def scripted_names():
    for dirpath, dirnames, filenames in os.walk('colonies/names'):
        for file in filenames:
            g = ScriptedNamesGenerator(os.path.join(dirpath, file))
            g.write_all('../in_game/common/scripted_country_names/htc_scripted_country_names.txt', '../main_menu/localization/english/htc_scripted_country_names_l_english.yml')

enable_charters()
charter_events()
# scripted_names()
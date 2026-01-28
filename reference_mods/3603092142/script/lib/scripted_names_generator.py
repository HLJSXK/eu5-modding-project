import yaml
from os import path
import re
from templates.scripted_name import ScriptedNames

class ScriptedNamesGenerator:
    def __init__(self, filepath: str):
        with open(filepath, encoding='utf-8-sig') as file:
            self.parsed: dict = yaml.safe_load(file)
            self.name = path.basename(filepath)[:-4]
    
    def write_events(self, event_out: str, file_data: list[dict[str, str]]):
        print(f'writing events...')
        # write events
        for data in file_data:
            if not data: continue
            with open(path.join(event_out, f'{data['namespace']}.txt'), 'w', encoding='utf-8-sig') as file:
                file.write(data['event'])

    def write_all(self, scripted_out: str, localization_out: str):
        print(f'loading data for `{self.name}`...')

        scripted_names_setting_file = open(scripted_out, 'w', encoding='utf-8-sig')
        scripted_names_localization_file = open(localization_out, 'w', encoding='utf-8-sig')
        scripted_names_localization_file.write('l_english:')

        for region, scripted_names in self.parsed.items():
            if not scripted_names: continue


            for identifier, name_data in scripted_names.items():
                name = name_data['name']
                adjective = name_data['adjective']
                country_trigger = name_data.get('country_trigger') or ''
                scripted_names_setting_file.write(ScriptedNames.SCRIPTED_TEMPLATE.format(
                    region=region,
                    identifier=identifier,
                    name=name,
                    adjective=adjective,
                    country_trigger=country_trigger
                ))
                scripted_names_localization_file.write(ScriptedNames.LOCALIZATION_TEMPLATE.format(
                    region=region,
                    identifier=identifier,
                    name=name,
                    adjective=adjective,
                ))

        scripted_names_setting_file.close()
        scripted_names_localization_file.close()
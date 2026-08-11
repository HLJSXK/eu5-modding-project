import yaml
from os import path
from templates.events.colonial_charter_finished import ColonialCharterFinishedTemplate

class ColonialCharterFinishedGenerator:
    def __init__(self, filepath: str):
        with open(filepath, encoding='utf-8-sig') as file:
            self.parsed: dict = yaml.safe_load(file)
            self.filename = path.basename(filepath)[:-4]
            if self.parsed: print('found unique colonial nations: ' + ', '.join(self.parsed.keys()))

    def get_unique_colonial_nations(self) -> list[str]:
        data = {"localization": [], "join_checks": [], "form_checks": []}
        if not self.parsed: return data

        for i, (tag, colony) in enumerate(self.parsed.items()):
            if not colony: continue
            name: str = colony.get('name')
            adjective: str = colony.get('adjective')
            geography_triggers: list[str] = colony.get('geography_triggers') or []
            overlord_triggers: list[str] = colony.get('overlord_triggers') or []

            if not name or not adjective or not geography_triggers: continue

            # join geo triggers into an `OR = {}`

            geography_triggers_joined = f"OR = {{ {' '.join(geography_triggers)} }}"
        
            print(f"adding unique colonial nation: {tag} ({name}, {adjective})")
            data["localization"].append(
                ColonialCharterFinishedTemplate.UNIQUE_COLONY_LOCALIZATION_TEMPLATE.format(
                    TAG = tag.strip(),
                    NAME = name.strip(),
                    ADJECTIVE = adjective.strip(),
                ).lstrip('\n').rstrip('\n')
            )
            data["join_checks"].append(
                ColonialCharterFinishedTemplate.UNIQUE_COLONY_JOIN_TEMPLATE.format(
                    IF_OR_ELSE_IF = 'if' if i == 0 else 'else_if',
                    TAG = tag.strip(),
                    TRIGGERS = ColonialCharterFinishedTemplate.JOIN_TRIGGERS_JOIN.join(\
                       [f'scope:target ?= {{ {geography_triggers_joined} }}']
                        + list(map(lambda t: f'scope:actor ?= {{ {t} }}', overlord_triggers))
                    ),
                ).lstrip('\n').rstrip('\n')
            )
            data["form_checks"].append(
                ColonialCharterFinishedTemplate.UNIQUE_COLONY_FORM_TEMPLATE.format(
                    IF_OR_ELSE_IF = 'if' if i == 0 else 'else_if',
                    TAG = tag.strip(),
                    TRIGGERS = ColonialCharterFinishedTemplate.FORM_TRIGGERS_JOIN.join(\
                        [f'capital ?= {{ {geography_triggers_joined} }}']
                        + list(map(lambda t: f'overlord ?= {{ {t} }}', overlord_triggers))
                    ),
                ).lstrip('\n').rstrip('\n')
            )
        return data

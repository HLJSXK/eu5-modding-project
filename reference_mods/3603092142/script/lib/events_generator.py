import yaml
from os import path
import re
from lib import DEFAULT_MONTHLY_CHANCE
from templates import *
from templates.take_location import TakeLocation
from templates.colonize_location import ColonizeLocation
from templates.colonize_province import ColonizeProvince
from templates.colonize_in_area import ColonizeInArea
from templates.colonize_in_region import ColonizeInRegion

class ColonyEventGenerator:
    def __init__(self, filepath: str):
        with open(filepath) as file:
            self.parsed: dict = yaml.safe_load(file)

            self.name = path.basename(filepath)[:-4]
            self.tags = self.parsed.get('tags') or []
    
    def write_events(self, event_out: str, file_data: list[dict[str, str]]):
        print(f'writing events...')
        # write events
        for data in file_data:
            if not data: continue
            with open(path.join(event_out, f'{data['namespace']}.txt'), 'w', encoding='utf-8-sig') as file:
                file.write(data['event'])

    def write_all(self, event_out: str | None = None, localization_out: str | None = None):
        file_data = []

        print(f'loading data for `{self.name}` using the following tags: {', '.join(self.tags)}...')

        if self.parsed.get('take'):
            take: dict[str, dict[str, str]] = self.parsed['take']
            if (locations := take.get('locations')):
                print(f'- take locations: {', '.join(locations)}')
                file_data.append(self._generate_files(TakeLocation, locations))

        if self.parsed.get('colonize'):
            colonize: dict[str, dict[str, str]] = self.parsed['colonize']
            if (locations := colonize.get('locations')):
                print(f'- colonize locations: {', '.join(locations)}')
                file_data.append(self._generate_files(ColonizeLocation, colonize.get('locations')))
            if (provinces := colonize.get('provinces')):
                print(f'- colonize provinces: {', '.join(provinces)}')
                file_data.append(self._generate_files(ColonizeProvince, provinces))
            if (areas := colonize.get('areas')):
                print(f'- colonize areas: {', '.join(areas)}')
                file_data.append(self._generate_files(ColonizeInArea, areas))
            if (regions := colonize.get('regions')):
                print(f'- colonize regions: {', '.join(regions)}')
                file_data.append(self._generate_files(ColonizeInRegion, regions))

        if event_out:
            self.write_events(event_out, file_data)
        if localization_out:
            self.write_localization(localization_out, file_data)
    
    def write_localization(self, localization_out: str, file_data: list[dict[str, str]]):
        # write localization
        lines = []
        with open(localization_out, 'r', encoding='utf-8-sig') as file:
            lines = file.read().split('\n')

            # add l_english if not present
            if len(lines) == 0:
                lines.append('l_english:')
            if len(lines) > 0 and 'l_english' not in lines[0]:
                lines.insert(0, 'l_english:')

            existing_loc_keys = [loc_line.split(':')[0].strip() for loc_line in lines[1:]]
            for data in file_data:
                if not data: continue
                for loc_line in data['localization'].split('\n'):
                    key = loc_line.split(':')[0].strip()
                    if (key not in existing_loc_keys):
                        lines.append(loc_line)
        
        if len(lines) > 0:
            with open(localization_out, 'w', encoding='utf-8-sig') as file:
                for line in lines:
                    if len(line) > 0:
                        file.write(line+'\n')

    def _parse_year(self, year: str | int) -> tuple[int, int, int]:
        '''
        Parse year with a Regex. Allowed formats:
            `1500`: ends in 1836, 10% chance each month
            `1500-1520`: ends in 1520, 10% chance each month
            `1500, 50`: ends in 1836, 50% chance each month
            `1444-1800, 1`: ends in 1800, 1% chance each month

            :return: 3-value tuple of start_year, end_year, chance
        '''
        if (r := re.match(r'(\d{4})(?:-(\d{4}))?(?:, ([1-9][0-9]?))?', str(year))):
            return (
                int(r.group(1)),
                int(r.group(2) or 1836),
                int(r.group(3) or DEFAULT_MONTHLY_CHANCE)
            )
        return (1337, 1836, DEFAULT_MONTHLY_CHANCE)

    def _generate_files(self, template: type[TemplateData], geo: dict[str, str] | None) -> dict[str, str]:  
        if not geo or len(geo) == 0: return {}
        namespace = template.NAMESPACE.format(name=self.name)

        data = {
            'localization': '',
            'namespace': namespace,
            'event': f'namespace = {namespace}\n\n',
        }
        for index, (geography, year) in enumerate(geo.items()):
            from_year, to_year, chance = self._parse_year(year)
            data['localization'] += template.LOCALIZATION_TEMPLATE.format(
                n = index+1,
                name = self.name.strip()
            )
            data['event'] += template.EVENT_TEMPLATE.format(
                tags = make_tags(self.tags),
                name = self.name.strip(),
                n = index+1,
                from_year = from_year,
                to_year = to_year,
                chance = chance,
                once = 'yes' if len(self.tags) < 3 else 'no',
                geography = geography.strip()
            )
        return data
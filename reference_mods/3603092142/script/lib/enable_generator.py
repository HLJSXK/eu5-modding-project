import yaml
from os import path
from templates import *
from templates.colonize_enabled import ColonizeEnabled

def get_geography(s: str) -> str:
    if s.endswith('_sub_continent'):
        return s[:-14]
    if s.endswith('_continent'):
        return s[:-10]
    return s

def get_geography_select(s: str) -> str:
    if s.endswith('_province'):
        return 'this'
    if s.endswith('_area'):
        return 'area'
    if s.endswith('_region'):
        return 'region'
    if s.endswith('_sub_continent'):
        return 'sub_continent'
    return 'continent'

def get_geography_type(s: str) -> str:
    if s.endswith('_province'):
        return 'province_definition'
    if s.endswith('_area'):
        return 'area'
    if s.endswith('_region'):
        return 'region'
    if s.endswith('_sub_continent'):
        return 'sub_continent'
    return 'continent'

class CharterFilterGenerator:
    def __init__(self, filepath: str):
        with open(filepath) as file:
            self.parsed: dict = yaml.safe_load(file)
            self.name = path.basename(filepath)[:-4]

    def get_enabled_filter(self):
        year_filters = []
        print(f'loading enable data for `{self.name}`...')

        if self.parsed.get('charters'):
            charters: dict[int, list[str]] = self.parsed['charters']
            if not charters or len(charters) == 0: return ''
            for year, geographies in charters.items():
                geo_filters = []
                for geography in geographies:
                    geo_filters.append(ColonizeEnabled.GEO_TEMPLATE.format(
                        select = get_geography_select(geography),
                        type = get_geography_type(geography),
                        identifier = get_geography(geography),
                    ))
                year_filters.append(ColonizeEnabled.FILTER_TEMPLATE.format(
                    year = year,
                    geo_filters = ''.join(geo_filters).rstrip()
                ))

        return ''.join(year_filters).rstrip()
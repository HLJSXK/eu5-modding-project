from dataclasses import dataclass

@dataclass(frozen=True)
class ColonizeEnabled:
    GEO_TEMPLATE = '''{select} = {type}:{identifier}
                                '''
    FILTER_TEMPLATE = '''trigger_else_if = {{
                        limit = {{
                            or = {{
                                {geo_filters}
                            }}
                        }}
                        current_year > {year}
                    }}
                    '''

    # GEO_FILTER_TEMPLATE = '''and = {{
    #                         current_year > {year}
    #                         {geography_select} = {geography_type}:{geography}
    #                     }}
    #                     '''
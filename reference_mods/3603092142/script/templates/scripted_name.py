from dataclasses import dataclass

@dataclass(frozen=True)
class ScriptedNames():
    SCRIPTED_TEMPLATE = '''{identifier}_scripted_country_name = {{
    country_trigger = {{
        {country_trigger}
    }}
    
    capital_trigger = {{ region = region:{region} }}
    
    location_trigger = {{}}
}}
'''

    LOCALIZATION_TEMPLATE = '''
  {identifier}_scripted_country_name: "{name}"
  {identifier}_scripted_country_name_ADJ: "{adjective}"'''
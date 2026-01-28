from dataclasses import dataclass
from templates import TemplateData

@dataclass(frozen=True)
class ColonizeLocation(TemplateData):
	NAMESPACE = 'htc_colonize_location_{name}'

	LOCALIZATION_TEMPLATE = '''
  htc_colonize_location_{name}.{n}.title: ""
  htc_colonize_location_{name}.{n}.desc: ""
'''[1:]

	EVENT_TEMPLATE = '''htc_colonize_location_{name}.{n} = {{
	type = country_event
	title = htc_colonize_location.title
	desc = htc_colonize_location.desc
	fire_only_once = {once}
	
	dynamic_historical_event = {{
{tags}
		from = {from_year}.1.1
		to = {to_year}.1.1
		monthly_chance = {chance}
	}}

	illustration_tags = {{
		10 = happy
		10 = exterior
	}}

	trigger = {{
		monthly_balance > 25
		location:{geography} = {{
			has_owner = no
			is_ownable = yes
			within_colonial_range_of = root
			is_discovered_by = root
		}}
	}}		

	immediate = {{
		location:{geography} = {{
			save_scope_as = geo
		}}
	}}
	

	option = {{
		name = htc.options.take
		historical_option = yes
		
		add_gold = {{
			value = -50
			add = {{
				value = location:{geography}.development
				multiply = -10
			}}
		}}
		
		location:{geography} = {{
			change_location_owner = root
			change_integration_level = colonized
		}}
	}}
	option = {{
		name = htc.options.no
	}}
}}
'''
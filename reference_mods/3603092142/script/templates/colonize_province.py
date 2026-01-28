from dataclasses import dataclass
from templates import TemplateData

@dataclass(frozen=True)
class ColonizeProvince(TemplateData):
	NAMESPACE = 'htc_colonize_province_{name}'
	
	LOCALIZATION_TEMPLATE = '''
  htc_colonize_province_{name}.{n}.title: ""
  htc_colonize_province_{name}.{n}.desc: ""
'''[1:]

	EVENT_TEMPLATE = '''htc_colonize_province_{name}.{n} = {{
	type = country_event
	title = htc_colonize_province.title
	desc = htc_colonize_province.desc
	fire_only_once = yes
	
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
		is_ai = yes
		monthly_balance > 25
		province_definition:{geography} = {{
			not = {{
				any_location_in_province_definition = {{
					has_owner = yes
					owner = {{ is_ai = no }}
				}}
			}}
			any_location_in_province_definition = {{
				or = {{
					is_adjacent_to_owned_or_subject_owns = yes
					within_colonial_range_of = root
				}}
				has_owner = no
				is_ownable = yes
				is_discovered_by = root
			}}
			not = {{ has_colonial_charter = root }}
		}}
	}}

	immediate = {{
		province_definition:{geography} = {{
			save_scope_as = geo
		}}
	}}
	

	option = {{
		name = htc.options.take
		historical_option = yes

		create_colonial_charter = {{
			target = province_definition:{geography}
		}}
	}}
	option = {{
		name = htc.options.no
	}}
}}
'''
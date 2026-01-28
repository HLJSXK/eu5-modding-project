from dataclasses import dataclass
from templates import TemplateData

@dataclass(frozen=True)
class ColonizeInArea(TemplateData):
	NAMESPACE = 'htc_colonize_in_area_{name}'

	LOCALIZATION_TEMPLATE = '''
  htc_colonize_in_area_{name}.{n}.title: ""
  htc_colonize_in_area_{name}.{n}.desc: ""
'''[1:]

	EVENT_TEMPLATE = '''htc_colonize_in_area_{name}.{n} = {{
	type = country_event
	title = htc_colonize_in_area.title
	desc = htc_colonize_in_area.desc
	fire_only_once = no
	
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
		area:{geography} = {{
			any_province_definition_in_area = {{
				not = {{ has_colonial_charter = root }}
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
			}}
		}}
	}}
	
	immediate = {{
		area:{geography} = {{
			save_scope_as = source
			random_province_definition_in_area = {{
				limit = {{
					not = {{ has_colonial_charter = root }}
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
				}}
				save_scope_as = geo
			}}
		}}
	}}

	option = {{
		name = htc.options.take
		historical_option = yes

		create_colonial_charter = {{
			target = scope:geo
		}}
	}}
	option = {{
		name = htc.options.no
	}}
}}
'''
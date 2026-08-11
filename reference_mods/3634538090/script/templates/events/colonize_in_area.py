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

	illustration_tags = {{
		10 = happy
		10 = exterior
	}}

	trigger = {{
		OR = {{
{tags}
		}}
		current_date > {from_year}.1.1
		current_date < {to_year}.1.1
		is_ai = yes
		monthly_balance > 50
		num_colonial_charters <= 5
		area:{geography} = {{
			any_province_definition_in_area = {{
				not = {{ has_colonial_charter = root }}
				not = {{
					any_location_in_province_definition = {{
						or = {{
							# prevent colonization if either:
							# owner is a player, owner is a colonial nation, owner is european, doesn't have owner
							owner ?= {{ is_ai = no }}
							owner ?= {{ is_colonial_subject = yes }}
							owner ?= {{ capital ?= {{ continent = continent:europe }} }}
						}}
					}}
				}}
				any_location_in_province_definition = {{
					or = {{
						within_colonial_range_of = root
						any_neighbor_location = {{
							OR = {{
								owner ?= root
								owner ?= {{
									exists = overlord
									overlord = root
								}}
							}}
						}}
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
							or = {{
								# prevent colonization if either:
								# owner is a player, owner is a colonial nation, owner is european, doesn't have owner
								owner ?= {{ is_ai = no }}
								owner ?= {{ is_colonial_subject = yes }}
								owner ?= {{ capital ?= {{ continent = continent:europe }} }}
							}}
						}}
					}}
					any_location_in_province_definition = {{
						or = {{
							within_colonial_range_of = root
							any_neighbor_location = {{
								OR = {{
									owner ?= root
									owner ?= {{
										exists = overlord
										overlord = root
									}}
								}}
							}}
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
		ai_will_do = 1000

		create_colonial_charter = {{
			target = scope:geo
		}}
	}}
	option = {{
		name = htc.options.no
	}}
}}
'''
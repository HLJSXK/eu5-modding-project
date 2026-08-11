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
		province_definition:{geography} = {{
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
		ai_will_do = 1000

		create_colonial_charter = {{
			target = province_definition:{geography}
		}}
	}}
	option = {{
		name = htc.options.no
	}}
}}
'''
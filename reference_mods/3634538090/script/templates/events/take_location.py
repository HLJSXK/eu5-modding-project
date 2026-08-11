from dataclasses import dataclass
from templates import TemplateData

@dataclass(frozen=True)
class TakeLocation(TemplateData):
	NAMESPACE = 'htc_take_location_{name}'

	LOCALIZATION_TEMPLATE = '''
  htc_take_location_{name}.{n}.title: ""
  htc_take_location_{name}.{n}.desc: ""
'''[1:]

	EVENT_TEMPLATE = '''htc_take_location_{name}.{n} = {{
	type = country_event
	title = htc_take_location.title
	desc = htc_take_location.desc

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
		location:{geography} = {{
			has_owner = yes
			is_ownable = yes
			within_colonial_range_of = root
			is_discovered_by = root
			owner ?= {{ is_ai = yes }}
		}}
	}}		

	immediate = {{
		location:{geography} = {{
			save_scope_as = geo
			owner = {{ save_scope_as = prev_owner }}
		}}
	}}
	
	option = {{
		name = htc.options.purchase

		location:{geography}.owner = {{
			add_gold = {{
				value = 50
				add = {{
					value = location:{geography}.development
					multiply = 35
				}}
			}}
		}}

		add_gold = {{
			value = 50
			add = {{
				value = location:{geography}.development
				multiply = 35
			}}
			multiply = -1
		}}

		location:{geography} = {{
			change_location_owner = root
		change_integration_level = integrated
		}}
	}}

	option = {{
		name = htc.options.take_for_guarantee
		historical_option = yes
		ai_will_do = 1000

		trigger = {{ great_power_score > scope:prev_owner.great_power_score }}

		create_relation = {{
			first = root
			second = scope:prev_owner
			type = relation_type:guarantee
		}}

		location:{geography} = {{
			change_location_owner = root
			change_integration_level = integrated
		}}
	}}

	option = {{
		name = htc.options.no
	}}
}}
'''
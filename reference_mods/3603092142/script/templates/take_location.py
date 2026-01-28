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
		location:{geography} = {{
			has_owner = yes
			is_ownable = yes
			within_colonial_range_of = root
			is_discovered_by = root
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

		add_gold = {{
			value = -50
			add = {{
				value = location:{geography}.development
				multiply = -35
			}}
		}}

		location:{geography} = {{
			change_location_owner = root
			change_integration_level = colonized
		}}
	}}

	option = {{
		name = htc.options.take_for_guarantee
		historical_option = yes

		trigger = {{ great_power_score > scope:prev_owner.great_power_score }}

		create_relation = {{
			first = root
			second = scope:prev_owner
			type = relation_type:guarantee
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
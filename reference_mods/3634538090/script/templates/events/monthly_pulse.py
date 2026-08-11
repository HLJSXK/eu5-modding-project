from dataclasses import dataclass

@dataclass(frozen=True)
class MonthlyPulseTemplate:
    TEMPLATE = '''
monthly_country_pulse = {{
    on_actions = {{
        htc_ai_monthly_colonize_pulse
	}}
}}

htc_ai_monthly_colonize_pulse = {{
    random_events = {{
{event_lines}
        chance_to_happen = 5
	}}
}}
'''
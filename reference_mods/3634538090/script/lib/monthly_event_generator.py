from templates.events.monthly_pulse import MonthlyPulseTemplate

class MonthlyPulseGenerator:
    events: list[str] = list()
    def __init__(self, events: list[str]):
        self.events = events.copy()
    
    def write_on_action(self, file_out: str):
        print(f'writing monthly pulse...')
        with open(file_out, 'w', encoding='utf-8-sig') as file:
            tabs = ' '*4*2
            event_lines = '\n'.join(tabs + '10 = ' + event for event in self.events)
            file.write(
                MonthlyPulseTemplate.TEMPLATE.format(
                    event_lines = event_lines
                )
            )

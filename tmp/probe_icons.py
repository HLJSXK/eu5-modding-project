import sys
sys.path.insert(0, 'ai_gui_assessment/renderer')
import scenarios
from run import setup

db, ex, ev, eng, log = setup(scenarios.ui_library('cards', {'ui_library_cards_tabs': 'cards1'}))
body = db.types['ExtraContentTooltipType']
el = ex.build('ExtraContentTooltipType', body, {}, 'x', 0)
eng.place(el, 0, 0, 470, 383)

def walk(x):
    yield x
    for c in x.children:
        yield from walk(c)

for x in walk(el):
    if x.kind == 'icon' and 'click' in str(x.props.get('texture')):
        print(x.props.get('texture'), x.props.get('visible'), x.x, x.y, x.w, x.h, eng.visible(x))
print('measure', eng.measure(el, None), 'log', log[-20:])

path = next(p for p in db.roots if p.replace('\\', '/').endswith('in_game/gui/ui_library.gui'))
root = next(n for n in db.roots[path] if n.key == 'window')
whole = ex.build(root.key, root.value, {}, path, root.line)
eng.place(whole, 0, 0, 1920, 1080)
for x in walk(whole):
    if x.typename in ('TooltipFunctionalBlock', 'TooltipUIActionBlock', 'ExtraContentTooltipType'):
        print('WHOLE', x.typename, x.x, x.y, x.w, x.h, eng.visible(x), x.props.get('visible'))

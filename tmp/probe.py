import sys
sys.path.insert(0, 'ai_gui_assessment/renderer')
import scenarios
from run import setup, find_root

names = [
    ('in_game/gui/eventwindow.gui', 'AgeEventWindow'),
    ('in_game/gui/selected_market_view.gui', 'lateralview'),
    ('in_game/gui/government_lateralview.gui', 'lateralview'),
    ('in_game/gui/battle_lateralview.gui', 'lateralview'),
]
db, ex, ev, eng, log = setup(scenarios.situation())

def walk(el):
    yield el
    for c in el.children:
        yield from walk(c)

for suffix, key in names:
    path, node = find_root(db, suffix, key)
    el = ex.build(node.key, node.value, {}, path, node.line)
    print('\n===', suffix, key, '===')
    for x in walk(el):
        if x.props.get('datamodel') or x.props.get('datacontexts') or x.props.get('text') or x.props.get('raw_text'):
            print(x.kind, x.typename, 'dm=', x.props.get('datamodel'), 'dc=', x.props.get('datacontexts'), 'text=', x.props.get('text') or x.props.get('raw_text'))

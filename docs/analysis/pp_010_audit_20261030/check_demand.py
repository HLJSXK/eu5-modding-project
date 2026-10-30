"""Offline demand reconciliation; no game or mod output writes."""
from pathlib import Path
from decimal import Decimal
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import gen_sol_mnt_compat as mnt
import gen_sol_pp_compat as pp
from test_sol_slave_demand import inject

NEW = ROOT.parent / 'prosper-or-perish-upstream/mod/Prosper or Perish (Population Growth & Food Rework)'
VANILLA = ROOT / '.eu5-base/reference_game_files/game/in_game/common/goods'
def resolve(mod):
    files = {p.name: p for p in VANILLA.glob('*.txt')}
    files.update({p.name: p for p in (mod / 'in_game/common/goods').glob('*.txt')})
    blocks = [b for name,p in sorted(files.items()) for b in mnt._blocks_in_file(p)]
    goods = {b.key: mnt._final_pop_demand(b.body) for b in blocks if not b.operation}
    inject(goods, [b for b in blocks if b.operation in ('INJECT','TRY_INJECT')])
    inject(goods, mnt._blocks_in_tree(pp.STABLE_ROOT / 'in_game/common/goods'))
    inject(goods, mnt._blocks_in_tree(pp.TARGET_ROOT / 'in_game/common/goods'))
    return goods
old, new = resolve(pp.PP_ROOT), resolve(NEW)
differences = {g: {pt: {'old': old.get(g,{}).get(pt), 'new': vals[pt]} for pt in mnt.ALL_POP_TYPES
                   if old.get(g,{}).get(pt,Decimal(0)) != vals[pt]}
               for g, vals in new.items()}
differences = {g:v for g,v in differences.items() if v}
baseline = pp._render_outputs()
pp.PP_ROOT = NEW
pp.PP_VICTUALS_FILE = NEW / 'in_game/common/goods/pp_goods_victuals.txt'
pp.PP_LUMBER_FILE = NEW / 'in_game/common/goods/pp_goods_adjustments.txt'
pp.PP_ROAD_PRICES = NEW / 'in_game/common/prices/pp_road_gold_adjustments.txt'
updated = pp._render_outputs()
render_diff = [str(p.relative_to(ROOT)) for p,v in updated.items() if v != baseline[p]]
result = {
  'scope': 'Per-good additive/multiply baselines only; excludes goods_demand template, climate, culture, religion, country modifiers and engine refresh.',
  'baseline_differences': differences,
  'new_nonzero_slave_baskets': {g:v['slaves'] for g,v in new.items() if v['slaves'] != 0},
  'lumber': new['lumber'], 'victuals': new['victuals'],
  'generator_outputs': len(updated), 'generator_outputs_changed_when_repointed': render_diff,
}
(OUT/'demand_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

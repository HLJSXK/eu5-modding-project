"""Count HUD-only script effects/conditions against the latest debug save."""
from collections import Counter
from copy import deepcopy
import argparse
import json
import mmap
import pickle
from pathlib import Path
import re
import hashlib
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'scripts/sol_lshud_income_source.py').is_file())
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from tools.eu5_save_parser import parser as sp
from test_sol_lshud_income import IncomeRuntime
from test_sol_lshud_ranking import RankingRuntime, Country
from test_sol_substitution import Scope, parse
from sol_lshud_income_source import ESTATES

SAVE_DIR = Path('C:/Users/Hades/Documents/Paradox Interactive/Europa Universalis V/save games')
cli = argparse.ArgumentParser(__doc__)
cli.add_argument('--save', type=Path, help='Pin the debug save; default is the most recently modified save')
args = cli.parse_args()
save = args.save or max(SAVE_DIR.glob('*.eu5'), key=lambda p: p.stat().st_mtime)
# Extend this analysis process's extractor only; do not change the shared parser.
sp._COUNTRY_SOL_VARIABLE_RE = re.compile(sp._COUNTRY_SOL_VARIABLE_RE.pattern.replace(
    b'sol_country_[^\\r\\n]+', b'sol_ls_[^\\r\\n]+|sol_sub_[^\\r\\n]+|sol_country_[^\\r\\n]+'))
cache = ROOT / 'tmp/lshud_cost_parsed.pkl'
stamp = (str(save), save.stat().st_mtime_ns)
cached = pickle.loads(cache.read_bytes()) if cache.exists() else None
if cached and cached[0] == stamp:
    parsed = cached[1]
else:
    parsed = sp.parse_save(save)
    cache.write_bytes(pickle.dumps((stamp, parsed)))
print('[PARSED]', save.name, parsed.metadata, flush=True)
owners = {}
for cid, tag in parsed.country_tags.items():
    c = Country('country', variables=dict(parsed.country_variables.get(cid, {})), population=0)
    c.tag, c.cid = tag, cid
    owners[cid] = c
missing_income = 0
for loc in parsed.locations:
    if loc.owner_id not in owners:
        continue
    c = owners[loc.owner_id]
    pops = Counter()
    for pid in loc.pop_ids:
        p = parsed.populations[pid]
        pops[p.type] += p.size
    c.population += sum(pops.values())
    variables = dict(loc.sol_variables)
    missing_income += 'sol_location_total_income' not in variables
    for estate in ESTATES:
        variables.setdefault(f'sol_location_{estate}_net_income', 0)
    variables.setdefault('sol_location_total_income', 0)
    c.locations.append(Scope('location', owner=c, pops=dict(pops), variables=variables))

active = [c for c in owners.values() if c.locations and c.population > 0]
humans = [c for c in active if c.variables.get('sol_demand_snapshot_human') == 1]
if not humans:
    # Metadata player tag is preferable to assuming a particular country.
    tag = parsed.metadata.get('player') or parsed.metadata.get('player_country')
    humans = [c for c in active if c.tag == tag]
if not humans:
    raise RuntimeError('Could not identify a human from saved control snapshots/metadata')
ai = [c for c in active if c not in humans]
year, month, day = map(int, parsed.metadata['date'].split('.'))

class CountIncome(IncomeRuntime):
    def __init__(self):
        super().__init__()
        self.conditions = 0
        # Use shipped effects, rather than trusting just the emitter.
        shipped = ROOT / 'src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt'
        self.effects.update({n.key: n.value for n in parse(shipped.read_text(encoding='utf-8-sig')) if n.key.startswith('sol_ls_')})

    def test(self, node, scope):
        self.conditions += 1
        return super().test(node, scope)

    def value(self, node, scope, initial=0.):
        if node == 'local_sol_population_sum':
            return sum(scope.pops.get(key, 0) for key in sp.SOL_POP_TYPES)
        return super().value(node, scope, initial)

    def solve(self, c):
        # These new calls live inside pre-existing solver preparation loops.
        self.execute(parse('sol_ls_reset_country_income = yes'), c)
        for loc in c.locations:
            self.execute(parse('sol_ls_accumulate_country_income = yes'), loc)
        self.execute(parse('sol_ls_finalize_country_income = yes'), c)

class CountRanking(RankingRuntime):
    def __init__(self, countries):
        shipped = ROOT / 'src/stable/in_game/common/scripted_effects/D_SOL_lshud_ranking.txt'
        super().__init__(countries, shipped.read_text(encoding='utf-8-sig'))
        self.conditions = 0

    def test(self, node, scope):
        self.conditions += 1
        return super().test(node, scope)

def counts(rt):
    effect = sum(rt.operations.values())
    return dict(script_nodes=effect + rt.conditions, effects=effect,
                conditions=rt.conditions, operations=dict(rt.operations))

def measure_income(countries, scenario):
    rt = CountIncome()
    rt.year, rt.month, rt.day = year, month, day
    for original in countries:
        c = deepcopy(original)
        if scenario == 'first':
            c.variables = {k:v for k,v in c.variables.items() if not k.startswith('sol_ls_')}
        elif scenario in ('mature', 'mature_repeated'):
            for metric in ('all', *ESTATES):
                value = c.variables.get(f'sol_ls_current_pci_{metric}', 0)
                c.variables[f'sol_ls_sample_{month}_{metric}'] = value
                c.variables[f'sol_ls_sample_{month}_previous_{metric}'] = value
            c.variables.update({f'sol_ls_sample_{month}_year': year if scenario == 'mature_repeated' else year - 1,
                                f'sol_ls_sample_{month}_day': day,
                                f'sol_ls_sample_{month}_previous_year': year - 1,
                                f'sol_ls_sample_{month}_previous_day': day})
        rt.solve(c)
    return counts(rt)

report = {
    'save': str(save), 'save_date': parsed.metadata['date'],
    'unit': 'One executed non-branch effect node or visited condition node. Includes helper calls and scope switches; excludes branch dispatch, RHS arithmetic/getter internals and GUI frame evaluation. Existing solver iterators are not charged again.',
    'topology': dict(country_records=len(owners), active_countries=len(active),
                     locations=sum(len(c.locations) for c in active),
                     humans=[dict(tag=c.tag, locations=len(c.locations)) for c in humans],
                     ai_countries=len(ai), ai_locations=sum(len(c.locations) for c in ai),
                     missing_income_location_caches=missing_income,
                     countries_with_current_pci=sum('sol_ls_pci' in c.variables for c in active),
                     countries_with_yoy=sum('sol_ls_pci_yoy' in c.variables for c in active)),
    'income': {},
    'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        'src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt',
        'src/stable/in_game/common/scripted_effects/D_SOL_lshud_ranking.txt')},
}
for group, countries in (('human', humans), ('ai_annual_total', ai), ('world', active)):
    report['income'][group] = {}
    for state in ('saved', 'first', 'mature', 'mature_repeated'):
        report['income'][group][state] = measure_income(countries, state)
        print('[COUNT]', group, state, report['income'][group][state]['script_nodes'], flush=True)

# Ranking can use the saved state or the caches produced by current initialization.
def ranking(countries):
    rt = CountRanking(countries)
    rt.execute(parse('sol_ls_recalculate_world_ranking = yes'), Scope('global'))
    return {**counts(rt), 'ranked_countries': rt.globals['sol_ls_rank_count'],
            'visits': dict(rt.visits)}
report['ranking_saved'] = ranking(deepcopy(list(owners.values())))
initialized = deepcopy(list(owners.values()))
rt = CountIncome()
rt.year, rt.month, rt.day = year, month, day
for c in initialized:
    if c.locations and c.population > 0:
        rt.solve(c)
report['ranking_initialized'] = ranking(initialized)
report['ranking_active_only_sensitivity'] = ranking([c for c in initialized if c.locations and c.population > 0])
report['initialization_first_sample'] = report['income']['world']['first']['script_nodes'] + report['ranking_initialized']['script_nodes']
report['global_refresh_saved'] = report['income']['world']['saved']['script_nodes'] + report['ranking_initialized']['script_nodes']
for state in ('saved', 'first', 'mature', 'mature_repeated'):
    h = report['income']['human'][state]['script_nodes']
    a = report['income']['ai_annual_total'][state]['script_nodes']
    r = report['ranking_initialized']['script_nodes']
    report.setdefault('monthly', {})[state] = dict(
        human=h, ai_anniversary_month_average=a/12,
        regular_month_average=h+a/12+1,
        january_average=h+a/12+1+r,
        annualized_average=h+a/12+1+r/12,
        all_ai_monthly=h+a+1+r/12)

with save.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
    # Native pulse dates, if serialized, allow a calendar distribution instead
    # of assuming every AI's annual work lands on January 1.
    bounds = sp._top_level_bounds(view, 'countries')
    records = list(sp._COUNTRY_RECORD_RE.finditer(view, *bounds))
    pulse_fields = Counter()
    for i, match in enumerate(records):
        end = records[i+1].start() if i+1 < len(records) else bounds[1]
        for m in re.finditer(rb'(?m)^\t([^=\r\n]*(?:pulse|anniversary|birth|creat)[^=\r\n]*)=([^\r\n]+)', view[match.start():end]):
            pulse_fields[m.group(1).decode()] += 1
    report['country_pulse_related_fields'] = dict(pulse_fields)
    # Record global toggle evidence without inferring CPU timing from it.
    marker = b'flag=sol_ai_reduced_freq_enabled'
    report['reduced_frequency_global_flag_present'] = view.find(marker) >= 0
    flag = re.search(rb'flag=sol_ai_reduced_freq_enabled\s+data=\{\s+type=boolean\s+identity=(\d+)', view)
    report['reduced_frequency_global_value'] = int(flag.group(1)) if flag else None

report['assumptions'] = [
    'AI reduced-frequency setting is read from the save; primary monthly projection assumes one AI solve per year and monthly human solves.',
    'Monthly AI figures divide annual work by twelve. Native pulse dates were not found; no exact calendar-month distribution is claimed.',
    'Saved scenario executes each country once at the saved date. Maturity scenarios reuse saved population/income topology; these are scale estimates, not forecasts.',
    'Ranking is bracketed between populated territorial countries and all saved country records; native live/dead filtering is not reproduced.',
    'Native sorting/comparisons, getter/expression internals, GUI frame/hover work and fixed-point timing are excluded.',
]
h = report['income']['human']['saved']['script_nodes']
a = report['income']['ai_annual_total']['saved']['script_nodes'] / 12
lo = report['ranking_active_only_sensitivity']['script_nodes']
hi = report['ranking_initialized']['script_nodes']
report['headline'] = dict(ordinary_month_mean=h+a+1, ranking_annual_range=[lo, hi],
    january_with_mean_ai_work_range=[h+a+1+lo, h+a+1+hi],
    annualized_month_mean_range=[h+a+1+lo/12, h+a+1+hi/12])

out = ROOT / 'docs/analysis/sol_topbar_cost_20261018'
out.mkdir(parents=True, exist_ok=True)
(out / 'counts.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('income',)}, ensure_ascii=False, indent=2))

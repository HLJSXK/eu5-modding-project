"""Compare executed substitution operations; these are not EU5 CPU timings."""
import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gen_market_unit_consumption import _load_good_rows
from sol_substitution import CORE, POPS
from test_sol_substitution import Runtime, Scope, parse

ROOT = Path(__file__).resolve().parent.parent
VAR_OPS = {'set_variable', 'change_variable', 'remove_variable',
           'set_local_variable', 'change_local_variable', 'remove_local_variable'}


class CountingRuntime(Runtime):
    def __init__(self, rows, source=None):
        super().__init__(rows)
        if source is not None:
            # The old name= field failed engine validation. Normalize it solely
            # to count the old intended effects, as the previous offline audit did.
            source = source.replace('add_country_modifier = { name = sol_substitute_',
                                    'add_country_modifier = { modifier = sol_substitute_')
            self.effects = {n.key: n.value for n in parse(source.lstrip('\ufeff'))}
            # Historical fixtures used static grants rather than cached autos.
            if 'sol_apply_country_substitution' in self.effects:
                self.auto_modifiers = {}
        self.reads = Counter()
        self.conditions = 0
        self.modifier_total_reads = 0
        self.modifier_strength_reads = 0

    def value(self, node, scope, initial=0.):
        if isinstance(node, str) and node.startswith('modifier:global_'):
            self.modifier_total_reads += 1
        if isinstance(node, str) and node.startswith('country_modifier_strength('):
            self.modifier_strength_reads += 1
        if isinstance(node, str) and node.startswith('global_variable_map('):
            name = node.split('(', 1)[1].split('|', 1)[0]
            self.reads['goods' if name.startswith('sol_market_good_spending_') else
                       'totals' if name.startswith('sol_country_market_spending_') and not name.endswith('_owner')
                       else 'other'] += 1
        return super().value(node, scope, initial)

    def test(self, node, scope):
        self.conditions += 1
        return super().test(node, scope)

    def measure(self, effect, scopes):
        self.operations.clear()
        self.reads.clear()
        self.conditions = 0
        self.modifier_total_reads = 0
        self.modifier_strength_reads = 0
        for scope in scopes:
            self.run(effect, scope)
        return {'variable_operations': sum(self.operations[k] for k in VAR_OPS),
                'condition_evaluations': self.conditions, 'map_reads': dict(self.reads),
                'map_writes': self.operations['add_to_global_variable_map'] + self.operations['remove_from_global_variable_map'],
                'modifier_adds': self.operations['add_country_modifier'],
                'modifier_removes': self.operations['remove_country_modifier'],
                'modifier_total_reads': self.modifier_total_reads,
                'modifier_strength_reads': self.modifier_strength_reads}


def scenario(source, locations, market_count, nonneutral=False):
    rows = _load_good_rows()
    rt = CountingRuntime(rows, source)
    country = Scope('country', human=False)
    weights = dict.fromkeys(CORE, 1.)
    if nonneutral:
        weights.update(cloth=.5, fish=1.5, lumber=.25, wine=2.)
    markets = [rt.market(weights) for _ in range(market_count)]
    for market in markets:
        for good, price, quantities in rows:
            for pop in POPS:
                if round(quantities[pop], 5) > 0:
                    rt.maps[(f'sol_market_good_spending_{pop}_{good}', id(market))] = round(quantities[pop], 5) * price
    country.locations = [Scope('location', owner=country, market=markets[i % market_count],
                               pops=dict.fromkeys(POPS, 10.)) for i in range(locations)]
    report = {'refresh': rt.measure('sol_refresh_country_substitution', [country]),
              'all_location_spending': rt.measure('sol_compute_substitute_unit_spending', country.locations),
              'unchanged_refresh': rt.measure('sol_refresh_country_substitution', [country])}
    for label, effect in (('clean_snapshot', 'sol_check_substitution_snapshot'),
                          ('unchanged_apply', 'sol_apply_country_substitution')):
        if effect in rt.effects:
            report[label] = rt.measure(effect, [country])
    return report


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--baseline', default='70561daf')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/technical/SOL_Monthly_Performance_Optimization_Counts_20261015.json')
    args = parser.parse_args()
    old = subprocess.run(['git', 'show', f'{args.baseline}:src/stable/in_game/common/scripted_effects/C_SOL_substitution.txt'],
                         cwd=ROOT, check=True, capture_output=True, encoding='utf-8').stdout
    report = {'baseline': args.baseline, 'measurement': 'executed offline operation counts, not game timings',
              'caveats': ['Python float arithmetic; EU5 intermediate fixed-point rounding is not emulated.',
                          'Baseline name= is normalized only to count intended old effects, despite its engine parse failure.',
                          'No country matrix, vertex sweep, engine demand recalculation, or monthly location modifier writes are counted.'],
              'scenarios': []}
    for locations, markets, nonneutral in ((1, 1, False), (10, 1, False), (180, 3, False), (180, 3, True)):
        entry = {'locations': locations, 'markets': markets, 'nonneutral': nonneutral,
                 'before': scenario(old, locations, markets, nonneutral),
                 'after': scenario(None, locations, markets, nonneutral)}
        report['scenarios'].append(entry)
        print(json.dumps(entry, ensure_ascii=False))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'[WRITE] {args.output}')


if __name__ == '__main__':
    main()

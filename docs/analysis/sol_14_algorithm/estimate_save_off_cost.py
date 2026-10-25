"""Counterfactual substitution-OFF operation estimates using actual HUN save topology."""
from pathlib import Path
from collections import Counter, defaultdict
import json
import mmap
import re
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from tools.eu5_save_parser.parser import parse_save, _top_level_bounds, decode_jomini_fixed_point
from report_sol_substitution_perf import read_snapshot
from measure_sol_substitution_performance import CountingRuntime, Scope, CORE, POPS, _load_good_rows, parse
from sol_substitution import market_details, map_write


def topology(path):
    parsed = parse_save(path)
    grouped = defaultdict(list)
    for loc in parsed.locations:
        if loc.owner_id in parsed.country_tags:
            grouped[loc.owner_id].append(loc)
    records = []
    for cid, locs in grouped.items():
        population = sum(parsed.populations[p].size for loc in locs for p in loc.pop_ids)
        variables = parsed.country_variables.get(cid, {})
        records.append({'id': cid, 'tag': parsed.country_tags[cid],
                        'locations': len(locs), 'markets': sorted({l.market_id for l in locs if l.market_id is not None}),
                        'locations_no_market': sum(l.market_id is None for l in locs),
                        'population': population, 'human_snapshot': variables.get('sol_demand_snapshot_human'),
                        'snapshot_locations': variables.get('sol_demand_snapshot_locations'),
                        'strategy': variables.get('sol_country_demand_selected_strategy'),
                        'location_market_ids': [[l.id, l.market_id] for l in locs]})
    summary = {'save': path.name, 'date': parsed.metadata.get('date'), 'diagnostics': dict(parsed.diagnostics),
               'country_records': len(parsed.country_tags), 'owned_country_count': len(records),
               'active_country_count': sum(c['population'] > 0 for c in records),
               'owned_locations': sum(c['locations'] for c in records),
               'active_locations': sum(c['locations'] for c in records if c['population'] > 0),
               'country_market_pairs': sum(len(c['markets']) for c in records if c['population'] > 0),
               'hun': next({k:v for k,v in c.items() if k != 'location_market_ids'} for c in records if c['tag']=='HUN'),
               'control_counts': dict(Counter(str(c['human_snapshot']) for c in records if c['population']>0)),
               'snapshot_location_mismatches': [{'id':c['id'],'tag':c['tag'],'live':c['locations'],'cached':c['snapshot_locations']} for c in records if c['population']>0 and c['locations']!=c['snapshot_locations']]}
    return summary, records


def load_world_maps(path):
    with path.open('rb') as stream, mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as view:
        a,b=_top_level_bounds(view,'variables')
        blob=view[a:b]
    headers=list(re.finditer(rb'name="([^"]+)"',blob))
    pair=re.compile(rb'key=\{\s*type=mark\s*(?:identity=(\d+)\s*)?\}\s*value=\{\s*type=value\s*(?:identity=(\d+)\s*)?\}')
    maps={}
    for i,h in enumerate(headers):
        name=h.group(1).decode()
        if not name.startswith(('sol_market_good_spending_','sol_market_unit_spending_','sol_market_substitute_cache','sol_market_substitute_weight_','sol_market_consumes_')):
            continue
        end=headers[i+1].start() if i+1<len(headers) else len(blob)
        maps[name]={int(m.group(1) or 0):decode_jomini_fixed_point(int(m.group(2) or 0)) for m in pair.finditer(blob,h.end(),end)}
    return maps


class NodeCounter(CountingRuntime):
    def measure(self,effect,scopes):
        result=super().measure(effect,scopes)
        result['effect_nodes']=sum(self.operations.values())
        result['script_nodes']=result['effect_nodes']+result['condition_evaluations']
        result['effect_breakdown']=dict(self.operations)
        return result


def make_runtime(n,m,human=False,world=None,location_markets=None):
    rows=_load_good_rows()
    rt=NodeCounter(rows)
    rt.enabled=False
    country=Scope('country',human=human)
    ids=sorted(set(location_markets)) if location_markets is not None else list(range(m))
    markets={mid:rt.market(dict.fromkeys(CORE,1.)) for mid in ids}
    for mid,market in markets.items():
        if world is not None:
            for name,mapping in world.items():
                if mid in mapping:
                    rt.maps[(name,id(market))]=mapping[mid]
        else:
            for good,price,q in rows:
                for pop in POPS:
                    if round(q[pop],5)>0:
                        rt.maps[(f'sol_market_good_spending_{pop}_{good}',id(market))]=round(q[pop],5)*price
            for pop in POPS:
                rt.maps[(f'sol_market_unit_spending_{pop}',id(market))]=sum(round(q[pop],5)*price for good,price,q in rows if round(q[pop],5)>0)
    sequence=location_markets if location_markets is not None else [ids[i%m] for i in range(n)]
    country.locations=[Scope('location',owner=country,market=markets[mid],pops={}) for mid in sequence]
    return rt,country


def legacy_spending():
    text=subprocess.run(['git','show','f9bee41d:src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt'],cwd=ROOT,check=True,capture_output=True,encoding='utf-8').stdout
    body=next(n.value for n in parse(text.lstrip(chr(65279))) if n.key=='sol_compute_location_pop_demand')
    cut=next(i for i,n in enumerate(body) if n.key=='set_variable' and any(v.key=='name' and v.value=='sol_location_nobles_income' for v in n.value))
    return body[:cut]


def measure_shape(n,m,human,old,world=None,location_markets=None):
    rt,country=make_runtime(n,m,human,world,location_markets)
    rt.run('sol_refresh_country_substitution',country)
    refresh=rt.measure('sol_refresh_country_substitution',[country])
    spending=rt.measure('sol_compute_substitute_unit_spending',country.locations)
    guard=rt.measure('sol_check_substitution_snapshot',[country])
    assert country.variables['sol_substitute_dirty']==0
    rt.effects['legacy_spending']=old
    legacy=rt.measure('legacy_spending',country.locations)
    return {'refresh':refresh,'spending':spending,'guard':guard,'legacy':legacy}


def calibrate():
    old=legacy_spending()
    results=[]
    for n,m,human in [(1,1,False),(2,1,False),(2,2,False),(17,3,False),(189,4,True)]:
        result=measure_shape(n,m,human,old)
        results.append({'n':n,'m':m,'human':human,'counts':result})
        print(json.dumps({'n':n,'m':m,'human':human,'counts':{k:{a:b for a,b in v.items() if a!='effect_breakdown'} for k,v in result.items()}},ensure_ascii=False),flush=True)
    (OUT/'off_cost_calibration.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


def predicted(n,m,human=False):
    return {
        'refresh':{'variable_operations':1381+6*n+2*int(human),'condition_evaluations':349+2*n+5*m,
                   'effect_nodes':1389+8*n+12*m+2*int(human),'script_nodes':1738+10*n+17*m+2*int(human),
                   'modifier_total_reads':168,'map_writes':9*m},
        'spending':{'variable_operations':14*n+342*m,'condition_evaluations':7*n+541*m-1,
                    'effect_nodes':18*n+358*m,'script_nodes':25*n+899*m-1,'goods_reads':215*m,
                    'total_reads':7*n,'owner_reads':n-m,'map_writes':16*m},
        'guard':{'variable_operations':3,'condition_evaluations':584+17*n,'effect_nodes':5+2*n,
                 'script_nodes':589+19*n,'modifier_total_reads':56},
        'legacy':{'variable_operations':14*n,'condition_evaluations':21*n,'effect_nodes':16*n,'script_nodes':37*n}
    }


def estimate():
    topology_data=json.loads((OUT/'save_topology.json').read_text(encoding='utf-8'))
    calibration=json.loads((OUT/'off_cost_calibration.json').read_text(encoding='utf-8'))
    for fixture in calibration:
        model=predicted(fixture['n'],fixture['m'],fixture['human'])
        for phase in model:
            for key in ('variable_operations','condition_evaluations','effect_nodes','script_nodes'):
                assert model[phase][key]==fixture['counts'][phase][key],(fixture['n'],phase,key)
    old=legacy_spending()
    report={'date':'2026-10-15','baseline':'f9bee41d','current':'5bc51c51',
            'unit':'One executed non-branch effect node OR one visited condition node. Nested condition nodes count separately; if/else dispatch, arithmetic subexpressions, native getter/map internals are not independently charged. Getter and map tallies are supplementary, not added twice.',
            'scenario':'counterfactual substitution OFF, main SOL ON, AI reduced frequency ON, HUN sole human, initialized caches, steady totals; old ON-save dirty counts excluded',
            'excluded':'Unchanged raw/classifier/exact/sweep core; monthly location apply already in 1.3; GUI rendering; native engine costs; new on_action trigger/dispatch nodes; January market refresh; actual OFF-mode solver strategy and future dirty counts unknown.',
            'formulas':{'guard':'589+19N','off_refresh':'1738+10N+17M+2human','new_spending':'25N+899M-1','old_spending':'37N','solve_increment':'1737-2N+916M+2human'},'saves':[]}
    for item in topology_data:
        active=[c for c in item['countries'] if c['population']>0]
        ai=[c for c in active if c['tag']!='HUN']
        hun=next(c for c in active if c['tag']=='HUN')
        world=load_world_maps(ROOT/'data/saves'/item['summary']['save'])
        mids={m for c in active for m in c['markets']}
        missing_cache_markets=sorted(mids-set(world['sol_market_substitute_cache']))
        assert all(set(hun['markets']).issubset(set(v)) for k,v in world.items() if k.startswith(('sol_market_good_spending_','sol_market_unit_spending_','sol_market_substitute_cache')))
        live=measure_shape(hun['locations'],len(hun['markets']),True,old,world,[m for _,m in hun['location_market_ids']])
        p=predicted(hun['locations'],len(hun['markets']),True)
        for phase in p:
            for key in ('variable_operations','condition_evaluations','effect_nodes','script_nodes'):
                assert live[phase][key]==p[phase][key],(item['summary']['date'],phase,key)
        guard={key:sum(predicted(c['locations'],len(c['markets']))['guard'][key] for c in ai)
               for key in ('variable_operations','condition_evaluations','effect_nodes','script_nodes','modifier_total_reads')}
        hun_increment=p['refresh']['script_nodes']+p['spending']['script_nodes']-p['legacy']['script_nodes']
        annual_increment=sum(1737-2*c['locations']+916*len(c['markets']) for c in ai)
        entry={'date':item['summary']['date'],'save':item['summary']['save'],'active_ai':len(ai),'ai_locations':sum(c['locations'] for c in ai),
               'ai_country_market_pairs':sum(len(c['markets']) for c in ai),'world_market_cache_keys':len(world['sol_market_substitute_cache']),
               'ai_missing_control_snapshot':[c['tag'] for c in ai if c['human_snapshot'] is None],
               'missing_world_cache_markets':missing_cache_markets,
               'missing_market_cache_countries':[c['tag'] for c in ai if set(c['markets'])&set(missing_cache_markets)],
               'hun_locations':hun['locations'],'hun_markets':hun['markets'],'hun_market_location_counts':dict(Counter(m for _,m in hun['location_market_ids'])),
               'ai_clean_guard':guard,'hun_counts_from_saved_maps':live,'hun_monthly_increment_nodes':hun_increment,
               'quiet_month_increment_nodes':guard['script_nodes']+hun_increment,
               'ai_annual_solve_added_nodes_per_year':annual_increment,'ai_annual_solve_added_nodes_monthly_average':annual_increment/12,
               'quiet_plus_amortized_anniversaries_increment_nodes':guard['script_nodes']+hun_increment+annual_increment/12,
               'existing_monthly_location_modifier_writes':sum(c['locations'] for c in active)}
        report['saves'].append(entry)
    changes=[]
    for first,last in zip(topology_data,topology_data[1:]):
        a={c['id']:c for c in first['countries'] if c['population']>0 and c['tag']!='HUN'}
        b={c['id']:c for c in last['countries'] if c['population']>0 and c['tag']!='HUN'}
        modified=[]
        for cid in a.keys()&b.keys():
            x,y=a[cid],b[cid]
            if x['tag']!=y['tag']:continue
            old_locations=dict(x['location_market_ids']);new_locations=dict(y['location_market_ids'])
            territory=old_locations.keys()!=new_locations.keys()
            market=any(old_locations[k]!=new_locations[k] for k in old_locations.keys()&new_locations.keys())
            if territory or market:
                n,m=y['locations'],len(y['markets'])
                model=predicted(n,m)
                modified.append({'id':cid,'tag':y['tag'],'locations':n,'markets':m,'territory_changed':territory,'market_changed':market,
                                 'off_framework_and_spending_nodes':model['refresh']['script_nodes']+model['spending']['script_nodes']})
        changes.append({'from':first['summary']['date'],'to':last['summary']['date'],'changed_common_ai':len(modified),
                        'territory_changed':sum(c['territory_changed'] for c in modified),'market_changed':sum(c['market_changed'] for c in modified),
                        'new_owned_ai':len(b.keys()-a.keys()),'locations':sum(c['locations'] for c in modified),
                        'eligible_large_countries':sum(c['locations']>=5 for c in modified),
                        'one_refresh_each_off_framework_and_spending_nodes':sum(c['off_framework_and_spending_nodes'] for c in modified),
                        'warning':'Topology changes in ON history, NOT measured OFF dirty events. Hypothetical one extra solve per changed common AI. Includes new OFF framework+spending but excludes old raw/classification/solver core. Anniversary overlap, timing, temporary changes and economic divergence unresolved.',
                        'countries':modified})
    report['topology_change_scenarios']=changes
    (OUT/'save_off_cost_estimate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'saves':[{k:v for k,v in s.items() if k!='hun_counts_from_saved_maps'} for s in report['saves']],
                      'changes':[{k:v for k,v in x.items() if k!='countries'} for x in changes]},ensure_ascii=False,indent=2),flush=True)


def world_increment():
    path=next((ROOT/'data/saves').glob('*07_15*'))
    world=load_world_maps(path)
    rows=_load_good_rows()
    rt=NodeCounter(rows)
    lines=['remove_from_global_variable_map = { name = sol_country_market_spending_owner key = scope:sol_market_cache }']
    for good,price,q in rows:
        pops=[p for p in POPS if round(q[p],5)>0]
        lines.extend(market_details(good,pops))
    lines.extend(map_write('sol_market_substitute_cache','1'))
    rt.effects['added_market_block']=parse(chr(10).join(lines))
    # A ratio inside the recorded tier selects exactly the same price-weight branches.
    ratios={0.25:2.4,0.5:2,0.75:1.5,1:1,1.25:.75,1.5:.5,2:.3}
    counts=[]
    for mid in sorted(world['sol_market_substitute_cache']):
        m=Scope('market');rt.saved['sol_market_cache']=m
        for good,price,q in rows:
            rt.local_context['sol_market_actual_price_'+good]=price*ratios[world['sol_market_substitute_weight_'+good][mid]]
            rt.local_context['sol_market_effective_price_'+good]=price
            rt.local_context['sol_market_consumes_'+good+'_count']=world['sol_market_consumes_'+good][mid]
        counts.append(rt.measure('added_market_block',[m]))
    keys=('script_nodes','effect_nodes','condition_evaluations','variable_operations','map_writes')
    result={'basis':'123 cached markets in July save. Replays only extra market_details, owner invalidation and substitute-cache writes, using SAVED price-weight tiers and supply eligibility; values representative within tiers, not forecast live prices. Excludes old cache, new camels base-accounting and global initialization marker.',
            'market_count':len(counts),'per_world_refresh':{k:sum(x[k] for x in counts) for k in keys}}
    result['amortized_per_month_nodes']=result['per_world_refresh']['script_nodes']/12
    (OUT/'world_cache_added_counts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    if '--world' in sys.argv:
        world_increment()
        sys.exit(0)
    if '--estimate' in sys.argv:
        estimate()
        sys.exit(0)
    if '--calibrate' in sys.argv:
        calibrate()
        sys.exit(0)
    if '--maps' in sys.argv:
        maps=load_world_maps(next((ROOT/'data/saves').glob('*07_15*')))
        print(json.dumps({'maps':len(maps),'coverage':dict(Counter(len(v) for v in maps.values())),'cache_keys':sorted(maps.get('sol_market_substitute_cache',{})),'amber_sample':list(maps.get('sol_market_good_spending_nobles_amber',{}).items())[:5]},ensure_ascii=False))
        sys.exit(0)
    outputs=[]
    for save in sorted((ROOT/'data/saves').glob('SP_HUN_1337_0[567]_15_*.eu5')):
        summary, records=topology(save)
        outputs.append({'summary':summary,'countries':records})
        print(json.dumps(summary,ensure_ascii=False),flush=True)
        (OUT/'save_topology.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2),encoding='utf-8')

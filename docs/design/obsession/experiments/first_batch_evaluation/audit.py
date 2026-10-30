import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json,sys
sys.path.insert(0,'.')
from copy import deepcopy
from tools.obsession_sim.graph import load_json, hops_from
from tools.obsession_sim import historical as H
g=load_json('tmp/obsession_real/eu5_1337.json')
res=json.load(open('docs/design/obsession/experiments/first_batch_evaluation/base_run.json',encoding='utf-8'))
idx={n:i for i,n in enumerate(g.names)}
tot={'targets':0,'free':0}
out={}
for good in ('coffee','tea','tobacco'):
    sp=H.scenario(good,deepcopy(g))
    routes=sp['transport']['routes']; corr=sp.get('land_corridors',[]); cev=sp.get('coefficient_events',[])
    wake=sp.get('wake',[]); contacts=sp.get('contacts',[]); waves=sp.get('waves',[]); coefs=sp.get('coefficients',[]); sources=sp.get('sources',[])
    # free parameters: each route has start, end, weight; corridor weight; coef event year+scale; wake year; contact year+value; wave start/end; coef scale; source start/end/amount
    free=3*len(routes)+len(corr)+2*len(cev)+len(wake)+2*len(contacts)+2*len(waves)+len(coefs)+3*len(sources)
    ms=sp['milestones']; tot['targets']+=len(ms); tot['free']+=free
    print(f"\n== {good}: milestones {len(ms)}; routes(directed rows) {len(routes)}, corridors {len(corr)}, coef-events {len(cev)}, wakes {len(wake)}, contacts {len(contacts)}, waves {len(waves)}, static coefs {len(coefs)} -> hand-set numbers ~{free}")
    endpoints={}
    for r in routes:
        for k in ('to',) + (() if r.get('directed') else ('from',)):
            endpoints.setdefault(r[k],[]).append(r['start_year'])
    corr_end={c['to']:c for c in corr}
    wake_nodes={n:w['start_year'] for w in wake for n in w.get('names',[])}
    contact_to={c['to']:c['start_year'] for c in contacts}
    sim={r['name']:r for r in res['goods'][good]['milestones']}
    rows=[]
    for m in ms:
        city=m['names'][0]; v=idx[city]
        why=[]
        if city in endpoints: why.append('route→'+'/'.join(str(y) for y in sorted(set(endpoints[city]))))
        if city in corr_end: why.append('corridor end')
        if city in wake_nodes: why.append(f'wake {wake_nodes[city]}')
        if city in contact_to: why.append(f'contact {contact_to[city]}')
        # is any route endpoint within 1 hop
        near=[e for e in endpoints if e!=city and idx[e] in g.incoming[v]]
        if near: why.append('route endpoint adjacent:'+','.join(near))
        r=sim[m['name']]
        rows.append((m['name'],city,m['target_year'],r['simulated_year'],'; '.join(why) or '-'))
        print(f"  {m['name']:<24}{city:<15} target {m['target_year']}  sim {r['simulated_year']}  | {'; '.join(why) or '-'}")
    out[good]=rows
print('\nTOTAL targets',tot['targets'],'hand-set numbers',tot['free'])
json.dump(out,open('docs/design/obsession/experiments/first_batch_evaluation/audit_rows.json','w'),ensure_ascii=False)

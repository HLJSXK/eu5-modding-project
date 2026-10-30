import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json,sys
sys.path.insert(0,'.')
from copy import deepcopy
from tools.obsession_sim.graph import load_json
from tools.obsession_sim import historical as H
from tools.obsession_sim.batch import run_batch
g=load_json('tmp/obsession_real/eu5_1337.json')
orig=H.scenario
def wave_of(sp,y):
    for w in sp.get('waves',[]):
        if w['start_year']<=y<w['end_year']: return w
    return None
def make(mode,delta=0,all_inputs=False):
    def sc(good,graph,**kw):
        sp=orig(good,graph,**kw)
        def move(y,end=None):
            w=wave_of(sp,y)
            if w is None: return y
            if mode=='wave_start': return w['start_year']
            ny=y+delta; hi=min(w['end_year'], end if end else 9999)-1
            return max(w['start_year'],min(ny,hi))
        last={}
        keep=[]
        for r in sorted(sp['transport']['routes'],key=lambda r:r['start_year']):
            r['start_year']=move(r['start_year'],r.get('end_year'))
            key=(r['from'],r['to'],r.get('directed',False))
            if key in last and r['start_year']<last[key]: r['start_year']=last[key]
            if r.get('end_year') and r['start_year']>=r['end_year']: continue
            last[key]=r.get('end_year',9999); keep.append(r)
        sp['transport']['routes']=keep
        if all_inputs:
            for k in ('coefficient_events','contacts','wake'):
                for r in sp.get(k,[]): r['start_year']=move(r['start_year'])
        return sp
    return sc
variants=[('base',None),('routes −20y',make('shift',-20)),('routes +20y',make('shift',20)),('routes at wave start',make('wave_start')),
          ('all timed inputs −20y',make('shift',-20,True)),('all timed inputs +20y',make('shift',20,True))]
out={}
for name,f in variants:
    H.scenario=f or orig
    sims,specs=H.prepare(g); led=run_batch(sims.values(),50000); rep=H.evaluate(sims,specs,led)
    H.scenario=orig
    row={good:{m['name']:(m['simulated_year'],m['within_tolerance']) for m in r['milestones']} for good,r in rep['goods'].items()}
    passed=sum(v[1] for gd in row.values() for v in gd.values())
    viol=sum(c['violations'] for r in rep['goods'].values() for c in r['constraints'])
    out[name]={'pass':passed,'violations':viol,'rows':row,'peak':led['peak_monthly_U']}
    print(f"{name:<24} pass {passed}/36  constraint-violating locations {viol}  peak {led['peak_monthly_U']}",flush=True)
json.dump(out,open('docs/design/obsession/experiments/first_batch_evaluation/ablation.json','w'),ensure_ascii=False)

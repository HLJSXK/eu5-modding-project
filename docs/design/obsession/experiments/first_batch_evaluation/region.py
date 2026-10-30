import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json,math
T=json.load(open('tools/obsession_sim/history_targets.json',encoding='utf-8'))
out={}
tot={k:[0,0,0] for k in ('city','country','region')}
for good in ('coffee','tea','tobacco'):
    pb=json.load(open(f'tmp/obsession_real/first_batch/{good}.playback.json',encoding='utf-8'))
    names=pb['names']; idx={n:i for i,n in enumerate(names)}; A=pb['attrs']; sy=pb['start_year']
    def col(th): return pb['first_positive'] if th=='positive' else pb['threshold_arrival'][str(th)]
    def arrive(nodes,th,frac=.5):
        c=col(th); got=sorted(c[v] for v in nodes if c[v] is not None and c[v]>=0); need=max(1,math.ceil(frac*len(nodes)))
        return None if len(got)<need else sy+got[need-1]/12
    print(f'\n== {good}')
    for name,city,th,ty,tol in T[good]:
        v=idx[city]; tag=A['owner_tag'][v]; reg=A['region'][v]
        sets={'city':[v],'country':[i for i,t in enumerate(A['owner_tag']) if t==tag] if tag else [v],'region':[i for i,r in enumerate(A['region']) if r==reg]}
        cells=[]
        for k,nodes in sets.items():
            y=arrive(nodes,th); tol_y=tol/12
            ok = y is not None and abs(y-ty)<=max(tol_y,0.01); ok2= y is not None and abs(y-ty)<=2*max(tol_y,.01)
            if name!='Japan custom':
                tot[k][0]+=ok; tot[k][1]+=ok2; tot[k][2]+=1
            cells.append(f"{k}:{'未达' if y is None else round(y,1)}{'✓' if ok else ('~' if ok2 else '✗')}")
        print(f"  {name:<24} target {ty}±{tol//12:<3} [{tag} n={len(sets['country'])}; {reg} n={len(sets['region'])}]  "+'  '.join(cells))
print()
for k,(a,b,n) in tot.items(): print(f"{k:<8} within tol {a}/{n}   within 2×tol {b}/{n}")

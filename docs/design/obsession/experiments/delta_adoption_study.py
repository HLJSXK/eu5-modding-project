"""Adopted change tolerance delta=0.1 under the option-A queue scheduler.

Hex grid (13,572 nodes), one good, abstract U with option-A pricing
(pop 3, push new 4 / pending 1). Compares delta 0 and 0.1 in growth, a
strongly controlled east half (gain 0.974), and whole-map fatigue decay
(rho 0.95, p 0.005, gain 0.98) to expose the decay freeze floor
x* ~ delta / (1 - effective gain). No EU5 timing claim. Only --output writes.
"""

import argparse
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from immunity_lock_study import NBRS, N, CENTER, W  # noqa: E402

EPS = 1e-5

def runA(delta, rho=0.99, p=0.02, init=None, region=None, rounds=3000):
    x=[0.0]*N; ptr=[None]*N; st={'h':None,'t':None,'n':0}
    par=[region(v) if region else (rho,p) for v in range(N)]
    U=0; served=0; peak=0
    def push(v):
        if ptr[v] is not None: return 1
        ptr[v]=v
        if st['t'] is None: st['h']=v
        else: ptr[st['t']]=v
        st['t']=v; st['n']+=1; return 4
    def pop():
        v=st['h']; n=ptr[v]
        if st['n']==1: st['h']=st['t']=None
        else: st['h']=n
        ptr[v]=None; st['n']-=1; return v
    if init is None:
        x[CENTER]=25.0
        for v in (CENTER,*NBRS[CENTER]): push(v)
    else:
        for v in range(N): x[v]=init; push(v)
    r=0
    while st['n'] and r<rounds:
        n0=st['n']; peak=max(peak,n0)
        for _ in range(n0):
            v=pop(); d=len(NBRS[v]); rv,pv=par[v]; old=x[v]
            y=rv*old
            for u in NBRS[v]: y+=pv*x[u]
            y=min(100.0,y)
            if y<EPS: y=0.0
            U+=3+8+4*d
            if abs(y-old)>delta or (y==0.0 and old!=0.0):
                x[v]=y; U+=1+d+push(v)
                for u in NBRS[v]: U+=push(u)
        served+=n0; r+=1
    pos=[a for a in x if a>0]
    return dict(rounds=r,U=U,served=served,peak=peak,members=sum(a>=1 for a in x),sat=sum(a>=100 for a in x),
                maxx=max(x),minpos=min(pos) if pos else 0, mean=sum(x)/N)


def strong(v):
    return (0.95, 0.004) if v % W > W // 2 + 5 else (0.99, 0.02)


GOODS_RHO0 = {"tobacco": 0.995, "coffee/tea/sugar/liquor/chili/incense/beeswax": 0.99,
              "wine/beer/medicaments": 0.985, "cocoa/pepper/cloves/saffron": 0.98,
              "staple": 0.975, "glass/furniture": 0.97, "horses/camels/elephants": 0.965,
              "porcelain/jewelry/pearls/gems/amber/ivory": 0.96, "lacquerware/fur": 0.955,
              "fine_cloth": 0.95, "books/paper": 0.998}


def study():
    out = {}
    for name, kw in [("growth_delta_0", dict(delta=0)), ("growth_delta_0.1", dict(delta=0.1)),
                     ("controlled_strong_delta_0", dict(delta=0, region=strong)),
                     ("controlled_strong_delta_0.1", dict(delta=0.1, region=strong)),
                     ("fatigue_decay_delta_0", dict(delta=0, rho=0.95, p=0.005, init=100.0)),
                     ("fatigue_decay_delta_0.1", dict(delta=0.1, rho=0.95, p=0.005, init=100.0))]:
        out[name] = runA(**kw)
    out["isolated_freeze_floor_delta_0.1_monthly"] = {k: round(0.1 / (1 - r), 2) for k, r in GOODS_RHO0.items()}
    out["isolated_freeze_floor_delta_0.1_annual_step"] = {k: round(0.1 / (1 - r ** 12), 2) for k, r in GOODS_RHO0.items()}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    res = study()
    if args.output:
        args.output.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in res.items():
        print(k, v)
    print("Synthetic abstract counts only; no EU5 timing claim.")


if __name__ == "__main__":
    main()

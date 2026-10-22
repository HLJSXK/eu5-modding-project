"""Estimate the whole-group basket fix (2026-10-22 plan); read-only, writes nothing.

Prints: partial (pop, group) cells, the proposed subscribe/unsubscribe matrix,
budget-preserving fill quantities, per-pop spend change, world quantity shifts
(HUN 1337 population mix) and the condiments olive/salt multiplier before/after.
"""
import csv
import glob
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from sol_substitution import CONFIG, response  # noqa: E402

P = "nobles clergy burghers laborers peasants soldiers".split()
q, price, G = {}, {}, {}
for r in csv.DictReader((ROOT / "data/demand_price_table.csv").open(encoding="utf-8-sig")):
    q[r["good"]] = {p: float(r[p]) for p in P}
    price[r["good"]] = float(r["price"])
for r in csv.DictReader((ROOT / "data/goods_weights.csv").open(encoding="utf-8-sig")):
    G.setdefault(r["group"], []).append(r["good"])
pos = lambda x, p: round(q[x][p], 5) > 0

# Proposed subscriptions: full groups stay; a partial group is kept when it owns a
# consumed good not explained by another kept group; commoner clothing -> basic.
sub = {}
for p in P:
    full = {g for g, m in G.items() if all(pos(x, p) for x in m)}
    part = {g for g, m in G.items() if any(pos(x, p) for x in m)} - full
    covered = {x for g in full for x in G[g]}
    for g, m in G.items():
        own = [x for x in m if pos(x, p) and x not in covered
               and not any(x in G[h] for h in part if h != g)]
        sub[p, g] = int(g in full or (g in part and bool(own)))
for p in ("laborers", "peasants", "soldiers"):
    sub[p, "basic_clothing"], sub[p, "standard_clothing"] = 1, 0


def fill():
    """Keep each (pop, group) budget; missing members get the group's mean share."""
    out = {}
    for p in P:
        groups = [g for g in G if sub[p, g]]
        k = {x: sum(x in G[g] for g in groups) for x in q}
        alloc = dict.fromkeys(q, 0.)
        for g in groups:
            have = [x for x in G[g] if pos(x, p)]
            part = {x: q[x][p] * price[x] / k[x] for x in have}
            budget = sum(part.values())
            for x in G[g]:
                part.setdefault(x, budget / len(have))
            scale = budget / sum(part.values())
            for x, v in part.items():
                alloc[x] += v * scale
        for x in q:
            exact = alloc[x] / price[x]
            out[p, x] = max(round(exact, 5), 1e-5) if exact > 0 else 0.
    return out


new = fill()
print("== cells: (pop, group, action, members to add or kept goods)")
for p in P:
    for g, m in G.items():
        have = [x for x in m if pos(x, p)]
        if have and len(have) < len(m):
            print(p, g, "FILL" if sub[p, g] else "DROP",
                  [x for x in m if not pos(x, p)] if sub[p, g] else have)
print("\n== per-pop spend at default price")
for p in P:
    a = sum(q[x][p] * price[x] for x in q)
    b = sum(new[p, x] * price[x] for x in q)
    print(f"{p:9} {a:.6g} -> {b:.6g} ({(b / a - 1) * 100:+.1f}%)")

pop = dict.fromkeys(P, 0.)
for r in csv.DictReader(open(sorted(glob.glob(str(ROOT / "data/save_analysis/SP_HUN_1337_08*/locations.csv")))[0], encoding="utf-8-sig")):
    for p in P:
        pop[p] += float(r["population_" + p] or 0)
print("\n== world quantity shift (HUN 1337 population mix)")
for x in sorted(q):
    a = sum(pop[p] * round(q[x][p], 5) for p in P)
    b = sum(pop[p] * new[p, x] for p in P)
    if abs(b - a) > 1e-9:
        print(f"{x:12} {(b / a - 1) * 100 if a else float('inf'):+.0f}%")

print("\n== condiments example: sugar unsupplied, olives weight 2, salt weight 1")
w = dict.fromkeys(q, 1.); w["olives"] = 2.
for label, qq, groups_for in (
        ("old", {(p, x): round(q[x][p], 5) for p in P for x in q},
         lambda p: {g: [x for x in m if pos(x, p)] for g, m in G.items()}),
        ("new", new, lambda p: {g: m for g, m in G.items() if sub[p, g]})):
    for x in ("olives", "salt"):
        D = {}
        for p in P:
            gs = {g: m for g, m in groups_for(p).items() if m}
            el = {y for m in gs.values() for y in m} - {"sugar"}
            D[p] = response(w, el, gs, {g: CONFIG["historical_sizes"][g] for g in gs}).get(x, 1.)
        base = sum(pop[p] * qq[p, x] for p in P)
        print(label, x, "M=%.3f" % (sum(pop[p] * qq[p, x] * D[p] for p in P) / base))

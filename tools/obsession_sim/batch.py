"""Calendar-aligned, round-robin shared-budget simulations (one ledger per month)."""
from __future__ import annotations


def run_batch(simulations, budget=480_000):
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise ValueError("shared budget must be a positive integer")
    sims = list(simulations)
    monthly, overruns = [], []
    month = 0
    while any(not sim.done and sim.t < sim.P.max_months for sim in sims):
        spent = 0
        prepared = []
        for k in range(len(sims)):
            sim = sims[(month + k) % len(sims)]
            if sim.done or sim.t >= sim.P.max_months:
                continue
            before = sim.U
            if sim.begin_month():
                prepared.append((sim, sim.U - before))
            spent += sim.U - before
        # Every good's clock/input costs have been booked before admitting a
        # node. Earlier goods cannot spend the later goods' maintenance reserve.
        for sim, maintenance in prepared:
            previous = sim.P.budget
            sim.P.budget = maintenance + max(0, budget - spent)
            before = sim.U
            try:
                sim.serve_month()
            finally:
                sim.P.budget = previous
            spent += sim.U - before
        monthly.append(spent)
        if spent > budget:
            overruns.append({"month": month, "U": spent})
        month += 1
    return {"budget": budget, "months": len(monthly), "monthly_U": monthly,
            "peak_monthly_U": max(monthly, default=0), "total_U": sum(monthly),
            "overruns": overruns,
            "note": "All goods' maintenance is charged before fair node admission; indivisible maintenance-only overruns are reported."}

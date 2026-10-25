"""Reproduce the 1406 purchasing-power investigation from exported save data."""
from __future__ import annotations

import csv
import json
import mmap
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.eu5_save_parser.parser import (
    _COUNTRY_RECORD_RE, _top_level_bounds, decode_jomini_fixed_point,
)

STEM = "SP_CAS_1406_01_23_de3601a2-b771-4e4e-a6bb-34fed262dca7"
ANALYSIS = ROOT / "data/save_analysis" / STEM
OUT = ANALYSIS / "purchasing_power"
OUT.mkdir(exist_ok=True)
POPS = ("nobles", "clergy", "burghers", "laborers", "peasants", "soldiers", "tribesmen")
STRATA = ("nobles", "clergy", "burghers", "commoners", "tribesmen")


def number(row, key):
    return float(row.get(key) or 0)


def load_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def summarize(rows):
    result = {"location_count": len(rows), "strata": {}}
    for stratum in STRATA:
        keys = ("base_spending", "income", "net_income", "liquid_funds")
        values = {k: sum(number(r, f"sol_location_{stratum}_{k}") for r in rows) for k in keys}
        base, funds = values["base_spending"], values["liquid_funds"]
        values["alpha"] = funds / base if base else None
        values["delta_percent"] = (funds / base - 1) * 100 if base else None
        values["population_thousands_at_save_time"] = sum(number(r, f"population_{stratum}") for r in rows)
        for scale in ("raw", "final"):
            values[f"{scale}_modeled_spending"] = sum(
                number(r, f"sol_location_{stratum}_base_spending") * number(r, f"sol_location_{scale}_demand_scale")
                for r in rows
            )
        result["strata"][stratum] = values
    valid = [r for r in rows if number(r, "sol_location_commoners_base_spending") > 0]
    ratios = sorted(number(r, "sol_location_commoners_liquid_funds") / number(r, "sol_location_commoners_base_spending") for r in valid)
    result["commoner_ratio_quantiles"] = {str(q): ratios[int((len(ratios) - 1) * q)] for q in (0, .1, .25, .5, .75, .9, .99, 1)}
    result["commoner_locations_alpha_ge_6"] = sum(a >= 6 for a in ratios)
    result["commoner_location_count_positive_baseline"] = len(valid)
    return result


locations = load_csv(ANALYSIS / "locations.csv")
countries = load_csv(ANALYSIS / "countries.csv")
cas = next(c for c in countries if c["owner_tag"] == "CAS")
cas_rows = [r for r in locations if r["owner_tag"] == "CAS" and r.get("sol_location_commoners_base_spending")]
world_rows = [r for r in locations if r["owner_id"] and r.get("sol_location_base_total_spending")]
table = {r["good"]: r for r in load_csv(ROOT / "data/demand_price_table.csv")}
goods = sorted(table)
source = ROOT / "data/saves" / (STEM + ".eu5")
pair_re = re.compile(rb"key=\{\s*type=mark\s*identity=(\d+)\s*\}\s*value=\{\s*type=value(?:\s*identity=(\d+))?\s*\}")
var_re = re.compile(rb"(?m)^\t{4}flag=([^\r\n]+)\r?\n\t{4}data=\{\r?\n\t{5}type=value\r?\n(?:\t{5}identity=(\d+)\r?\n)?")
maps = {}
with source.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
    start, end = _top_level_bounds(view, "variables")
    anchors = list(re.finditer(rb'name="([^"]+)"', view[start:end]))
    for i, match in enumerate(anchors):
        name = match.group(1).decode()
        if not name.startswith(("sol_market_", "sol_country_market_spending_")):
            continue
        a = start + match.end()
        b = start + anchors[i + 1].start() if i + 1 < len(anchors) else end
        maps[name] = {int(m.group(1)): decode_jomini_fixed_point(int(m.group(2) or 0)) for m in pair_re.finditer(view, a, b)}
    start, _ = _top_level_bounds(view, "countries")
    end = _top_level_bounds(view, "population")[0]
    records = list(_COUNTRY_RECORD_RE.finditer(view, start, end))
    idx = next(i for i, m in enumerate(records) if int(m.group(1)) == int(cas["owner_id"]))
    a, b = records[idx].start(), records[idx + 1].start()
    cv = {m.group(1).decode(): decode_jomini_fixed_point(int(m.group(2) or 0)) for m in var_re.finditer(view, a, b)}
    record = view[a:b]
    tax = re.search(rb"tax_rates=\{([^}]+)\}", record).group(1).decode()
    start, end = _top_level_bounds(view, "market_manager")
    market_records = list(re.finditer(rb"(?m)^(\d+)=\{\r?\n\tcenter=(\d+)", view[start:end]))
    market_data = {}
    for i, m in enumerate(market_records):
        mid = int(m.group(1))
        a = start + m.start()
        b = start + market_records[i + 1].start() if i + 1 < len(market_records) else end
        prices = {p.group(1).decode(): float(p.group(2)) for p in re.finditer(rb"(?m)^\t\t([a-z_]+)=\{\r?\n\t{3}price=([-+0-9.eE]+)", view[a:b])}
        market_data[mid] = {"center": int(m.group(2)), "prices": prices}


def market_map(name, mid):
    return maps.get(name, {}).get(mid, 0.0)


pop_by_market = defaultdict(lambda: defaultdict(float))
for row in cas_rows:
    for pop in POPS:
        pop_by_market[int(row["market_id"])][pop] += number(row, f"population_{pop}")
market_reports = {}
good_rows = []
replay_errors = []
four_strata_replay_errors = defaultdict(list)
for mid, populations in pop_by_market.items():
    totals = defaultdict(float)
    for good in goods:
        data = table[good]
        effect = cv.get(f"sol_good_effective_{good}", 1.0)
        base_price = float(data["price"])
        supply = market_map(f"sol_market_consumes_{good}", mid)
        price = market_data[mid]["prices"].get(good)
        row = {"market_id": mid, "good": good, "cached_supply": supply, "current_market_price": price,
               "base_price_head": base_price, "saved_effective_good_factor": effect}
        for pop in ("laborers", "peasants", "soldiers"):
            quantity = round(number(data, pop), 5)
            popsize = populations[pop]
            cost = market_map(f"sol_market_good_spending_{pop}_{good}", mid)
            row[f"{pop}_head_quantity"] = quantity
            row[f"{pop}_cached_unit_cost"] = cost
            totals["saved_goods_cost_no_substitution"] += popsize * cost
            totals["saved_goods_cost_with_effective_factor"] += popsize * cost * effect
            totals["head_full_base_prices_no_factors"] += popsize * quantity * base_price
            if supply > 0:
                totals["head_supplied_base_prices_no_factors"] += popsize * quantity * base_price
                if price is not None:
                    totals["head_supplied_capped_prices_no_factors"] += popsize * quantity * min(price, base_price)
                    totals["head_supplied_actual_prices_no_factors"] += popsize * quantity * price
                    totals["head_supplied_actual_prices_effective_factors"] += popsize * quantity * price * effect
                    totals["head_supplied_capped_prices_effective_factors"] += popsize * quantity * min(price, base_price) * effect
                    totals["head_fixed_point_cost_capped_no_factors"] += popsize * int(quantity * min(price, base_price) * 100000 + 1e-8) / 100000
            row[f"{pop}_predicted_contribution"] = popsize * cost * effect
        row["commoner_predicted_contribution"] = sum(row[f"{pop}_predicted_contribution"] for pop in ("laborers", "peasants", "soldiers"))
        good_rows.append(row)
    totals["population_thousands"] = sum(populations[pop] for pop in ("laborers", "peasants", "soldiers"))
    totals["saved_location_base_spending"] = sum(number(r, "sol_location_commoners_base_spending") for r in cas_rows if int(r["market_id"]) == mid)
    totals["saved_location_liquid_funds"] = sum(number(r, "sol_location_commoners_liquid_funds") for r in cas_rows if int(r["market_id"]) == mid)
    totals["unit_cost_peasants_from_saved_map"] = market_map("sol_market_unit_spending_peasants", mid)
    # Reproduce both engine multiplication boundaries in exact 1e-5 units.
    units = {pop: 0 for pop in ("laborers", "peasants", "soldiers")}
    for good in goods:
        factor = round(cv.get(f"sol_good_effective_{good}", 1.0) * 100000)
        for pop in units:
            cost = round(market_map(f"sol_market_good_spending_{pop}_{good}", mid) * 100000)
            units[pop] += cost * factor // 100000
    replay = 0
    for location in cas_rows:
        if int(location["market_id"]) != mid:
            continue
        baseline = sum(units[pop] * round(number(location, f"population_{pop}") * 100000) // 100000 for pop in units)
        saved = round(number(location, "sol_location_commoners_base_spending") * 100000)
        replay_errors.append(abs(baseline - saved))
        replay += baseline
    totals["fixed_point_replayed_location_baseline"] = replay / 100000
    totals["fixed_point_unit_costs"] = {pop: value / 100000 for pop, value in units.items()}
    for stratum in ("nobles", "clergy", "burghers", "commoners"):
        members = ("laborers", "peasants", "soldiers") if stratum == "commoners" else (stratum,)
        stratum_units = {
            pop: sum(
                round(market_map(f"sol_market_good_spending_{pop}_{good}", mid) * 100000)
                * round(cv.get(f"sol_good_effective_{good}", 1.0) * 100000) // 100000
                for good in goods
            ) for pop in members
        }
        for location in cas_rows:
            if int(location["market_id"]) != mid:
                continue
            replayed = sum(stratum_units[pop] * round(number(location, f"population_{pop}") * 100000) // 100000 for pop in members)
            saved = round(number(location, f"sol_location_{stratum}_base_spending") * 100000)
            four_strata_replay_errors[stratum].append(abs(replayed - saved))
    market_reports[str(mid)] = {"center": market_data[mid]["center"], **totals}

summary = {
    "save": STEM,
    "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
    "source_size": source.stat().st_size,
    "CAS": summarize(cas_rows), "world": summarize(world_rows),
    "CAS_country_display": {k: number(cas, k) for k in cas if k.startswith("gls_sol_")},
    "CAS_savings_adjustment": number(cas, "gls_savings_pressure_adjustment"),
    "CAS_tax_rates_raw": tax, "CAS_markets": market_reports,
    "full_base_price_unit_costs_head": {pop: sum(round(number(data, pop), 5) * float(data["price"]) for data in table.values()) for pop in POPS},
    "effective_factor_peasant_goods": {g: cv.get(f"sol_good_effective_{g}", 1) for g in goods if number(table[g], "peasants") > 0},
}
country_groups = defaultdict(list)
for row in world_rows:
    country_groups[row["owner_id"]].append(row)
cr = []
for cid, rows in country_groups.items():
    base = sum(number(r, "sol_location_commoners_base_spending") for r in rows)
    funds = sum(number(r, "sol_location_commoners_liquid_funds") for r in rows)
    if base > 0:
        cr.append({"country_id": cid, "tag": rows[0]["owner_tag"], "location_count": len(rows), "base": base, "funds": funds, "alpha": funds / base, "delta_percent": (funds / base - 1) * 100})
summary["country_commoner_positive_baseline_count"] = len(cr)
summary["country_commoner_alpha_median"] = statistics.median(r["alpha"] for r in cr)
summary["country_commoner_alpha_ge_6_count"] = sum(r["alpha"] >= 6 for r in cr)
summary["CAS_baseline_replay_max_error_fixed_point_units"] = max(replay_errors)
assert len(replay_errors) == len(cas_rows) == 263
assert max(replay_errors) == 0, "Per-location saved costs must replay exactly"
summary["CAS_four_strata_replay_max_error_fixed_point_units"] = {
    stratum: max(errors) for stratum, errors in four_strata_replay_errors.items()
}
for stratum, errors in four_strata_replay_errors.items():
    assert len(errors) == 263 and max(errors) <= 1, f"{stratum}: saved costs must replay within one 1e-5 unit"
summary["CAS_four_strata_replay_nonzero_error_count"] = {
    stratum: sum(error != 0 for error in errors) for stratum, errors in four_strata_replay_errors.items()
}
assert abs(sum(number(r, "sol_location_commoners_liquid_funds") for r in cas_rows) - number(cas, "sol_country_demand_target_commoners")) < 0.00001
summary["CAS_snapshot_basket_scaling_only"] = {
    str(k): (summary["CAS"]["strata"]["commoners"]["alpha"] / k - 1) * 100
    for k in (1, 2, 3, 4, 6)
}


def four_stratum_counterfactual(rows):
    """Separate availability from cheap prices with common quantities/funds.

    Neutral goods factors and ordinary precision isolate these two mechanisms.
    The sequence is full basket -> supplied basket -> capped current prices.
    """
    members = {
        "nobles": ("nobles",), "clergy": ("clergy",),
        "burghers": ("burghers",), "commoners": ("laborers", "peasants", "soldiers"),
    }
    populations = defaultdict(lambda: defaultdict(float))
    for location in rows:
        mid = int(location["market_id"])
        assert mid in market_data, f"Missing market record: {mid}"
        for pop in POPS:
            populations[mid][pop] += number(location, f"population_{pop}")
    result = {}
    for stratum, pops in members.items():
        stages = defaultdict(float)
        contributions = []
        for good in goods:
            base_price = float(table[good]["price"])
            item = defaultdict(float)
            for mid, counts in populations.items():
                amount = sum(counts[pop] * round(number(table[good], pop), 5) for pop in pops)
                if amount <= 0:
                    continue
                nominal = amount * base_price
                stages["full_base_price_cost"] += nominal
                if market_map(f"sol_market_consumes_{good}", mid) <= 0:
                    item["missing_cost"] += nominal
                    continue
                assert good in market_data[mid]["prices"], (mid, good)
                actual_price = market_data[mid]["prices"][good]
                assert actual_price >= 0
                capped = amount * min(actual_price, base_price)
                stages["supplied_base_price_cost"] += nominal
                stages["supplied_capped_price_cost"] += capped
                stages["supplied_actual_price_cost"] += amount * actual_price
                item["cheap_cost"] += nominal - capped
            contributions.append({"good": good, "missing_cost": item["missing_cost"], "cheap_cost": item["cheap_cost"]})
        full = stages["full_base_price_cost"]
        available = stages["supplied_base_price_cost"]
        cheap = stages["supplied_capped_price_cost"]
        funds = sum(number(r, f"sol_location_{stratum}_liquid_funds") for r in rows)
        saved = sum(number(r, f"sol_location_{stratum}_base_spending") for r in rows)
        assert 0 < cheap <= available <= full
        assert abs(sum(c["missing_cost"] for c in contributions) - (full - available)) < 1e-6
        assert abs(sum(c["cheap_cost"] for c in contributions) - (available - cheap)) < 1e-6
        result[stratum] = {
            **stages, "saved_baseline": saved, "saved_funds": funds,
            "missing_cost_reduction_percent": (1 - available / full) * 100,
            "cheap_cost_reduction_of_remaining_percent": (1 - cheap / available) * 100,
            "cheap_cost_reduction_of_full_percent": (available - cheap) / full * 100,
            "combined_cost_reduction_percent": (1 - cheap / full) * 100,
            "missing_alpha_multiplier": full / available,
            "cheap_alpha_multiplier": available / cheap,
            "combined_alpha_multiplier": full / cheap,
            "pp_full_base_price_percent": (funds / full - 1) * 100,
            "pp_supplied_base_price_percent": (funds / available - 1) * 100,
            "pp_supplied_capped_price_percent": (funds / cheap - 1) * 100,
            "pp_saved_percent": (funds / saved - 1) * 100,
            "missing_pp_gain_percentage_points": (funds / available - funds / full) * 100,
            "cheap_pp_gain_percentage_points": (funds / cheap - funds / available) * 100,
            "missing_share_of_combined_cost_loss_percent": (full - available) / (full - cheap) * 100,
            "price_cap_cost_discount_percent": (1 - cheap / stages["supplied_actual_price_cost"]) * 100,
            "top_missing_goods": sorted(contributions, key=lambda c: -c["missing_cost"])[:5],
            "top_cheap_goods": sorted(contributions, key=lambda c: -c["cheap_cost"])[:5],
        }
    return result


summary["four_stratum_counterfactuals"] = {
    "CAS": four_stratum_counterfactual(cas_rows),
    "world": four_stratum_counterfactual(world_rows),
}
comparison_rows = [
    {"scope": scope, "stratum": stratum, **{k: v for k, v in values.items() if not k.startswith("top_")}}
    for scope, strata in summary["four_stratum_counterfactuals"].items()
    for stratum, values in strata.items()
]

with (OUT / "summary.json").open("w", encoding="utf-8") as stream:
    json.dump(summary, stream, ensure_ascii=False, indent=2)
for name, rows in (("CAS_goods.csv", good_rows), ("country_commoners.csv", cr), ("four_strata_counterfactuals.csv", comparison_rows)):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("Wrote", OUT)

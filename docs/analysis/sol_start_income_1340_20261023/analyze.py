"""Audit early-game income medians and a median-income basket calibration."""
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
from tools.eu5_save_parser.parser import _COUNTRY_RECORD_RE, _top_level_bounds, decode_jomini_fixed_point

STEM = "1340.04.01_autosave_c681faf6-91c6-45a9-bde4-9d8c22cd321e"
BASE = ROOT / "data/save_analysis" / STEM
SOURCE = ROOT / "data/saves/observer_archive/c681faf6-91c6-45a9-bde4-9d8c22cd321e" / (STEM + ".eu5")
OUT = BASE / "income_calibration"
STRATA = ("nobles", "clergy", "burghers", "commoners")
MEMBERS = {s: (s,) for s in STRATA}
MEMBERS["commoners"] = ("laborers", "peasants", "soldiers")
POPS = ("nobles", "clergy", "burghers", "laborers", "peasants", "soldiers")
REPRESENTATIVES = ("CAS", "FRA", "VEN", "MAM", "CHI", "DLH", "VIJ", "MAL", "JAP")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def number(row, key):
    return float(row.get(key) or 0)


def weighted_quantile(pairs, quantile=.5):
    values = sorted((value, weight) for value, weight in pairs if weight > 0)
    total = sum(weight for _, weight in values)
    assert total > 0 and 0 < quantile <= 1
    target, cumulative = total * quantile, 0
    for value, weight in values:
        cumulative += weight
        if cumulative >= target:
            return value
    return values[-1][0]


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


locations = read_csv(BASE / "locations.csv")
owned = [row for row in locations if row["owner_id"]]
countries = read_csv(BASE / "countries.csv")
country_by_tag = {row["owner_tag"]: row for row in countries}
country_by_id = {row["owner_id"]: row for row in countries}
good_table = {}
for row in read_csv(ROOT / "data/demand_price_table.csv"):
    if row["good"] in good_table:
        assert all(abs(number(row, key) - number(good_table[row["good"]], key)) < 1e-9 for key in ("price", *POPS))
    good_table[row["good"]] = row
goods = sorted(good_table)
full_unit_costs = {
    pop: sum(round(number(row, pop), 5) * number(row, "price") for row in good_table.values()) for pop in POPS
}
rows_by_country = defaultdict(list)
for row in owned:
    rows_by_country[row["owner_id"]].append(row)

income_stats = {}
country_income_rows = []
for stratum in STRATA:
    popkey = f"population_{stratum}"
    eligible = [row for row in owned if number(row, popkey) > 0]
    valid = [row for row in eligible if row.get(f"sol_location_{stratum}_net_income") not in (None, "")]
    total_population = sum(number(row, popkey) for row in eligible)
    covered_population = sum(number(row, popkey) for row in valid)
    assert abs(total_population - covered_population) < 1e-5, (stratum, "income coverage")
    stats = {"locations": len(valid), "population_thousands": covered_population,
             "coverage_percent": covered_population / total_population * 100, "metrics": {}}
    for metric in ("income", "net_income", "liquid_funds"):
        pairs = [(number(row, f"sol_location_{stratum}_{metric}") / number(row, popkey), number(row, popkey)) for row in valid]
        grouped = defaultdict(lambda: [0.0, 0.0])
        for row in valid:
            grouped[row["owner_id"]][0] += number(row, f"sol_location_{stratum}_{metric}")
            grouped[row["owner_id"]][1] += number(row, popkey)
        country_pairs = [(income / pop, pop) for income, pop in grouped.values()]
        median = weighted_quantile(pairs)
        stats["metrics"][metric] = {
            "population_weighted_location_median_monthly_per_1000": median,
            "population_weighted_location_median_annual_per_1000": median * 12,
            "population_weighted_location_median_monthly_per_person": median / 1000,
            "country_equal_weight_median_monthly_per_1000": statistics.median(value for value, _ in country_pairs),
            "population_weighted_country_median_monthly_per_1000": weighted_quantile(country_pairs),
            "location_equal_weight_median_monthly_per_1000": statistics.median(value for value, _ in pairs),
            "population_weighted_mean_monthly_per_1000": sum(value * weight for value, weight in pairs) / covered_population,
            "zero_income_population_percent": sum(weight for value, weight in pairs if value == 0) / covered_population * 100,
            "countries": len(country_pairs),
            "weighted_quantiles_monthly_per_1000": {str(q): weighted_quantile(pairs, q) for q in (.1, .25, .5, .75, .9)},
        }
        if metric == "net_income":
            for cid, (income, population) in grouped.items():
                country_income_rows.append({"country_id": cid, "tag": country_by_id[cid]["owner_tag"],
                                            "stratum": stratum, "net_income": income, "population_thousands": population,
                                            "monthly_net_per_1000": income / population})
    income_stats[stratum] = stats

pair_re = re.compile(rb"key=\{\s*type=mark\s*identity=(\d+)\s*\}\s*value=\{\s*type=value(?:\s*identity=(\d+))?\s*\}")
var_re = re.compile(rb"(?m)^\t{4}flag=([^\r\n]+)\r?\n\t{4}data=\{\r?\n\t{5}type=value\r?\n(?:\t{5}identity=(\d+)\r?\n)?")
market_maps, market_data, country_variables, country_types = {}, {}, {}, {}
matched_country_income_samples = {}
with SOURCE.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
    start, end = _top_level_bounds(view, "variables")
    anchors = list(re.finditer(rb'name="([^"]+)"', view[start:end]))
    for i, match in enumerate(anchors):
        name = match.group(1).decode()
        if not name.startswith(("sol_market_consumes_", "sol_market_good_spending_")):
            continue
        a = start + match.end()
        b = start + anchors[i + 1].start() if i + 1 < len(anchors) else end
        market_maps[name] = {int(m.group(1)): decode_jomini_fixed_point(int(m.group(2) or 0)) for m in pair_re.finditer(view, a, b)}
    start, end = _top_level_bounds(view, "market_manager")
    entries = list(re.finditer(rb"(?m)^(\d+)=\{\r?\n\tcenter=(\d+)", view[start:end]))
    for i, match in enumerate(entries):
        a = start + match.start()
        b = start + entries[i + 1].start() if i + 1 < len(entries) else end
        prices = {m.group(1).decode(): float(m.group(2)) for m in re.finditer(rb"(?m)^\t\t([a-z_]+)=\{\r?\n\t{3}price=([-+0-9.eE]+)", view[a:b])}
        market_data[int(match.group(1))] = {"center": int(match.group(2)), "prices": prices}
    start, _ = _top_level_bounds(view, "countries")
    end = _top_level_bounds(view, "population")[0]
    entries = list(_COUNTRY_RECORD_RE.finditer(view, start, end))
    representative_ids = {country_by_tag[tag]["owner_id"] for tag in REPRESENTATIVES}
    for i, match in enumerate(entries):
        cid = match.group(1).decode()
        a, b = match.start(), entries[i + 1].start() if i + 1 < len(entries) else end
        kind = re.search(rb"(?m)^\tcountry_type=([^\r\n]+)", view[a:b])
        country_types[cid] = kind.group(1).decode() if kind else "unspecified"
        samples = {}
        for match_value in var_re.finditer(view, a, b):
            name = match_value.group(1).decode()
            if name.startswith(("sol_ls_pop_", "sol_ls_income_")):
                samples[name] = decode_jomini_fixed_point(int(match_value.group(2) or 0))
        if samples:
            matched_country_income_samples[cid] = samples
        if cid in representative_ids:
            country_variables[cid] = {m.group(1).decode(): decode_jomini_fixed_point(int(m.group(2) or 0)) for m in var_re.finditer(view, a, b)}

# Four-stratum calibration: all three commoner subtypes have the same complete
# reference cost. This avoids country composition changing the nominal anchor.
median_net = {s: income_stats[s]["metrics"]["net_income"]["population_weighted_location_median_monthly_per_1000"] for s in STRATA}
median_funds = {s: income_stats[s]["metrics"]["liquid_funds"]["population_weighted_location_median_monthly_per_1000"] for s in STRATA}
pop_stratum = {pop: stratum for stratum, pops in MEMBERS.items() for pop in pops}
calibration_factors = {pop: median_net[pop_stratum[pop]] / full_unit_costs[pop] for pop in POPS}
minimum_positive_unit_costs = {
    pop: sum(number(row, "price") * .00001 for row in good_table.values() if round(number(row, pop), 5) > 0)
    for pop in POPS
}
for pop in POPS:
    assert abs(full_unit_costs[pop] * calibration_factors[pop] - median_net[pop_stratum[pop]]) < 1e-12
    assert median_net[pop_stratum[pop]] > minimum_positive_unit_costs[pop]

representative_rows, country_diagnostics = [], {}
for tag in REPRESENTATIVES:
    country = country_by_tag[tag]
    cid = country["owner_id"]
    rows = [row for row in rows_by_country[cid] if row.get("sol_location_base_total_spending") not in (None, "")]
    populations = defaultdict(lambda: defaultdict(float))
    for row in rows:
        mid = int(row["market_id"])
        assert mid in market_data
        for pop in POPS:
            populations[mid][pop] += number(row, f"population_{pop}")
    multipliers = sorted({number(row, "sol_location_liquid_funds_multiplier") for row in rows})
    country_diagnostics[tag] = {"location_count": len(rows), "country_type": country_types[cid],
                                "cached_funds_multipliers": multipliers, "population_thousands": number(country, "population_total"),
                                "substitution_cache_year": country_variables[cid].get("sol_substitute_year")}
    for stratum, pops in MEMBERS.items():
        totals = defaultdict(float)
        replay_max_error, replay_nonzero = 0, 0
        units_by_market = {}
        for mid, counts in populations.items():
            units = {pop: 0 for pop in pops}
            for good in goods:
                data = good_table[good]
                price0 = number(data, "price")
                supplied = market_maps.get(f"sol_market_consumes_{good}", {}).get(mid, 0) > 0
                factor = country_variables[cid].get(f"sol_good_effective_{good}", 1)
                for pop in pops:
                    amount = counts[pop] * round(number(data, pop), 5)
                    nominal = amount * price0
                    totals["full_cost"] += nominal
                    totals["calibrated_full_cost"] += nominal * calibration_factors[pop]
                    if supplied and amount:
                        assert good in market_data[mid]["prices"], (mid, good)
                        price = market_data[mid]["prices"][good]
                        assert price >= 0
                        capped = amount * min(price0, price)
                        totals["supplied_cost"] += nominal
                        totals["capped_cost"] += capped
                        totals["actual_price_cost"] += amount * price
                        totals["calibrated_supplied_cost"] += nominal * calibration_factors[pop]
                        totals["calibrated_capped_cost"] += capped * calibration_factors[pop]
                    cost = market_maps.get(f"sol_market_good_spending_{pop}_{good}", {}).get(mid, 0)
                    units[pop] += round(cost * 100000) * round(factor * 100000) // 100000
            units_by_market[mid] = units
        for row in rows:
            mid = int(row["market_id"])
            replay = sum(units_by_market[mid][pop] * round(number(row, f"population_{pop}") * 100000) // 100000 for pop in pops)
            saved = round(number(row, f"sol_location_{stratum}_base_spending") * 100000)
            error = abs(replay - saved)
            replay_max_error = max(replay_max_error, error)
            replay_nonzero += error > 0
        population = sum(number(row, f"population_{stratum}") for row in rows)
        net = sum(number(row, f"sol_location_{stratum}_net_income") for row in rows)
        funds = sum(number(row, f"sol_location_{stratum}_liquid_funds") for row in rows)
        saved_base = sum(number(row, f"sol_location_{stratum}_base_spending") for row in rows)
        full, available, cheap = (totals[key] for key in ("full_cost", "supplied_cost", "capped_cost"))
        assert 0 < cheap <= available <= full
        calibrated_full, calibrated_cheap = totals["calibrated_full_cost"], totals["calibrated_capped_cost"]
        assert abs(calibrated_full - population * median_net[stratum]) < 1e-8
        effective_savings = funds / net if net else 0
        representative_rows.append({
            "tag": tag, "stratum": stratum, "population_thousands": population,
            "monthly_net_per_1000": net / population, "monthly_funds_per_1000": funds / population,
            "matched_country_cache_monthly_net_per_1000": country_variables[cid][f"sol_ls_income_{stratum}"] / country_variables[cid][f"sol_ls_pop_{stratum}"],
            "funds_over_net": effective_savings, **totals,
            "missing_cost_percent": (1 - available / full) * 100,
            "cheap_remaining_cost_percent": (1 - cheap / available) * 100,
            "calibrated_missing_cost_percent": (1 - totals["calibrated_supplied_cost"] / calibrated_full) * 100,
            "calibrated_cheap_remaining_cost_percent": (1 - calibrated_cheap / totals["calibrated_supplied_cost"]) * 100,
            "missing_alpha_multiplier": full / available, "cheap_alpha_multiplier": available / cheap,
            "combined_alpha_multiplier": full / cheap,
            "saved_pp_percent": (funds / saved_base - 1) * 100,
            "old_neutral_pp_percent": (funds / cheap - 1) * 100,
            "calibrated_actual_net_fixed_snapshot_pp_percent": (funds / calibrated_cheap - 1) * 100,
            "hypothetical_median_net_neutral_savings_pp_percent": (calibrated_full / calibrated_cheap - 1) * 100,
            "hypothetical_median_net_saved_savings_pp_percent": (calibrated_full * effective_savings / calibrated_cheap - 1) * 100,
            "reference_income_index_percent": (net / population / median_net[stratum] - 1) * 100,
            "replay_max_error_1e5_units": replay_max_error, "replay_nonzero_locations": replay_nonzero,
            "replay_status": "exact" if replay_max_error == 0 else "not_a_synchronized_cost_replay",
        })

matched_country_medians = {}
for stratum in STRATA:
    samples = [(values[f"sol_ls_income_{stratum}"] / values[f"sol_ls_pop_{stratum}"], values[f"sol_ls_pop_{stratum}"])
               for cid, values in matched_country_income_samples.items()
               if cid in rows_by_country and values.get(f"sol_ls_pop_{stratum}", 0) > 0 and f"sol_ls_income_{stratum}" in values]
    matched_country_medians[stratum] = {
        "countries": len(samples), "population_thousands_at_solve": sum(weight for _, weight in samples),
        "country_equal_weight_median_monthly_per_1000": statistics.median(value for value, _ in samples),
        "population_weighted_country_median_monthly_per_1000": weighted_quantile(samples),
    }

result = {
    "save": STEM, "metadata": json.loads((BASE / "metadata.json").read_text(encoding="utf-8")),
    "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
    "income_statistics": income_stats, "head_full_unit_costs": full_unit_costs,
    "median_monthly_net_per_1000": median_net, "median_monthly_funds_per_1000": median_funds,
    "matched_country_net_income_medians": matched_country_medians,
    "country_equal_weight_calibration_factors_by_pop_type": {
        pop: matched_country_medians[pop_stratum[pop]]["country_equal_weight_median_monthly_per_1000"] / full_unit_costs[pop] for pop in POPS
    },
    "minimum_positive_unit_costs": minimum_positive_unit_costs,
    "owned_location_count": len(owned), "owned_country_count": len(rows_by_country),
    "calibration_factors_by_pop_type": calibration_factors,
    "representative_country_diagnostics": country_diagnostics,
    "owned_country_types": dict((kind, sum(country_types.get(cid) == kind for cid in rows_by_country)) for kind in set(country_types.values())),
    "representatives": representative_rows,
}
OUT.mkdir(exist_ok=True)
assert all(row["hypothetical_median_net_neutral_savings_pp_percent"] > 0 for row in representative_rows)
(OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
write_csv("country_net_income.csv", country_income_rows)
write_csv("representative_countries.csv", representative_rows)
print(json.dumps({key: result[key] for key in ("income_statistics", "calibration_factors_by_pop_type", "representative_country_diagnostics", "owned_country_types")}, ensure_ascii=False, indent=2))
for row in representative_rows:
    print(row["tag"], row["stratum"], "missing", round(row["missing_cost_percent"], 2),
          "cheap", round(row["cheap_remaining_cost_percent"], 2),
          "median-net-neutral-savings PP", round(row["hypothetical_median_net_neutral_savings_pp_percent"], 2),
          "replay error", row["replay_max_error_1e5_units"])
print("Wrote", OUT)

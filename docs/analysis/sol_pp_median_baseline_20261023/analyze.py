"""Calibrate four fixed basket scales to 1340 country purchasing-power medians."""
from __future__ import annotations

import csv
import json
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
START = "1340.04.01_autosave_c681faf6-91c6-45a9-bde4-9d8c22cd321e"
LATER = "SP_CAS_1406_01_23_de3601a2-b771-4e4e-a6bb-34fed262dca7"
OUT = ROOT / "data/save_analysis" / START / "purchasing_power_median_baseline"
STRATA = ("nobles", "clergy", "burghers", "commoners")
POPS = ("nobles", "clergy", "burghers", "laborers", "peasants", "soldiers")
POP_STRATUM = {pop: pop if pop in STRATA else "commoners" for pop in POPS}
TAGS = ("CAS", "FRA", "ENG", "VEN", "MAM", "CHI", "VIJ", "MAL", "TIM")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def number(row, key):
    return float(row.get(key) or 0)


def read_world(stem):
    base = ROOT / "data/save_analysis" / stem
    locations = read_csv(base / "locations.csv")
    countries = read_csv(base / "countries.csv")
    country_by_id = {row["owner_id"]: row for row in countries}
    grouped = defaultdict(lambda: defaultdict(lambda: {"funds": 0., "base": 0., "population": 0., "locations": 0}))
    for location in locations:
        if not location["owner_id"]:
            continue
        for stratum in STRATA:
            key = f"sol_location_{stratum}_base_spending"
            if location.get(key) in (None, ""):
                continue
            target = grouped[location["owner_id"]][stratum]
            target["funds"] += number(location, f"sol_location_{stratum}_liquid_funds")
            target["base"] += number(location, key)
            target["population"] += number(location, f"population_{stratum}")
            target["locations"] += 1
    samples = {s: [] for s in STRATA}
    for country_id, strata in grouped.items():
        country = country_by_id[country_id]
        for stratum, values in strata.items():
            if values["population"] <= 0 or values["base"] <= 0:
                continue
            assert values["funds"] >= 0
            samples[stratum].append({"country_id": country_id, "tag": country["owner_tag"],
                                     "stratum": stratum, **values, "alpha": values["funds"] / values["base"]})
    return samples, countries, json.loads((base / "metadata.json").read_text(encoding="utf-8"))


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


start, start_countries, start_metadata = read_world(START)
later, later_countries, later_metadata = read_world(LATER)
coefficients = {stratum: statistics.median(row["alpha"] for row in rows) for stratum, rows in start.items()}
start_summary, later_summary = {}, {}
all_country_rows = []
for stratum in STRATA:
    scale = coefficients[stratum]
    assert scale > 0
    start_normalized = [row["alpha"] / scale - 1 for row in start[stratum]]
    assert abs(statistics.median(start_normalized)) < 1e-12
    start_summary[stratum] = {
        "countries": len(start[stratum]), "zero_funds_countries": sum(row["funds"] == 0 for row in start[stratum]),
        "median_alpha": scale, "old_median_pp_percent": (scale - 1) * 100,
        "new_median_pp_percent": statistics.median(start_normalized) * 100,
        "basket_quantity_change_percent": (scale - 1) * 100,
    }
    later_alpha = statistics.median(row["alpha"] for row in later[stratum])
    later_summary[stratum] = {"countries": len(later[stratum]), "median_alpha": later_alpha,
                              "old_median_pp_percent": (later_alpha - 1) * 100,
                              "new_median_pp_percent": (later_alpha / scale - 1) * 100}
    for period, samples in (("1340", start[stratum]), ("1406", later[stratum])):
        for row in samples:
            all_country_rows.append({"period": period, **row, "baseline_scale": scale,
                                     "old_pp_percent": (row["alpha"] - 1) * 100,
                                     "new_pp_percent": (row["alpha"] / scale - 1) * 100})

table = {}
for row in read_csv(ROOT / "data/demand_price_table.csv"):
    if row["good"] in table:
        assert all(abs(number(row, key) - number(table[row["good"]], key)) < 1e-9 for key in ("price", *POPS))
    table[row["good"]] = row
basket_rows, quantity_rows = [], []
for pop in POPS:
    scale = coefficients[POP_STRATUM[pop]]
    old, ideal, rounded = 0., 0., 0.
    for good, row in table.items():
        price = number(row, "price")
        quantity = round(number(row, pop), 5)
        new_quantity = quantity * scale
        rounded_quantity = round(new_quantity, 5)
        assert (quantity > 0) == (rounded_quantity > 0), (pop, good, "positive member lost")
        old += quantity * price
        ideal += new_quantity * price
        rounded += rounded_quantity * price
        quantity_rows.append({"good": good, "pop_type": pop, "baseline_scale": scale,
                              "old_quantity": quantity, "ideal_new_quantity": new_quantity,
                              "rounded_5dp_quantity": rounded_quantity})
    assert abs(ideal - old * scale) < 1e-10
    basket_rows.append({"pop_type": pop, "stratum": POP_STRATUM[pop], "baseline_scale": scale,
                        "old_full_reference_cost": old, "ideal_new_full_reference_cost": ideal,
                        "rounded_new_full_reference_cost": rounded,
                        "rounding_budget_error_percent": (rounded / ideal - 1) * 100,
                        "quantity_change_percent": (scale - 1) * 100})

# Keep saved panel caches separate: the generated country UI reads gls_sol_*,
# which can be older than the current-territory sum. Never mix their numerators.
later_country_by_tag = {row["owner_tag"]: row for row in later_countries}
representatives = []
for tag in TAGS:
    country = later_country_by_tag[tag]
    for stratum in STRATA:
        sample = next(row for row in later[stratum] if row["tag"] == tag)
        scale = coefficients[stratum]
        panel_base_key, panel_funds_key = f"gls_sol_{stratum}_base", f"gls_sol_{stratum}_liquid"
        assert country.get(panel_base_key) not in (None, "") and number(country, panel_base_key) > 0, (tag, stratum)
        panel_alpha = number(country, panel_funds_key) / number(country, panel_base_key)
        old_pp = (sample["alpha"] - 1) * 100
        new_pp = (sample["alpha"] / scale - 1) * 100
        assert abs(new_pp - ((1 + old_pp / 100) / scale - 1) * 100) < 1e-9
        assert abs(new_pp - (sample["funds"] / (sample["base"] * scale) - 1) * 100) < 1e-9
        representatives.append({"tag": tag, "stratum": stratum, "baseline_scale": scale,
                                "funds_current_territory": sample["funds"], "base_current_territory": sample["base"],
                                "ideal_new_base_current_territory": sample["base"] * scale,
                                "old_current_territory_pp_percent": old_pp,
                                "new_current_territory_pp_percent": new_pp,
                                "saved_panel_funds": number(country, panel_funds_key), "saved_panel_base": number(country, panel_base_key),
                                "old_saved_panel_pp_percent": (panel_alpha - 1) * 100,
                                "new_saved_panel_pp_percent": (panel_alpha / scale - 1) * 100})

# Report sensitivity to the stale panel subset and the previous country solve.
cache_comparisons = {}
for stratum in STRATA:
    comparisons = {}
    for mode, funds_key, base_key in (
        ("saved_panel_subset", f"gls_sol_{stratum}_liquid", f"gls_sol_{stratum}_base"),
        ("saved_country_solve", f"sol_country_demand_target_{stratum}", f"sol_country_base_spending_{stratum}"),
    ):
        rows = [row for row in start_countries if number(row, f"population_{stratum}") > 0
                and row.get(funds_key) not in (None, "") and row.get(base_key) not in (None, "") and number(row, base_key) > 0]
        comparisons[mode] = {"countries": len(rows), "median_alpha": statistics.median(number(row, funds_key) / number(row, base_key) for row in rows)}
    cache_comparisons[stratum] = comparisons

result = {"method": "Equal-weight median of country sums of saved liquid funds / saved local baseline costs on current owned territory; zero funds retained; positive population and baseline required.",
          "start_save": START, "later_save": LATER, "start_metadata": start_metadata, "later_metadata": later_metadata,
          "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
          "baseline_coefficients": coefficients, "start_summary": start_summary, "later_summary": later_summary,
          "baskets": basket_rows, "representatives": representatives, "cache_sensitivity": cache_comparisons}
OUT.mkdir(exist_ok=True)
(OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
write_csv("country_power_samples.csv", all_country_rows)
write_csv("basket_reference_costs.csv", basket_rows)
write_csv("candidate_quantities.csv", quantity_rows)
write_csv("1406_representatives.csv", representatives)
print(json.dumps({key: result[key] for key in ("baseline_coefficients", "start_summary", "later_summary", "baskets")}, ensure_ascii=False, indent=2))
for tag in TAGS:
    rows = [row for row in representatives if row["tag"] == tag]
    print("CURRENT", tag, " | ".join(f"{row['old_current_territory_pp_percent']:+.1f}% -> {row['new_current_territory_pp_percent']:+.1f}%" for row in rows))
    print("PANEL", tag, " | ".join(f"{row['old_saved_panel_pp_percent']:+.1f}% -> {row['new_saved_panel_pp_percent']:+.1f}%" for row in rows))
print("Verified all four normalized 1340 medians are zero; wrote", OUT)

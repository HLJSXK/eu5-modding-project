"""Survey every country in every save for exact-solve feasibility.

Assumes the finest possible model: one independent nonnegative coefficient per
owned location. That is the theoretical upper bound on what any classification
can reach, so a country failing here can never be solved exactly by improving
the classifier.

Feasibility uses the runtime residual tolerance, |target_s| * 0.001 + 0.01
per stratum row, matching sol_country_demand_validate_class_residual.

Usage:
  python -m tools.eu5_save_parser.cone_survey <analysis_dir> [<analysis_dir> ...]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.eu5_save_parser.cone_feasibility import nnls  # noqa: E402
from tools.eu5_save_parser.demand_analysis import (  # noqa: E402
    DEFAULT_EPSILON,
    _read_inputs,
)

STRATA = ("nobles", "clergy", "burghers", "lower")


def row_tolerance(target_value: float) -> float:
    """Mirror the runtime per-row residual tolerance."""

    return abs(target_value) * 0.001 + 0.01


def classify_country(country, locations) -> dict:
    """Feasibility verdict for one country under the per-location model."""

    usable = [l for l in locations if sum(l.spending) > DEFAULT_EPSILON]
    target = list(country.target)
    baseline = list(country.baseline)
    if not usable:
        return {"status": "no_valid_locations"}
    if all(v <= DEFAULT_EPSILON for v in target):
        return {"status": "no_target"}
    if all(v <= DEFAULT_EPSILON for v in baseline):
        return {"status": "no_baseline"}

    vectors = [list(l.spending) for l in usable]
    _, residual = nnls(vectors, target)
    worst_ratio = 0.0
    feasible = True
    for index in range(4):
        limit = row_tolerance(target[index])
        if abs(residual[index]) > limit:
            feasible = False
        scale = abs(target[index]) or 1.0
        worst_ratio = max(worst_ratio, abs(residual[index]) / scale)
    scale_total = sum(abs(v) for v in target) or 1.0
    return {
        "status": "feasible" if feasible else "infeasible",
        "locations": len(usable),
        "l1_relative": sum(abs(v) for v in residual) / scale_total,
        "worst_row_relative": worst_ratio,
    }


def survey(analysis: Path) -> dict:
    countries, by_owner = _read_inputs(analysis)
    buckets: dict[str, int] = {}
    records = []
    for country in countries:
        verdict = classify_country(country, by_owner.get(country.owner_id, []))
        buckets[verdict["status"]] = buckets.get(verdict["status"], 0) + 1
        if verdict["status"] in {"feasible", "infeasible"}:
            records.append((country.owner_tag, verdict))
    return {"buckets": buckets, "records": records}


def report(name: str, result: dict, *, csv_writer=None) -> tuple[int, int]:
    buckets = result["buckets"]
    records = result["records"]
    scored = len(records)
    feasible = sum(1 for _, v in records if v["status"] == "feasible")
    print(f"\n{name}")
    print(f"  scored countries        : {scored}")
    if scored:
        print(
            f"  exact solve POSSIBLE    : {feasible} "
            f"({feasible / scored * 100:.1f}%)"
        )
        print(
            f"  exact solve IMPOSSIBLE  : {scored - feasible} "
            f"({(scored - feasible) / scored * 100:.1f}%)"
        )
        infeasible = sorted(
            (v["l1_relative"] for _, v in records if v["status"] == "infeasible")
        )
        if infeasible:
            mid = infeasible[len(infeasible) // 2]
            print(
                f"  infeasible residual     : median {mid:.4f}  "
                f"max {infeasible[-1]:.4f}"
            )
        by_size = {"1-9": [0, 0], "10-49": [0, 0], "50-199": [0, 0], "200+": [0, 0]}
        for _, verdict in records:
            count = verdict["locations"]
            key = (
                "1-9" if count < 10
                else "10-49" if count < 50
                else "50-199" if count < 200
                else "200+"
            )
            by_size[key][0] += 1
            if verdict["status"] == "feasible":
                by_size[key][1] += 1
        print("  by owned-location count :")
        for key, (total, ok) in by_size.items():
            if total:
                print(
                    f"    {key:>7}  {ok:>5}/{total:<5} feasible "
                    f"({ok / total * 100:5.1f}%)"
                )
    skipped = {k: v for k, v in buckets.items()
               if k not in {"feasible", "infeasible"}}
    if skipped:
        print(f"  skipped                 : {skipped}")
    if csv_writer:
        for tag, verdict in records:
            csv_writer.writerow({
                "save": name,
                "country": tag,
                "locations": verdict["locations"],
                "status": verdict["status"],
                "l1_relative": f"{verdict['l1_relative']:.6f}",
                "worst_row_relative": f"{verdict['worst_row_relative']:.6f}",
            })
    return feasible, scored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analyses", nargs="+", type=Path)
    parser.add_argument("--csv", type=Path, help="write a per-country CSV")
    args = parser.parse_args()

    handle = writer = None
    if args.csv:
        handle = args.csv.open("w", encoding="utf-8", newline="")
        writer = csv.DictWriter(handle, fieldnames=[
            "save", "country", "locations", "status",
            "l1_relative", "worst_row_relative",
        ])
        writer.writeheader()

    grand_ok = grand_total = 0
    for analysis in args.analyses:
        if not (analysis / "countries.csv").is_file():
            print(f"\n{analysis.name}: missing countries.csv, skipped")
            continue
        ok, total = report(analysis.name, survey(analysis), csv_writer=writer)
        grand_ok += ok
        grand_total += total

    if grand_total:
        print(f"\n{'=' * 58}\nALL SAVES: {grand_ok}/{grand_total} countries "
              f"({grand_ok / grand_total * 100:.1f}%) can be solved exactly")
        print("with one independent nonnegative coefficient per location.")
    if handle:
        handle.close()
        print(f"per-country CSV: {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

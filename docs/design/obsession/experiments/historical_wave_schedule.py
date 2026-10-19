"""Audit proposed historical-wave concurrency; no game scripts are generated."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def audit(data, envelope):
    first, end = data["game_start_year"], data["game_end_exclusive"]
    early = data["early_start_years"] if envelope else 0
    late = data["late_finish_years"] if envelope else 0
    by_year = {}
    for year in range(first, end):
        active = [wave for wave in data["waves"]
                  if wave["start"] - early <= year < wave["end"] + late]
        goods = [good for wave in active for good in wave["goods"]]
        assert len(set(goods)) == len(goods), (year, "overlapping waves for the same good", active)
        by_year[year] = {"waves": [wave["id"] for wave in active], "goods": sorted(goods)}
    goods_counts = [len(item["goods"]) for item in by_year.values()]
    wave_counts = [len(item["waves"]) for item in by_year.values()]
    goods_peak, wave_peak = max(goods_counts), max(wave_counts)
    intervals = []
    for year, active in by_year.items():
        if intervals and intervals[-1]["active_waves"] == active["waves"]:
            intervals[-1]["end_exclusive"] = year + 1
        else:
            intervals.append({"start": year, "end_exclusive": year + 1,
                              "historical_wave_count": len(active["waves"]),
                              "historical_goods_layers": len(active["goods"]),
                              "active_waves": active["waves"], "active_goods": active["goods"]})
    bands = []
    cuts = (first, 1400, 1500, 1600, 1700, 1800, end)
    for left, right in zip(cuts, cuts[1:]):
        counts = [len(by_year[year]["goods"]) for year in range(left, right)]
        bands.append({"start": left, "end_exclusive": right,
                      "mean_historical_goods_layers": round(sum(counts) / len(counts), 3),
                      "peak_historical_goods_layers": max(counts)})
    return {"historical_wave_peak": wave_peak,
            "historical_goods_peak": goods_peak,
            "historical_goods_layer_years": sum(goods_counts),
            "goods_peak_with_generic_layer": goods_peak + data["generic_goods_layers"],
            "historical_wave_mean": round(sum(wave_counts) / len(by_year), 3),
            "historical_goods_mean": round(sum(goods_counts) / len(by_year), 3),
            "years_by_historical_goods_count": {
                str(count): years for count, years in sorted(Counter(goods_counts).items())
            },
            "peak_goods_intervals": [item for item in intervals if item["historical_goods_layers"] == goods_peak],
            "bands": bands, "intervals": intervals}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path,
                        default=Path(__file__).with_suffix(".json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.schedule.read_text(encoding="utf-8"))
    waves = data["waves"]
    assert len({wave["id"] for wave in waves}) == len(waves)
    assert all(data["game_start_year"] <= wave["start"] < wave["end"] <= data["game_end_exclusive"]
               for wave in waves)
    assert all(wave["goods"] and len(set(wave["goods"])) == len(wave["goods"]) for wave in waves)
    durations = [{"id": wave["id"], "nominal_years": wave["end"] - wave["start"],
                  "envelope_years": min(data["game_end_exclusive"], wave["end"] + data["late_finish_years"])
                  - max(data["game_start_year"], wave["start"] - data["early_start_years"])}
                 for wave in waves]
    if "max_runtime_years" in data:
        assert all(item["envelope_years"] <= data["max_runtime_years"] for item in durations), durations
    result = {"evidence_scope": data["evidence_scope"],
              "interval_convention": "[start, end), annual resolution; game ends during 1836",
              "wave_count": len(waves),
              "wave_durations": durations,
              "maximum_envelope_years": max(item["envelope_years"] for item in durations),
              "distinct_historical_goods": sorted({good for wave in waves for good in wave["goods"]}),
              "nominal": audit(data, False), "early_and_late_envelope": audit(data, True)}
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

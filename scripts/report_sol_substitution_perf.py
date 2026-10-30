"""Read country substitution diagnostics from one or two plaintext EU5 saves.

Only metadata scalars and country records are scanned through a read-only mmap;
population/location data is never deserialized. Counters are cumulative within
the current enabled diagnostic period, so frequency requires two ordered saves.
"""
from __future__ import annotations

import argparse
import csv
import json
import mmap
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.eu5_save_parser.parser import (  # noqa: E402
    SAVE_HEADER,
    SaveFormatError,
    _COUNTRY_RECORD_RE,
    _metadata_scalar,
    _parse_country_tags,
    _top_level_bounds,
    decode_jomini_fixed_point,
)

PREFIX = "sol_sub_perf_"
STRATEGY = "sol_country_demand_selected_strategy"
CONTROL = "sol_sub_perf_human"
REASONS = {
    1: "初始化/开关/控制",
    2: "领土数量/归属",
    3: "市场变化",
    4: "市场支出缓存缺失",
    5: "自身商品修正缺失",
    6: "外部商品修正变化",
    7: "实际SOL修正相对上次读取漂移",
}
DETAIL_NAMES = (
    "dirty_reason", "dirty_good", "old_total", "new_total",
    "cached_own", "actual_own", "external_now",
)
VARIABLE_RE = re.compile(
    rb"(?m)^\t{4}flag=(sol_sub_perf_[A-Za-z0-9_]+|"
    rb"sol_country_demand_selected_strategy)\r?$"
    rb"\n\t{4}data=\{\r?$"
    rb"\n\t{5}type=value\r?$"
    rb"(?:\n\t{5}identity=(\d+)\r?$)?"
)


@dataclass
class Snapshot:
    label: str
    date: str | None
    playthrough_id: str | None
    tags: dict[int, str]
    variables: dict[int, dict[str, float]]


def read_snapshot(path: Path) -> Snapshot:
    """Reuse the targeted save parser's record layout and fixed-point decoder."""
    with path.open("rb") as stream:
        if stream.read(3) != SAVE_HEADER:
            raise SaveFormatError("需要 SAV 开头的未压缩文本 debug 存档")
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
            metadata_bounds = _top_level_bounds(view, "metadata")
            date = _metadata_scalar(view, *metadata_bounds, "date")
            playthrough = _metadata_scalar(view, *metadata_bounds, "playthrough_id")
            countries_start, countries_end = _top_level_bounds(view, "countries")
            tags = _parse_country_tags(view, countries_start, countries_end)
            # EU5's database country records use column-zero numeric headers.
            # As in parse_save(), the next population section bounds the scan.
            try:
                countries_end = _top_level_bounds(view, "population")[0]
            except SaveFormatError:
                pass
            database_start = view.find(b"\n\tdatabase={", countries_start, countries_end)
            if database_start < 0:
                raise SaveFormatError("countries.database 未找到")
            variables: dict[int, dict[str, float]] = {}
            records = _COUNTRY_RECORD_RE.finditer(view, database_start, countries_end)
            previous = next(records, None)

            def read_record(match: re.Match[bytes], end: int) -> None:
                country_id = int(match.group(1))
                if country_id not in tags:
                    return
                values = {}
                for item in VARIABLE_RE.finditer(view, match.start(), end):
                    identity = int(item.group(2)) if item.group(2) else 0
                    values[item.group(1).decode("ascii")] = decode_jomini_fixed_point(identity)
                # Retain records without counters so missing coverage stays visible.
                variables[country_id] = values

            if previous is not None:
                for current in records:
                    read_record(previous, current.start())
                    previous = current
                read_record(previous, countries_end)
    return Snapshot(path.name, date, playthrough, tags, variables)


def core_goods() -> list[str]:
    with (ROOT / "data/goods_weights.csv").open(encoding="utf-8-sig", newline="") as stream:
        return sorted({row["good"] for row in csv.DictReader(stream)})


def has_counters(values: dict[str, float]) -> bool:
    return any(PREFIX + name in values for name in ("refresh_count", "dirty_count"))


def counts(values: dict[str, float]) -> dict[str, float]:
    # A missing dirty counter means no dirty events only AFTER instrumentation
    # is known to exist. Never call this to convert an uninstrumented save to 0.
    return {name: values.get(PREFIX + name + "_count", 0) for name in ("refresh", "dirty")}


def details(values: dict[str, float], goods: list[str]) -> dict:
    result = {name: values.get(PREFIX + name) for name in DETAIL_NAMES}
    reason = result["dirty_reason"]
    result["reason_label"] = REASONS.get(reason, "未知" if reason is not None else "未记录")
    good = result["dirty_good"]
    index = int(good) if good is not None else 0
    result["good"] = goods[index - 1] if good == index and 1 <= index <= len(goods) else None
    result["strategy"] = values.get(STRATEGY)
    result["control"] = {0: "AI", 1: "human"}.get(values.get(CONTROL), "unknown")
    return result


def summarize(snapshot: Snapshot) -> dict:
    values = snapshot.variables.values()
    covered = [item for item in values if has_counters(item)]
    reasons = Counter(item.get(PREFIX + "dirty_reason") for item in covered
                      if item.get(PREFIX + "dirty_count", 0) > 0)
    strategies = Counter(item[STRATEGY] for item in values if STRATEGY in item)
    known = sum(strategies.values())
    return {
        "save": snapshot.label,
        "date": snapshot.date,
        "country_records": len(snapshot.variables),
        "diagnostic_variable_countries": sum(any(name.startswith(PREFIX) for name in item)
                                            for item in values),
        "counter_covered_countries": len(covered),
        "counter_missing_countries": len(snapshot.variables) - len(covered),
        "refresh_count_total": sum(counts(item)["refresh"] for item in covered) if covered else None,
        "dirty_count_total": sum(counts(item)["dirty"] for item in covered) if covered else None,
        "latest_dirty_reason_countries": [
            {"reason": reason, "label": REASONS.get(reason, "未记录/未知"), "countries": count}
            for reason, count in sorted(reasons.items(), key=lambda pair: (-pair[1], str(pair[0])))
        ],
        "strategy_cache": {
            "variable": STRATEGY,
            "known_countries": known,
            "missing_countries": len(snapshot.variables) - known,
            "strategy8_countries": strategies[8],
            "strategy8_share_of_known": strategies[8] / known if known else None,
            "distribution": {str(int(key)): count for key, count in sorted(strategies.items())},
        },
        "warning": None if covered else "没有本轮诊断变量，不能判定当前AI重算频率",
    }


def compare(before: Snapshot, after: Snapshot, goods: list[str]) -> dict:
    rows = []
    for country_id in sorted(before.variables.keys() | after.variables.keys()):
        old = before.variables.get(country_id)
        new = after.variables.get(country_id)
        row = {"id": country_id, "tag": after.tags.get(country_id, before.tags.get(country_id)),
               "refresh_delta": None, "dirty_delta": None, "control": "unknown"}
        if new is not None:
            row.update(details(new, goods))
        if old is None:
            row["status"] = "new_country"
        elif new is None:
            row["status"] = "removed_country"
        elif before.tags[country_id] != after.tags[country_id]:
            row["status"] = "tag_changed_or_id_reused"
            row["previous_tag"] = before.tags[country_id]
        elif not has_counters(old) and not has_counters(new):
            row["status"] = "no_diagnostics"
        elif not has_counters(old):
            row["status"] = "new_diagnostics"
        elif not has_counters(new):
            row["status"] = "diagnostics_cleared"
        else:
            old_counts, new_counts = counts(old), counts(new)
            if any(new_counts[name] < old_counts[name] for name in old_counts):
                row["status"] = "counter_reset"
                row["before_counts"], row["after_counts"] = old_counts, new_counts
            else:
                row["status"] = "comparable"
                row["refresh_delta"] = new_counts["refresh"] - old_counts["refresh"]
                row["dirty_delta"] = new_counts["dirty"] - old_counts["dirty"]
        rows.append(row)
    status_counts = Counter(row["status"] for row in rows)
    comparable = [row for row in rows if row["status"] == "comparable"]
    top = sorted((row for row in comparable if row["refresh_delta"] or row["dirty_delta"]),
                 key=lambda row: (-row["refresh_delta"], -row["dirty_delta"], row["id"]))[:20]
    by_control = {
        control: {
            "comparable_countries": sum(row["control"] == control for row in comparable),
            "refresh_delta_total": sum(row["refresh_delta"] for row in comparable if row["control"] == control),
            "dirty_delta_total": sum(row["dirty_delta"] for row in comparable if row["control"] == control),
        }
        for control in ("AI", "human", "unknown")
    }
    return {
        "status_countries": dict(status_counts),
        "comparable_countries": len(comparable),
        "refresh_delta_total": sum(row["refresh_delta"] for row in comparable) if comparable else None,
        "dirty_delta_total": sum(row["dirty_delta"] for row in comparable) if comparable else None,
        "delta_by_control": by_control,
        "top20_refresh_countries": top,
        "noncomparable_countries": [row for row in rows if row["status"] not in {"comparable", "no_diagnostics"}],
        "warning": None if comparable else "没有可比较的本轮计数，不能判定两档之间的AI重算频率",
    }


def make_report(snapshots: list[Snapshot]) -> dict:
    report = {
        "snapshots": [summarize(snapshot) for snapshot in snapshots],
        "notes": ["计数为本轮启用期间累计；单档不能表示每月频率。",
                  "dirty 原因是每国最后一次事件的首个原因；不是历次事件原因分布。",
                  "策略 8 占比来自当前策略缓存；不是累计 sweep 次数。",
                  "AI/human 按较晚存档的控制快照分类；无快照归 unknown，玩家月度刷新不表示 AI 异常。",
                  "清理后重启且新计数追平旧计数无法仅凭两档识别，比较档间应保持替代开关启用。"],
    }
    if len(snapshots) == 2:
        before, after = snapshots
        if before.playthrough_id and after.playthrough_id and before.playthrough_id != after.playthrough_id:
            raise ValueError("两个存档来自不同 playthrough，不能按国家 ID 比较")
        if before.date and after.date:
            try:
                ordered = tuple(map(int, before.date.split("."))) <= tuple(map(int, after.date.split(".")))
            except ValueError:
                ordered = True
            if not ordered:
                raise ValueError("存档顺序倒置；请先给较早的存档，再给较晚的存档")
        report["comparison"] = compare(before, after, core_goods())
    return report


def print_report(report: dict) -> None:
    for item in report["snapshots"]:
        print(f"{item['save']} | 日期 {item['date'] or '未知'} | 国家记录 {item['country_records']}")
        print(f"  本轮计数覆盖 {item['counter_covered_countries']}/{item['country_records']}；"
              f"含诊断变量 {item['diagnostic_variable_countries']} 国")
        if item["warning"]:
            print("  " + item["warning"])
        else:
            print(f"  累计刷新 {item['refresh_count_total']:g}；累计 dirty {item['dirty_count_total']:g}")
            reason_text = "；".join(f"{row['label']}={row['countries']}国"
                                   for row in item["latest_dirty_reason_countries"])
            print("  最后 dirty 原因（国家数）：" + (reason_text or "尚未记录 dirty"))
        strategy = item["strategy_cache"]
        share = strategy["strategy8_share_of_known"]
        percentage = f" ({share:.1%})" if share is not None else "（无法计算占比）"
        print(f"  当前策略8 {strategy['strategy8_countries']}/{strategy['known_countries']} 已知缓存国家"
              f"{percentage}；缺缓存 {strategy['missing_countries']} 国")
    diff = report.get("comparison")
    if diff:
        print("两档差分：" + "；".join(f"{key}={count}国" for key, count in diff["status_countries"].items()))
        if diff["warning"]:
            print("  " + diff["warning"])
        else:
            print(f"  可比国家新增刷新 {diff['refresh_delta_total']:g}；新增 dirty {diff['dirty_delta_total']:g}")
            print("  按控制快照：" + "；".join(
                f"{control}={group['comparable_countries']}国 刷新+{group['refresh_delta_total']:g} dirty+{group['dirty_delta_total']:g}"
                for control, group in diff["delta_by_control"].items()))
            print("  Top20（最后 dirty 详情；不代表档间所有事件原因）：")
            for row in diff["top20_refresh_countries"]:
                print(f"    {row['tag']}#{row['id']} [{row['control']}]: 刷新+{row['refresh_delta']:g} dirty+{row['dirty_delta']:g}"
                      f" | {row['reason_label']} | good={row['good'] or '-'}"
                      f" | total={row['old_total']}->{row['new_total']}"
                      f" own={row['cached_own']}/{row['actual_own']} external={row['external_now']}")
        noncomparable = diff["noncomparable_countries"]
        if noncomparable:
            print("  不作差分：" + "；".join(f"{row['tag']}#{row['id']}={row['status']}" for row in noncomparable[:20]))
            if len(noncomparable) > 20:
                print(f"  另有 {len(noncomparable) - 20} 国，完整列表可用 --output JSON 查看")
    print("注：" + " ".join(report["notes"]))


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("saves", nargs="+", type=Path, metavar="SAVE", help="一个存档，或按时间排序的两个存档")
    cli.add_argument("--output", "-o", type=Path, help="将报告另存为 JSON")
    args = cli.parse_args(argv)
    if len(args.saves) not in (1, 2):
        cli.error("需要一个或两个存档")
    if args.output and args.output.resolve() in {path.resolve() for path in args.saves}:
        cli.error("JSON 输出不能覆盖输入存档")
    try:
        report = make_report([read_snapshot(path) for path in args.saves])
        print_report(report)
        if args.output:
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, SaveFormatError, ValueError) as error:
        message = str(error) if not isinstance(error, OSError) else error.strerror or type(error).__name__
        print(f"诊断报告失败：{message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

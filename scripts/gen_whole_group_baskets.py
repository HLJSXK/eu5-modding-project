#!/usr/bin/env python3
"""Migrate calibrated baskets once; validate explicit whole-group subscriptions."""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
POPS = ("nobles", "clergy", "burghers", "laborers", "peasants", "soldiers", "tribesmen")
QUANTUM = Decimal("0.00001")
GROUPS: dict[str, list[str]] = {}
with (ROOT / "data/goods_weights.csv").open(encoding="utf-8-sig", newline="") as handle:
    for row in csv.DictReader(handle):
        GROUPS.setdefault(row["group"], []).append(row["good"])
CORE = sorted({good for members in GROUPS.values() for good in members})


def load_subscriptions(path: Path = ROOT / "data/pop_group_baskets.csv") -> dict[str, list[str]]:
    subscribed = {pop: [] for pop in POPS}
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["group", *POPS]:
            raise ValueError(f"{path}: expected group and all seven pop columns")
        for row in reader:
            group = row["group"]
            if group not in GROUPS or group in seen:
                raise ValueError(f"{path}: unknown or duplicate group {group}")
            seen.add(group)
            for pop in POPS:
                if row[pop] not in ("0", "1"):
                    raise ValueError(f"{group}/{pop}: subscription must be 0 or 1")
                if row[pop] == "1":
                    subscribed[pop].append(group)
    if seen != set(GROUPS):
        raise ValueError(f"{path}: missing groups {sorted(set(GROUPS) - seen)}")
    return subscribed


SUBSCRIBED = load_subscriptions()


def groups_for_pop(pop: str, removed_goods=()) -> dict[str, list[str]]:
    removed = set(removed_goods)
    if removed - set(CORE):
        raise ValueError(f"Unknown target-level removals: {sorted(removed - set(CORE))}")
    return {group: [good for good in GROUPS[group] if good not in removed]
            for group in SUBSCRIBED[pop]}


def validate_baskets(quantities, *, removed_goods=(), label="basket") -> None:
    """Core consumption must equal the union of subscribed, target-level groups."""
    errors = []
    for pop in POPS:
        expected = {good for members in groups_for_pop(pop, removed_goods).values() for good in members}
        for good in CORE:
            if good not in quantities or pop not in quantities[good]:
                errors.append(f"{good}/{pop}: missing quantity")
                continue
            value = Decimal(str(quantities[good][pop]))
            if value.is_finite():
                value = value.quantize(Decimal("0.000000000001"))
            if not value.is_finite() or value < 0:
                errors.append(f"{good}/{pop}: invalid quantity {value}")
            elif good in expected and value < QUANTUM:
                errors.append(f"{good}/{pop}: subscribed member must be >= {QUANTUM}, got {value}")
            elif good not in expected and value != 0:
                errors.append(f"{good}/{pop}: quantity {value} outside subscribed groups")
    if errors:
        raise ValueError(f"{label}: whole-group basket violation\n" + "\n".join(errors))


def read_quantities(path: Path):
    quantities, prices = {}, {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            # Remove binary-float CSV noise, retaining half-quantum vanilla nets.
            values = {pop: Decimal(row[pop]).quantize(Decimal("0.000000000001")) for pop in POPS}
            good = row["good"]
            if good in quantities and quantities[good] != values:
                raise ValueError(f"{path}: duplicate quantities disagree for {good}")
            quantities[good] = values
            if "price" in row:
                prices[good] = Decimal(row["price"])
    return quantities, prices


def validate_target(target_rows) -> None:
    validate_baskets({row.good: row.demand for row in target_rows}, label="target_demand.csv")


def validate_net_targets(target_rows, vanilla_net) -> None:
    """A five-decimal INJECT delta must reproduce the stored net target."""
    from gen_pop_goods import _derive_inject_add
    for row in target_rows:
        delta = _derive_inject_add(row, vanilla_net)
        for pop in POPS:
            actual = vanilla_net.get(row.good, {}).get(pop, 0) + delta.get(pop, 0)
            if abs(actual - row.demand[pop]) > 1e-12:
                raise ValueError(f"{row.good}/{pop}: net target {row.demand[pop]} cannot be emitted ({actual})")


def round_component(ideal, prices, budget, vanilla):
    """Price-weighted largest remainders on the emitted net-quantity lattice.

    Shared goods connect groups: round their combined allocations once so they
    are neither charged nor rounded twice. Positive minimums take precedence.
    """
    rounded, remainders = {}, {}
    for good, value in ideal.items():
        offset = vanilla[good] % QUANTUM
        floor = offset + ((value - offset) / QUANTUM).to_integral_value(rounding=ROUND_FLOOR) * QUANTUM
        rounded[good] = max(floor, QUANTUM if offset == 0 else offset + QUANTUM)
        remainders[good] = (value - rounded[good]) / QUANTUM
    spending = sum(rounded[good] * prices[good] for good in rounded)
    for good in sorted(rounded, key=lambda good: (-remainders[good], good)):
        unit = QUANTUM * prices[good]
        if remainders[good] > 0 and abs(spending + unit - budget) < abs(spending - budget):
            rounded[good] += QUANTUM
            spending += unit
    return rounded, spending - budget


def migrate(quantities, prices, vanilla_net):
    result = {good: dict(values) for good, values in quantities.items()}
    for pop in POPS:
        groups = groups_for_pop(pop)
        counts = Counter(good for members in groups.values() for good in members)
        allocated = dict.fromkeys(counts, Decimal(0))
        budgets = {}
        for group, members in groups.items():
            old = {good: quantities[good][pop] * prices[good] / counts[good]
                   for good in members if quantities[good][pop] > 0}
            budget = sum(old.values(), Decimal(0))
            if not old:
                raise ValueError(f"{pop}/{group}: no baseline budget; set a calibrated budget first")
            budgets[group] = budget
            parts = {good: old.get(good, budget / len(old)) for good in members}
            scale = budget / sum(parts.values())
            print(f"[budget] {pop}/{group}: {budget:.8f} -> {sum(v * scale for v in parts.values()):.8f} (before rounding)")
            for good, part in parts.items():
                allocated[good] += part * scale / prices[good]
        # Connected groups share a good's single final quantity and rounding.
        remaining = set(counts)
        while remaining:
            component = {min(remaining)}
            while True:
                expanded = component | {good for members in groups.values() if component.intersection(members) for good in members}
                if expanded == component:
                    break
                component = expanded
            budget = sum(budgets[group] for group, members in groups.items() if component.intersection(members))
            vanilla = {good: Decimal(f"{vanilla_net[good][pop]:.12f}") for good in component}
            rounded, error = round_component({good: allocated[good] for good in sorted(component)}, prices, budget, vanilla)
            print(f"[rounding] {pop}/{' + '.join(g for g, m in groups.items() if component.intersection(m))}: budget error {error:+.8f}")
            for good, value in rounded.items():
                result[good][pop] = value
            remaining -= component
        for good in set(CORE) - set(counts):
            result[good][pop] = Decimal(0)
    validate_baskets(result, label="migrated basket")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fill", action="store_true", help="One-time budget-preserving migration from current net demand table")
    mode.add_argument("--check", action="store_true", help="Validate calibrated whole-group baskets without writing")
    args = parser.parse_args()
    from gen_pop_goods import TARGET_CSV, _load_target_csv, _write_target_csv, _compute_vanilla_net
    rows = _load_target_csv(TARGET_CSV)
    vanilla = _compute_vanilla_net()
    if args.fill:
        try:
            validate_target(rows)
        except ValueError:
            old, prices = read_quantities(ROOT / "data/demand_price_table.csv")
            new = migrate(old, prices, vanilla)
            for row in rows:
                for pop in POPS:
                    value = float(new[row.good][pop])
                    if abs(value - row.demand[pop]) > 1e-12:
                        print(f"[quantity] {row.good}/{pop}: {row.demand[pop]:g} -> {value:g}")
                    row.demand[pop] = value
            validate_net_targets(rows, vanilla)
            _write_target_csv(rows, TARGET_CSV)
        else:
            print("[OK] Already migrated; --fill leaves calibrated quantities unchanged")
    validate_target(rows)
    validate_net_targets(rows, vanilla)
    print("[OK] Whole-group subscriptions and emittable net quantities")


if __name__ == "__main__":
    main()

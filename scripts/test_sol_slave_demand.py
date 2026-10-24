#!/usr/bin/env python3
"""Resolve shipped goods and verify slaves never have a purchasing basket."""

import csv
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gen_sol_jtg_compat as jtg
import gen_sol_mnt_compat as mnt
import gen_sol_pp_compat as pp
from gen_pop_goods import (
    _compute_vanilla_net, _load_target_csv, _load_vanilla_thresholds,
    generate_inject_file, TARGET_CSV,
    _vanilla_goods_ordered,
)

ROOT = Path(__file__).resolve().parents[1]
VANILLA = ROOT / ".eu5-base/reference_game_files/game/in_game/common/goods"


def definitions(root):
    return {block.key: mnt._final_pop_demand(block.body)
            for block in mnt._blocks_in_tree(root)}


def inject(goods, blocks):
    for block in blocks:
        if block.operation not in {"INJECT", "TRY_INJECT"}:
            raise AssertionError(f"Expected injection: {block.key}")
        if mnt._simple_block_values(block.body, "demand_multiply"):
            raise AssertionError(f"Unexpected injected multiplier: {block.key}")
        delta = mnt._final_pop_demand(block.body)
        for pop_type in mnt.ALL_POP_TYPES:
            goods[block.key][pop_type] += delta[pop_type]
    return goods


def base_goods(target="stable"):
    return inject(definitions(VANILLA), mnt._blocks_in_tree(
        ROOT / "src" / target / "in_game/common/goods"))


class SlaveDemandTests(unittest.TestCase):
    def assert_no_slave_demand(self, goods):
        for good, demand in goods.items():
            with self.subTest(good=good):
                self.assertEqual(demand["slaves"], Decimal(0))

    def test_both_base_targets_zero_slaves_preserve_income_baskets(self):
        with TARGET_CSV.open(encoding="utf-8-sig", newline="") as handle:
            targets = list(csv.DictReader(handle))
        for target in ("stable", "sol_standalone"):
            with self.subTest(target=target):
                goods = base_goods(target)
                self.assertEqual(len(goods), 75)
                self.assert_no_slave_demand(goods)
                for row in targets:
                    for pop_type in mnt.POP_TYPES:
                        self.assertEqual(goods[row["good"]][pop_type], Decimal(row[pop_type]))

    def test_goods_outside_calibrated_csv_still_cancel_slave_demand(self):
        rows = _load_target_csv(TARGET_CSV)
        vanilla = _compute_vanilla_net()
        extra = {pt: 0.25 for pt in mnt.ALL_POP_TYPES}
        vanilla["new_good"] = extra
        with patch("gen_pop_goods._vanilla_goods_ordered", return_value=[
            *_vanilla_goods_ordered(), ("new_good", "raw_materials"),
        ]):
            text = generate_inject_file(rows, vanilla, _load_vanilla_thresholds())
        source = definitions(VANILLA)
        source["new_good"] = {pt: Decimal("0.25") for pt in mnt.ALL_POP_TYPES}
        goods = inject(source, mnt._parse_top_level_blocks(text, Path("generated")))
        self.assert_no_slave_demand(goods)
        for pop_type in mnt.POP_TYPES:
            self.assertEqual(goods["new_good"][pop_type], Decimal("0.25"))

    def test_pp_stacking_cancels_lumber_exactly_and_victuals_has_no_slaves(self):
        goods = base_goods()
        goods.update({b.key: mnt._final_pop_demand(b.body)
                      for b in mnt._blocks_in_file(pp.PP_VICTUALS_FILE)})
        inject(goods, mnt._blocks_in_file(pp.PP_LUMBER_FILE))
        inject(goods, mnt._blocks_in_tree(pp.TARGET_ROOT / "in_game/common/goods"))
        self.assert_no_slave_demand(goods)

    def test_mnt_replacements_and_unmodified_goods_have_no_slave_demand(self):
        goods = definitions(VANILLA)
        goods.update(definitions(mnt.MNT_GOODS_ROOT))
        goods.update(definitions(mnt.TARGET_ROOT / "in_game/common/goods"))
        self.assert_no_slave_demand(goods)

    def test_jtg_all_goods_including_excluded_goods_have_no_slave_demand(self):
        rows = jtg._load_rows()
        workshop = ROOT / ".eu5-base/reference_mods"
        jtg._audit_workshop(workshop, rows)
        goods = base_goods()
        goods.update(definitions(workshop / jtg.JUST_GOODS_WORKSHOP_ID / "in_game/common/goods"))
        inject(goods, mnt._blocks_in_file(jtg.GOODS_OUTPUT))
        self.assert_no_slave_demand(goods)
        for row in rows:
            for pop_type, expected in jtg._target_quantities(row).items():
                self.assertLessEqual(
                    abs(goods[row["good"]][pop_type] - Decimal(str(expected))),
                    Decimal("0.000005"),  # Existing JTG five-decimal injection rounding.
                )


if __name__ == "__main__":
    unittest.main()

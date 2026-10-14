#!/usr/bin/env python3
"""Regression checks for sheet C balances and the preserved F goods tiers.

This source/AST check prevents retired dials and population charts returning,
protects the three balance values and signed scale, and preserves all goods
memberships without requiring a running game. The legacy filename is kept for
existing tooling; the current spec is sheet C balances with F goods tiers.
"""
from __future__ import annotations

import csv
import os
import re
import sys
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("PyYAML is required to run test_sol_ui_f_route.py") from exc

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ai_gui_assessment" / "renderer"))
from pdx import Node, parse  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from sol_goods_order import GROUP_ORDER  # noqa: E402


def load_spec() -> dict:
    with (ROOT / "data" / "sol_ui_f_spec.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def walk(nodes: list[Node]):
    for node in nodes:
        yield node
        if node.is_block():
            yield from walk(node.value)


def node_name(node: Node) -> str:
    """Return a source node's type name, including barslice variants."""
    return node.key.split(":", 1)[-1]


def node_size(text: str, size: list[int]) -> bool:
    width, height = size
    return re.search(rf"size\s*=\s*\{{\s*{width}\s+{height}\s*\}}", text) is not None


def goods_memberships(path: Path) -> list[tuple[str, str]]:
    """Read grouped goods from the parsed GUI, preserving source order."""
    memberships: list[tuple[str, str]] = []

    def visit(nodes: list[Node], group: str | None = None) -> None:
        current = group
        for node in nodes:
            name = node_name(node)
            if name == "sol_group_label" and isinstance(node.value, list):
                text_nodes = [child for child in node.value if node_name(child) == "text"]
                if text_nodes and isinstance(text_nodes[0].value, str):
                    label = text_nodes[0].value
                    current = label.removeprefix("SOL_SUBGROUP_").lower()
            elif name == "tooltip" and isinstance(node.value, str):
                match = re.match(r"@([^!]+)!", node.value)
                if match and current:
                    memberships.append((current, match.group(1)))
            if node.is_block():
                visit(node.value, current)

    visit(parse(path.read_text(encoding="utf-8-sig"), str(path)))
    return memberships


def expected_memberships(path: Path) -> list[tuple[str, str]]:
    # The CSV is the membership source, while sol_goods_order.py owns the UI
    # group order.  This preserves every overlapping membership without making
    # the test depend on incidental CSV group interleaving.
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [(row["group"].strip(), row["good"].strip()) for row in csv.DictReader(handle)]
    members = {group: [good for g, good in rows if g == group] for group in GROUP_ORDER}
    return [(group, good) for group in GROUP_ORDER for good in members[group]]


class SOLFRoute(unittest.TestCase):
    def test_gui_consumption_is_raw_only(self):
        forbidden = ("SOL_F_APPLIED_COEF", "local_sol_pop_demand_modifier_size",
                     "local_sol_pop_demand_scale", "gls_country_final_demand_scale",
                     "sol_location_final_demand_scale", "sol_country_class_coefficient")
        for target in ('stable', 'sol_standalone', 'sol_pp_compatibility_submod', 'sol_jtg_compatibility_submod'):
            for path in (ROOT / 'src' / target / 'in_game/gui').rglob('*.gui'):
                source = path.read_text(encoding='utf-8-sig')
                for binding in forbidden:
                    self.assertNotIn(binding, source, str(path))
        from gen_sol_ls_gui import render_tooltip, render_panel, _goods_names, f_coef, LOC, COUNTRY
        for source, scope, prefix in ((render_tooltip(_goods_names()), LOC, 'local_sol'),
                                      (render_panel(_goods_names()), COUNTRY, 'gls_country')):
            balance = f_coef(scope, prefix + '_liquid_funds_display', prefix + '_base_spending_display')
            self.assertIn(f'[{balance}|+=1%]', source)

    @classmethod
    def setUpClass(cls):
        cls.spec = load_spec()
        cls.surface_spec = cls.spec["surfaces"]

    def _surface_paths(self, kind: str) -> list[Path]:
        config = self.surface_spec[kind]
        return [ROOT / config["gui"], ROOT / config["standalone_gui"]]

    def test_design_reference_exists(self):
        self.assertTrue((ROOT / self.spec["evidence"]["balance_reference"]).exists())
        self.assertEqual(self.spec["consumption_display"], "raw_location_alpha_only")

    def test_balance_surface_structure_and_order(self):
        markers = self.surface_spec["markers"]
        banned = set(self.surface_spec["banned_nodes"])
        for kind in ("location", "country"):
            config = self.surface_spec[kind]
            for path in self._surface_paths(kind):
                with self.subTest(surface=kind, path=path):
                    text = path.read_text(encoding="utf-8-sig")
                    nodes = list(walk(parse(text, str(path))))
                    names = [node_name(node) for node in nodes]
                    self.assertFalse(banned.intersection(names), sorted(banned.intersection(names)))
                    self.assertNotIn("dial.dds", text)
                    self.assertNotIn("bar_steel.dds", text)
                    positions = [text.find(markers["overall_balance"]),
                                 text.find(markers["estate_balances"]),
                                 text.find(config["goods_marker"])]
                    self.assertTrue(all(position >= 0 for position in positions))
                    self.assertEqual(positions, sorted(positions))
                    for key in ("overall_row", "estate_row", "overall_bar", "estate_bar"):
                        self.assertTrue(node_size(text, config[key]), f"missing {key}")
                    for name in ("sol_balance_value", "sol_balance_funds", "sol_balance_baseline",
                                 "sol_balance_negative", "sol_balance_positive"):
                        count = sum(1 for node in nodes if node_name(node) == "name" and node.value == name)
                        self.assertEqual(count, self.surface_spec["balance_rows"], name)
                    for label in self.surface_spec["scale_labels"]:
                        self.assertEqual(text.count(f'raw_text = "{label}"'), self.surface_spec["balance_rows"])
                    for estate in ("NOBLES","CLERGY","BURGHERS","COMMONERS","TRIBESMEN"):
                        self.assertEqual(text.count(f'text = "SOL_ESTATE_{estate}"'), 1)

    def test_goods_membership_and_group_order(self):
        expected = expected_memberships(ROOT / self.spec["goods"]["source"])
        self.assertEqual(len(expected), self.spec["goods"]["membership_rows"])
        self.assertEqual(len({good for _, good in expected}), self.spec["goods"]["unique_goods"])
        expected_groups = list(GROUP_ORDER)
        for kind in ("location", "country"):
            for path in self._surface_paths(kind):
                with self.subTest(surface=kind, path=path):
                    actual = goods_memberships(path)
                    self.assertEqual(len(actual), len(expected), "goods membership count changed")
                    self.assertEqual(actual, expected, "goods membership/group order changed")
                    labels = [group for group, _ in actual]
                    self.assertEqual(list(dict.fromkeys(labels)), expected_groups)

    def test_generic_goods_tooltip_has_no_market_or_country_scope(self):
        forbidden = self.spec["generic_goods_tooltip"]["forbidden_scope_expressions"]
        for configured in self.spec["generic_goods_tooltip"]["files"]:
            path = ROOT / configured
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8-sig")
                for expression in forbidden:
                    self.assertNotIn(expression, text)


if __name__ == "__main__":
    unittest.main()

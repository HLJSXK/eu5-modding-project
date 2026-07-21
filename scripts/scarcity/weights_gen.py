"""Patch SOL_goods_weight_values.txt — Part 1 string-replace per good."""
from __future__ import annotations

import sys
from typing import List

from ._data import (
    SHORTAGE_TIERS, SURPLUS_TIERS, ALL_GOODS,
    _good_list_name,
)


def _new_weight_part1(good: str) -> str:
    """Return the replacement Part 1 substitution block (tab-indented, no trailing newline)."""
    lines: List[str] = ["\t# Part 1 — Substitution"]
    first = True
    for suffix, _threshold, weight, desc in SHORTAGE_TIERS:
        lst = _good_list_name(good, suffix)
        kw = "if" if first else "else_if"
        first = False
        lines += [
            f"\t{kw} = {{",
            f"\t\tlimit = {{ location.market ?= {{ is_target_in_global_variable_list = {{ name = {lst} target = this }} }} }}",
            f'\t\tmultiply = {{ value = {weight} desc = "{desc}" }}',
            f"\t}}",
        ]
    for suffix, _threshold, weight, desc in SURPLUS_TIERS:
        lst = _good_list_name(good, suffix)
        lines += [
            f"\telse_if = {{",
            f"\t\tlimit = {{ location.market ?= {{ is_target_in_global_variable_list = {{ name = {lst} target = this }} }} }}",
            f'\t\tmultiply = {{ value = {weight} desc = "{desc}" }}',
            f"\t}}",
        ]
    return "\n".join(lines)


def patch_weights_file(text: str) -> str:
    """String-replace the Part 1 block for every good in the weights file."""
    for good in ALL_GOODS:
        old = (
            f"\t# Part 1 — Substitution\n"
            f"\tif = {{\n"
            f"\t\tlimit = {{ location.market ?= {{ is_target_in_global_variable_list = {{ name = SOL_{good}_scarce_markets target = this }} }} }}\n"
            f'\t\tmultiply = {{ value = 0.5 desc = "SOL_WEIGHT_SCARCE" }}\n'
            f"\t}}\n"
        )
        new = _new_weight_part1(good) + "\n"
        if old not in text:
            already_updated = f"SOL_{good}_severe_markets" in text
            if not already_updated:
                print(f"WARNING: Part 1 block not found for good '{good}' in weights file", file=sys.stderr)
            continue
        text = text.replace(old, new)
    return text

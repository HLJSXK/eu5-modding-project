"""
EU5 SOL Demand Simulator — File Parser (v2)

Correct EU5 demand formula:
    demand[good][pop_type] =
        (vanilla_demand_add[pop_type] × vanilla_demand_multiply[pop_type]
         + inject_demand_add[pop_type])
        × inject_demand_multiply[pop_type]
        × sol_gdp_per_capita_scale[pop_type]

Sources:
  - vanilla demand_add / demand_multiply  →  reference_game_files/…/common/goods/*.txt
  - inject demand_add / demand_multiply   →  src/stable/…/common/goods/z_SOL_pop_goods.txt
  - sol_gdp_per_capita_scale              →  handled by simulator.py (SOL_pop_values.txt)

z_SOL_pop_demand.txt is NOT used for base demand; it provides only the scaling scriptvalue.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

MOD_ROOT = Path(__file__).resolve().parent.parent.parent

VANILLA_GOODS_DIR = MOD_ROOT / "reference_game_files/game/in_game/common/goods"
INJECT_FILE       = MOD_ROOT / "src/stable/in_game/common/goods/z_SOL_pop_goods.txt"

# EU5 pop types the tool tracks (slaves excluded — no scaling formula)
EU5_POP_TYPES: List[str] = [
    "nobles", "clergy", "burghers", "laborers", "peasants", "soldiers", "tribesmen",
]
EU5_POP_TYPES_SET = frozenset(EU5_POP_TYPES)

# Group keywords → which EU5 pop types they expand to
UPPER_TYPES = frozenset(["nobles", "clergy", "burghers"])  # soldiers does NOT have upper = yes

# Simulator strata → underlying EU5 pop types
STRATA_TO_POP_TYPES: Dict[str, List[str]] = {
    "nobles":    ["nobles"],
    "clergy":    ["clergy"],
    "burghers":  ["burghers"],
    "commoners": ["laborers", "peasants", "soldiers"],
    "tribesmen": ["tribesmen"],
}

# Canonical simulator strata list (used throughout the app)
STRATA: List[str] = list(STRATA_TO_POP_TYPES.keys())


@dataclass
class DemandEntry:
    good: str
    price: float
    # Base demand per EU5 pop type — before sol_gdp_per_capita_scale
    # = (vanilla_add × vanilla_mult + inject_add) × inject_mult
    demand_per_pop_type: Dict[str, float]
    # Aggregated to the 5 simulator strata (commoners = average of laborers/peasants/soldiers)
    strata_demand: Dict[str, float]
    category: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _collect_brace_block(text: str, start: int) -> Tuple[str, int]:
    """Return (inner_content, closing_brace_index) starting from '{' at text[start]."""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i
        i += 1
    return text[start + 1 :], n - 1


def _parse_kv_block(inner: str) -> Dict[str, float]:
    """
    Parse `key = value` pairs from a simple block body.
    Handles negative values (-0.05).  Ignores sub-blocks and comments.
    """
    result: Dict[str, float] = {}
    for m in re.finditer(r"\b([a-z_]+)\s*=\s*(-?[\d.]+)", inner):
        key = m.group(1)
        try:
            result[key] = float(m.group(2))
        except ValueError:
            pass
    return result


def _find_sub_block(text: str, keyword: str) -> str | None:
    """
    Within *text*, find `keyword = { ... }` and return the inner content, or None.
    """
    m = re.search(r"\b" + re.escape(keyword) + r"\s*=\s*\{", text)
    if not m:
        return None
    brace_pos = m.end() - 1
    inner, _ = _collect_brace_block(text, brace_pos)
    return inner


def _expand_demand_add(kv: Dict[str, float]) -> Dict[str, float]:
    """
    Expand demand_add {all, upper, pop_type_name} to per-EU5-pop-type additions.
    Each EU5 pop type gets the SUM of all applicable keys.
    """
    result: Dict[str, float] = {pt: 0.0 for pt in EU5_POP_TYPES}
    for key, val in kv.items():
        if key == "all":
            for pt in EU5_POP_TYPES:
                result[pt] += val
        elif key == "upper":
            for pt in UPPER_TYPES:
                result[pt] += val
        elif key in EU5_POP_TYPES_SET:
            result[key] += val
        # else: unknown key (slaves, etc.) — skip
    return result


def _expand_demand_multiply(kv: Dict[str, float]) -> Dict[str, float]:
    """
    Expand demand_multiply {all, upper, pop_type_name} to per-EU5-pop-type multipliers.
    Multiple matching keys MULTIPLY together (user-confirmed behaviour).
    Processing order: all → upper → specific types (more specific stacks on broader).
    Default = 1.0 for any unspecified type.
    """
    result: Dict[str, float] = {pt: 1.0 for pt in EU5_POP_TYPES}
    # Process broad keys first, then narrow
    for key in ["all", "upper", *[k for k in kv if k not in ("all", "upper")]]:
        if key not in kv:
            continue
        val = kv[key]
        if key == "all":
            for pt in EU5_POP_TYPES:
                result[pt] *= val
        elif key == "upper":
            for pt in UPPER_TYPES:
                result[pt] *= val
        elif key in EU5_POP_TYPES_SET:
            result[key] *= val
    return result


def _compute_base_demand_per_pop_type(
    vanilla_add:  Dict[str, float],
    vanilla_mult: Dict[str, float],
    inject_add:   Dict[str, float],
    inject_mult:  Dict[str, float],
) -> Dict[str, float]:
    """
    Apply the formula per EU5 pop type:
        (vanilla_add × vanilla_mult + inject_add) × inject_mult
    """
    result: Dict[str, float] = {}
    for pt in EU5_POP_TYPES:
        base = vanilla_add.get(pt, 0.0) * vanilla_mult.get(pt, 1.0) + inject_add.get(pt, 0.0)
        result[pt] = base * inject_mult.get(pt, 1.0)
    return result


def _aggregate_to_strata(demand_per_pt: Dict[str, float]) -> Dict[str, float]:
    """
    Collapse EU5 pop types into the 5 simulator strata.
    commoners = mean(laborers, peasants, soldiers).
    """
    result: Dict[str, float] = {}
    for strata, pop_types in STRATA_TO_POP_TYPES.items():
        vals = [demand_per_pt.get(pt, 0.0) for pt in pop_types]
        result[strata] = sum(vals) / len(vals)
    return result


def _split_named_blocks(text: str) -> List[Tuple[str, str]]:
    """
    Split text into [(name, inner), ...] for every top-level `name = { ... }` entry.
    """
    results: List[Tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\n\r":
            i += 1
        if i >= n:
            break
        if text[i] == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        m = re.match(r"([A-Za-z_][\w]*)\s*=\s*\{", text[i:])
        if m:
            name = m.group(1)
            brace_start = i + m.end() - 1
            inner, end = _collect_brace_block(text, brace_start)
            results.append((name, inner))
            i = end + 1
        else:
            while i < n and text[i] != "\n":
                i += 1
    return results


# ---------------------------------------------------------------------------
# Vanilla goods file parser
# ---------------------------------------------------------------------------

def _parse_vanilla_goods_file(path: Path) -> Dict[str, Dict]:
    """
    Parse one vanilla goods .txt file.
    Returns {good_name: {'price': float, 'add': {pt: float}, 'mult': {pt: float}}}
    """
    text = _read(path)
    goods: Dict[str, Dict] = {}

    for good_name, block in _split_named_blocks(text):
        # Skip non-good top-level blocks
        if good_name in {"category", "color", "method"}:
            continue

        # Price
        price_m = re.search(r"\bdefault_market_price\s*=\s*([\d.]+)", block)
        price = float(price_m.group(1)) if price_m else 1.0

        # demand_add
        da_inner = _find_sub_block(block, "demand_add")
        demand_add = _expand_demand_add(_parse_kv_block(da_inner)) if da_inner else {pt: 0.0 for pt in EU5_POP_TYPES}

        # demand_multiply
        dm_inner = _find_sub_block(block, "demand_multiply")
        demand_mult = _expand_demand_multiply(_parse_kv_block(dm_inner)) if dm_inner else {pt: 1.0 for pt in EU5_POP_TYPES}

        goods[good_name] = {"price": price, "add": demand_add, "mult": demand_mult}

    return goods


def load_vanilla_goods() -> Dict[str, Dict]:
    """
    Merge all vanilla goods files into one dict.
    Returns {good_name: {'price', 'add', 'mult'}}.
    """
    merged: Dict[str, Dict] = {}
    for path in sorted(VANILLA_GOODS_DIR.glob("*.txt")):
        if path.name.lower() == "readme.txt":
            continue
        for name, data in _parse_vanilla_goods_file(path).items():
            if name in merged:
                # Merge: sum adds, multiply mults, keep first price
                for pt in EU5_POP_TYPES:
                    merged[name]["add"][pt] += data["add"][pt]
                    merged[name]["mult"][pt] *= data["mult"][pt]
            else:
                merged[name] = data
    return merged


# ---------------------------------------------------------------------------
# Inject goods file parser (z_SOL_pop_goods.txt)
# ---------------------------------------------------------------------------

def _parse_inject_file(path: Path) -> Dict[str, Dict]:
    """
    Parse z_SOL_pop_goods.txt INJECT entries.
    Returns {good_name: {'inject_add': {pt: float}, 'inject_mult': {pt: float}}}.
    """
    text = _read(path)
    result: Dict[str, Dict] = {}

    # Match INJECT:good_name = { ... }
    i = 0
    n = len(text)
    while i < n:
        m = re.search(r"\bINJECT:(\w+)\s*=\s*\{", text[i:])
        if not m:
            break
        good_name = m.group(1)
        brace_pos = i + m.end() - 1
        inner, end = _collect_brace_block(text, brace_pos)
        i = end + 1

        da_inner = _find_sub_block(inner, "demand_add")
        inject_add = _expand_demand_add(_parse_kv_block(da_inner)) if da_inner else {pt: 0.0 for pt in EU5_POP_TYPES}

        dm_inner = _find_sub_block(inner, "demand_multiply")
        inject_mult = _expand_demand_multiply(_parse_kv_block(dm_inner)) if dm_inner else {pt: 1.0 for pt in EU5_POP_TYPES}

        result[good_name] = {"inject_add": inject_add, "inject_mult": inject_mult}

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_goods_prices() -> Dict[str, float]:
    """Return {good_name: default_market_price} from vanilla goods files."""
    vanilla = load_vanilla_goods()
    return {name: data["price"] for name, data in vanilla.items()}


def load_demand_matrix() -> Dict[str, DemandEntry]:
    """
    Build the complete demand matrix using the correct formula:
        demand[good][pop_type] = (vanilla_add × vanilla_mult + inject_add) × inject_mult

    Returns {good_name: DemandEntry} for every good that has non-zero demand
    for at least one pop type.
    """
    vanilla = load_vanilla_goods()
    inject  = _parse_inject_file(INJECT_FILE)

    # Section grouping from vanilla file name for display
    section_map: Dict[str, str] = {}
    for path in sorted(VANILLA_GOODS_DIR.glob("*.txt")):
        if path.name.lower() == "readme.txt":
            continue
        label = path.stem.split("_", 1)[-1].replace("_", " ").title() if "_" in path.stem else path.stem
        for name in _parse_vanilla_goods_file(path):
            section_map.setdefault(name, label)

    matrix: Dict[str, DemandEntry] = {}
    for good_name, v_data in vanilla.items():
        inj = inject.get(good_name, {})
        inject_add  = inj.get("inject_add",  {pt: 0.0 for pt in EU5_POP_TYPES})
        inject_mult = inj.get("inject_mult",  {pt: 1.0 for pt in EU5_POP_TYPES})

        demand_pt = _compute_base_demand_per_pop_type(
            vanilla_add  = v_data["add"],
            vanilla_mult = v_data["mult"],
            inject_add   = inject_add,
            inject_mult  = inject_mult,
        )

        # Only include goods that have any demand
        if all(abs(v) < 1e-12 for v in demand_pt.values()):
            continue

        matrix[good_name] = DemandEntry(
            good               = good_name,
            price              = v_data["price"],
            demand_per_pop_type= demand_pt,
            strata_demand      = _aggregate_to_strata(demand_pt),
            category           = section_map.get(good_name, ""),
        )

    return matrix


if __name__ == "__main__":
    vanilla = load_vanilla_goods()
    print(f"Vanilla goods: {len(vanilla)}")

    injects = _parse_inject_file(INJECT_FILE)
    print(f"INJECT entries: {len(injects)}")

    dm = load_demand_matrix()
    print(f"Goods with demand: {len(dm)}")

    # Spot-check: fur
    print("\n--- fur ---")
    fur = dm.get("fur")
    if fur:
        print(f"  price = {fur.price}")
        print("  per pop type (base):")
        for pt, v in fur.demand_per_pop_type.items():
            if abs(v) > 1e-9:
                print(f"    {pt:12s}: {v:.6f}")
        print("  strata demand:")
        for s, v in fur.strata_demand.items():
            print(f"    {s:12s}: {v:.6f}")

    # Spot-check: wine
    print("\n--- wine ---")
    wine = dm.get("wine")
    if wine:
        print(f"  price = {wine.price}")
        for pt, v in wine.demand_per_pop_type.items():
            if abs(v) > 1e-9:
                print(f"    {pt:12s}: {v:.6f}")

    # Spot-check: livestock
    print("\n--- livestock ---")
    ls = dm.get("livestock")
    if ls:
        for pt, v in ls.demand_per_pop_type.items():
            if abs(v) > 1e-9:
                print(f"    {pt:12s}: {v:.6f}")

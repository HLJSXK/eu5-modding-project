"""Localization key generation and upsert for SOL substitute goods."""
from __future__ import annotations

import re
from typing import List, Tuple

from ._data import (
    ALL_GOODS, GOOD_TO_IND_GROUP, DEMAND_GROUPS,
    DEMAND_GROUP_NAMES_EN, DEMAND_GROUP_NAMES_ZH,
    GOOD_NAMES_EN, GOOD_NAMES_ZH,
    _fmt_ratio,
)

NEW_LOC_KEYS_EN = [
    ("SOL_SUBST_SECTION_TITLE", "Substitute Group"),
    ("SOL_WEIGHT_SCARCE_1", "Mild shortage — weight ×0.75"),
    ("SOL_WEIGHT_SCARCE_2", "Moderate shortage — weight ×0.50"),
    ("SOL_WEIGHT_SCARCE_3", "Severe shortage — weight ×0.25"),
    ("SOL_WEIGHT_CHEAP_1",  "Affordable — weight ×1.25"),
    ("SOL_WEIGHT_CHEAP_2",  "Cheap — weight ×1.50"),
    ("SOL_WEIGHT_CHEAP_3",  "Very cheap — weight ×2.00"),
    ("SOL_TT_STATUS_OK",          'OK'),
    ("SOL_TT_STATUS_MILD",       '#R Mild#!'),
    ("SOL_TT_STATUS_MODERATE",   '#R Moderate#!'),
    ("SOL_TT_STATUS_SEVERE",     '#R Severe#!'),
    ("SOL_TT_STATUS_AFFORDABLE", '#G Affordable#!'),
    ("SOL_TT_STATUS_CHEAP",      '#G Cheap#!'),
    ("SOL_TT_STATUS_VCHEAP",     '#G Very Cheap#!'),
    ("SOL_TT_STATUS_ABSENT",     'Unknown'),
    ("SOL_PANEL_SCARCITY_TITLE", "Substitute Groups — Capital Market"),
]

NEW_LOC_KEYS_ZH = [
    ("SOL_SUBST_SECTION_TITLE", "替代组"),
    ("SOL_WEIGHT_SCARCE_1", "轻微短缺——权重 ×0.75"),
    ("SOL_WEIGHT_SCARCE_2", "中度短缺——权重 ×0.50"),
    ("SOL_WEIGHT_SCARCE_3", "严重短缺——权重 ×0.25"),
    ("SOL_WEIGHT_CHEAP_1",  "价格低廉——权重 ×1.25"),
    ("SOL_WEIGHT_CHEAP_2",  "价格便宜——权重 ×1.50"),
    ("SOL_WEIGHT_CHEAP_3",  "极度便宜——权重 ×2.00"),
    ("SOL_TT_STATUS_OK",          '正常'),
    ("SOL_TT_STATUS_MILD",       '#R 轻微短缺#!'),
    ("SOL_TT_STATUS_MODERATE",   '#R 中度短缺#!'),
    ("SOL_TT_STATUS_SEVERE",     '#R 严重短缺#!'),
    ("SOL_TT_STATUS_AFFORDABLE", '#G 低廉#!'),
    ("SOL_TT_STATUS_CHEAP",      '#G 便宜#!'),
    ("SOL_TT_STATUS_VCHEAP",     '#G 极度便宜#!'),
    ("SOL_TT_STATUS_ABSENT",     '未知'),
    ("SOL_PANEL_SCARCITY_TITLE", "替代商品组——首都市场"),
]


def upsert_localization(text: str, keys: List[Tuple[str, str]]) -> str:
    for key, val in keys:
        line = f' {key}:0 "{val}"'
        existing = re.compile(rf'^ {re.escape(key)}(?::0)? ".*"$', re.MULTILINE)
        if existing.search(text):
            text = existing.sub(line, text)
        else:
            text = text.rstrip("\n") + "\n" + line + "\n"
    return text


def gen_subst_group_loc_keys(prices: dict) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    demand_groups_dict = {grp: members for grp, members in DEMAND_GROUPS}
    en_entries: List[Tuple[str, str]] = []
    zh_entries: List[Tuple[str, str]] = []

    for good in ALL_GOODS:
        ind_grp = GOOD_TO_IND_GROUP.get(good)
        if not ind_grp:
            continue
        members = demand_groups_dict.get(ind_grp, [])
        grp_name_en = DEMAND_GROUP_NAMES_EN.get(ind_grp, ind_grp)
        grp_name_zh = DEMAND_GROUP_NAMES_ZH.get(ind_grp, ind_grp)
        good_name_en = GOOD_NAMES_EN.get(good, good)
        good_name_zh = GOOD_NAMES_ZH.get(good, good)
        pa = prices.get(good, 1.0)

        en_parts: List[str] = []
        zh_parts: List[str] = []
        for other in members:
            if other == good:
                continue
            pb = prices.get(other, 1.0)
            ratio = _fmt_ratio(pa / pb)
            en_parts.append(f"1 {good_name_en} ≈ {ratio} {GOOD_NAMES_EN.get(other, other)}")
            zh_parts.append(f"1份{good_name_zh}可替代{ratio}份{GOOD_NAMES_ZH.get(other, other)}")

        key = f"SOL_good_subst_group_{good}"
        if en_parts:
            en_entries.append((key, f"Belongs to #B{grp_name_en}#! substitute group: {'; '.join(en_parts)}."))
            zh_entries.append((key, f"该商品属于 #B{grp_name_zh}#! 替代组：{'；'.join(zh_parts)}。"))
        else:
            en_entries.append((key, f"Belongs to #B{grp_name_en}#! substitute group (sole member)."))
            zh_entries.append((key, f"该商品属于 #B{grp_name_zh}#! 替代组（唯一成员）。"))

    return en_entries, zh_entries


def gen_subst_ratio_loc_keys(prices: dict) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    en_keys: List[Tuple[str, str]] = []
    zh_keys: List[Tuple[str, str]] = []
    seen_from: set = set()
    seen_pair: set = set()

    for _grp, members in DEMAND_GROUPS:
        for a in members:
            a_en = GOOD_NAMES_EN.get(a, a)
            a_zh = GOOD_NAMES_ZH.get(a, a)
            pa = prices.get(a, 1.0)
            if a not in seen_from:
                seen_from.add(a)
                en_keys.append((f"SOL_SUBST_FROM_{a}", f"1 {a_en}"))
                zh_keys.append((f"SOL_SUBST_FROM_{a}", f"1单位{a_zh}"))
            for b in members:
                if b == a:
                    continue
                pair = (a, b)
                if pair in seen_pair:
                    continue
                seen_pair.add(pair)
                pb = prices.get(b, 1.0)
                ratio_str = _fmt_ratio(pa / pb)
                b_en = GOOD_NAMES_EN.get(b, b)
                b_zh = GOOD_NAMES_ZH.get(b, b)
                en_keys.append((f"SOL_SUBST_RATIO_{a}_{b}", f"= {ratio_str} {b_en}"))
                zh_keys.append((f"SOL_SUBST_RATIO_{a}_{b}", f"可替代 {ratio_str}单位{b_zh}"))

    return en_keys, zh_keys

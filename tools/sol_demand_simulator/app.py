"""
EU5 SOL Demand Simulator — Streamlit UI (v3)

Three tabs:
  Tab 0 — Substitute Group Manager: per-group k-factor weight editor
  Tab 1 — Alpha Adjustment: piecewise Engel curve / budget share designer
  Tab 2 — Savings Dynamics: simplified single-variable savings pressure simulator

Run:
    cd tools/sol_demand_simulator
    pip install -r requirements.txt
    streamlit run app.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace as dc_replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from simulator import (
    PRESSURE_MODES,
    savings_pressure_curve_np,
)
from parser import (
    STRATA,
    load_demand_matrix,
)
from curve_designer import (
    SUBSTITUTE_GROUPS,
    GROUP_GOODS,
    GROUP_COLORS,
    ALL_GOODS,
    MULTI_GROUP_GOODS,
    LUXURY_RANK,
    GoodsWeightStore,
    CurveDesignerState,
    luxury_sorted_groups,
    groups_for_good,
)
from engel_export import (
    REPO_ROOT,
    BRACKET_TABLE,
    DEFAULT_THRESHOLDS,
    load_bracket_table,
    load_bracket_thresholds,
    save_bracket_table,
    validate_all_bracket_constraints,
    export_bracket_budget_shares,
    export_group_prices,
    init_bracket_table_from_alpha_table,
    compute_piecewise_offsets,
    compute_reference_income,
    compute_intersection_b,
    generate_power_alpha_bracket_table,
    generate_power_b_profile,
    pick_bracket_sample_incomes,
    export_demand_offsets,
    export_demand_base,
    export_demand_scales_with_offset,
    BUDGET_SHARES_FILE as ENGEL_BUDGET_SHARES_FILE,
    DEMAND_OFFSETS_FILE,
    DEMAND_BASE_FILE,
    DEMAND_SCALES_FILE,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SOL Demand Simulator",
    page_icon="📊",
    layout="wide",
)

st.title("SOL Pop Demand Simulator")

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Parsing demand file…")
def _load_matrix():
    return load_demand_matrix()

demand_matrix = _load_matrix()


def _reweight_commoners(dm: dict, pop_lab: float, pop_peas: float, pop_sold: float) -> dict:
    total = max(1e-9, pop_lab + pop_peas + pop_sold)
    w = {"laborers": pop_lab / total, "peasants": pop_peas / total, "soldiers": pop_sold / total}
    result = {}
    for good, entry in dm.items():
        weighted_comm = sum(entry.demand_per_pop_type[pt] * w[pt] for pt in w)
        result[good] = dc_replace(
            entry,
            strata_demand={**entry.strata_demand, "commoners": weighted_comm},
        )
    return result


# Fixed default pop split for commoner reweighting
demand_matrix_w = _reweight_commoners(demand_matrix, 500.0, 500.0, 0.0)

STRATA_LABELS = {
    "nobles":    "贵族 Nobles",
    "clergy":    "教士 Clergy",
    "burghers":  "商人 Burghers",
    "commoners": "平民 Commoners",
    "tribesmen": "部落民 Tribesmen",
}

# ---------------------------------------------------------------------------
# Lazy init (runs once, before tabs)
# ---------------------------------------------------------------------------
if "curve_designer" not in st.session_state:
    cd = CurveDesignerState()
    cd.init_from_demand_matrix(demand_matrix_w)
    st.session_state["curve_designer"] = cd
cd: CurveDesignerState = st.session_state["curve_designer"]

# ---------------------------------------------------------------------------
# Alpha generator helpers
# ---------------------------------------------------------------------------

ALPHA_GENERATOR_SETTINGS_FILE = REPO_ROOT / "data" / "alpha_generator_settings.json"


def _default_group_order() -> dict[str, int]:
    ordered = luxury_sorted_groups()[::-1]
    return {group: idx + 1 for idx, group in enumerate(ordered)}


def _normalize_group_order(order_map: dict[str, int]) -> dict[str, int]:
    decorated = []
    fallback = _default_group_order()
    for idx, group in enumerate(luxury_sorted_groups()):
        raw = order_map.get(group, fallback.get(group, idx + 1))
        try:
            val = int(raw)
        except (TypeError, ValueError):
            val = fallback.get(group, idx + 1)
        decorated.append((val, idx, group))
    decorated.sort(key=lambda x: (x[0], x[1]))
    return {group: pos + 1 for pos, (_, _, group) in enumerate(decorated)}


def _parse_ag_section(section: dict, defaults: dict) -> dict:
    return {
        "low_rank_exp": float(section.get("low_rank_exp", defaults["low_rank_exp"])),
        "high_rank_exp": float(section.get("high_rank_exp", defaults["high_rank_exp"])),
        "group_order": _normalize_group_order(section.get("group_order", defaults["group_order"])),
    }


def load_alpha_generator_settings(strata_key: str = "all") -> dict:
    """Load alpha-generator settings for the given strata key (or "all")."""
    defaults = {
        "low_rank_exp": -0.35,
        "high_rank_exp": 0.35,
        "group_order": _default_group_order(),
    }
    if not ALPHA_GENERATOR_SETTINGS_FILE.exists():
        return defaults
    try:
        raw = json.loads(ALPHA_GENERATOR_SETTINGS_FILE.read_text(encoding="utf-8"))
        # Backwards compat: old flat format has "low_rank_exp" at top level
        if "low_rank_exp" in raw:
            return _parse_ag_section(raw, defaults) if strata_key == "all" else defaults
        # New per-strata format: try requested key, fall back to "all", then defaults
        section = raw.get(strata_key) or raw.get("all") or {}
        return _parse_ag_section(section, defaults)
    except Exception:
        return defaults


def save_alpha_generator_settings(settings: dict, strata_key: str = "all") -> None:
    """Save alpha-generator settings for the given strata key into the JSON file."""
    existing: dict = {}
    if ALPHA_GENERATOR_SETTINGS_FILE.exists():
        try:
            raw = json.loads(ALPHA_GENERATOR_SETTINGS_FILE.read_text(encoding="utf-8"))
            if "low_rank_exp" in raw:
                # Migrate old flat format → put under "all"
                existing["all"] = {
                    "low_rank_exp": float(raw.get("low_rank_exp", -0.35)),
                    "high_rank_exp": float(raw.get("high_rank_exp", 0.35)),
                    "group_order": _normalize_group_order(raw.get("group_order", _default_group_order())),
                }
            else:
                existing = {k: v for k, v in raw.items() if isinstance(v, dict)}
        except Exception:
            pass
    existing[strata_key] = {
        "low_rank_exp": float(settings.get("low_rank_exp", -0.35)),
        "high_rank_exp": float(settings.get("high_rank_exp", 0.35)),
        "group_order": _normalize_group_order(settings.get("group_order", _default_group_order())),
    }
    ALPHA_GENERATOR_SETTINGS_FILE.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _derive_exponents_from_order(order_map: dict[str, int], high_exp: float, low_exp: float) -> dict[str, float]:
    normalized = _normalize_group_order(order_map)
    ordered_groups = [g for g, _ in sorted(normalized.items(), key=lambda item: item[1])]
    n = len(ordered_groups)
    if n <= 1:
        mid = (float(high_exp) + float(low_exp)) * 0.5
        return {ordered_groups[0]: mid} if ordered_groups else {}

    result: dict[str, float] = {}
    for pos, group in enumerate(ordered_groups):
        t = pos / (n - 1)
        result[group] = float(high_exp) + (float(low_exp) - float(high_exp)) * t
    return result


tab0, tab1, tab2, tab3 = st.tabs([
    "Tab 0 — Substitute Group Manager",
    "Tab 1 — Alpha Generator",
    "Tab 2 — Alpha Adjustment",
    "Tab 3 — Savings Dynamics",
])

# ===========================================================================
# TAB 0: Substitute Group Manager
# ===========================================================================
with tab0:
    st.caption(
        "管理各替代组内商品的 k 因子权重。"
        "商品在组内的需求份额 = k_i / Σk_j，调整后自动存储在 data/goods_weights.csv。"
    )

    wstore: GoodsWeightStore = cd.goods_weight_store

    # ---- Group selector ----
    gw_col1, gw_col2 = st.columns([1, 2])
    with gw_col1:
        selected_group = st.selectbox(
            "选择替代组",
            options=luxury_sorted_groups(),
            format_func=lambda g: f"{g.replace('_', ' ').title()} ({len(GROUP_GOODS.get(g, []))} goods)",
            key="gw_selected_group",
        )
    with gw_col2:
        total_k = wstore.group_total_weight(selected_group)
        st.caption(f"Σk = **{total_k:.4f}**  |  λ (N_g for multi-group scaling) is not applied here; it is a constant in the mod formula.")

    # ---- Per-good weight table for selected group ----
    st.markdown(f"#### {selected_group.replace('_', ' ').title()} — 商品权重")
    goods_in_group = GROUP_GOODS.get(selected_group, [])
    if goods_in_group:
        header_cols = st.columns([2, 1.5, 2, 1])
        with header_cols[0]:
            st.markdown("**商品**")
        with header_cols[1]:
            st.markdown("**k 因子**")
        with header_cols[2]:
            st.markdown("**组内份额**")
        with header_cols[3]:
            st.markdown("**跨组**")

        for good in goods_in_group:
            color_hex = GROUP_COLORS.get(selected_group, "#888")
            cur_k = wstore.get_k(good, selected_group)
            share = wstore.good_share_in_group(good, selected_group)
            multi_groups = [g for g in groups_for_good(good) if g != selected_group]

            g_col1, g_col2, g_col3, g_col4 = st.columns([2, 1.5, 2, 1])
            with g_col1:
                st.markdown(
                    f"<span style='background-color:{color_hex};color:white;padding:1px 6px;"
                    f"border-radius:3px;font-size:0.85em;font-weight:bold'>{good}</span>",
                    unsafe_allow_html=True,
                )
            with g_col2:
                new_k = st.number_input(
                    f"k_{good}_{selected_group}",
                    min_value=0.0,
                    max_value=10.0,
                    value=float(cur_k),
                    step=0.1,
                    format="%.2f",
                    key=f"gw_k_{selected_group}_{good}",
                    label_visibility="collapsed",
                )
                if abs(new_k - cur_k) > 1e-9:
                    wstore.set_k(good, selected_group, new_k)
            with g_col3:
                st.progress(min(float(share), 1.0), text=f"{share*100:.1f}%")
            with g_col4:
                if multi_groups:
                    st.caption(", ".join(multi_groups))
                else:
                    st.caption("—")

    # ---- All-groups summary table ----
    st.markdown("#### 全组摘要")
    summary_rows = wstore.all_groups_summary()
    st.dataframe(
        pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "group": st.column_config.TextColumn("替代组"),
            "n_goods": st.column_config.NumberColumn("商品数"),
            "total_k": st.column_config.NumberColumn("Σk", format="%.4f"),
            "multi_goods": st.column_config.TextColumn("跨组商品"),
        },
    )

    # ---- Save / Reset ----
    gw_btn1, gw_btn2, gw_btn3 = st.columns([1, 1, 2])
    with gw_btn1:
        if st.button("保存权重", type="primary", key="gw_save_btn",
                     help="保存到 data/goods_weights.csv"):
            wstore.save_csv()
            st.success("已保存到 data/goods_weights.csv")
    with gw_btn2:
        if st.button("重置全为 1.0", key="gw_reset_btn"):
            wstore.init_defaults()
            st.rerun()

# ===========================================================================
# TAB 1: Alpha Generator
# ===========================================================================
with tab1:
    st.caption(
        "按替代组幂次批量生成初始分档 α。"
        "核心假设：所有组的 b(y)=α/P 在 bracket1~2 临界点共同相交，再由各组幂次决定偏离方式。"
    )

    # Read the currently selected target before the widget renders (available from session state)
    _ag_cur_target = st.session_state.get("ag_target_strata", "all")

    # Load settings when first entering Tab 1 or when the target strata changes
    if (st.session_state.get("_ag_loaded_for_target") != _ag_cur_target
            or "ag_settings_initialized" not in st.session_state):
        ag_settings = load_alpha_generator_settings(_ag_cur_target)
        st.session_state["ag_low_rank_exp"] = ag_settings["low_rank_exp"]
        st.session_state["ag_high_rank_exp"] = ag_settings["high_rank_exp"]
        st.session_state["ag_group_order"] = ag_settings["group_order"]
        st.session_state["ag_settings_initialized"] = True
        st.session_state["_ag_loaded_for_target"] = _ag_cur_target

    if st.session_state.pop("ag_reset_to_saved_defaults", False):
        ag_settings = load_alpha_generator_settings(_ag_cur_target)
        st.session_state["ag_low_rank_exp"] = ag_settings["low_rank_exp"]
        st.session_state["ag_high_rank_exp"] = ag_settings["high_rank_exp"]
        st.session_state["ag_group_order"] = ag_settings["group_order"]

    if "bm_thresholds" not in st.session_state:
        if BRACKET_TABLE.exists():
            st.session_state["bm_thresholds"] = load_bracket_thresholds(BRACKET_TABLE)
        else:
            st.session_state["bm_thresholds"] = DEFAULT_THRESHOLDS.copy()

    if "bm_alpha" not in st.session_state:
        if BRACKET_TABLE.exists():
            st.session_state["bm_alpha"] = load_bracket_table(BRACKET_TABLE)
            st.session_state["bm_initialized"] = True
        else:
            st.session_state["bm_alpha"] = {}

    if "ag_group_order" not in st.session_state:
        st.session_state["ag_group_order"] = _default_group_order()

    ag_target = st.selectbox(
        "生成范围",
        options=["all"] + list(STRATA),
        format_func=lambda s: "all strata（全部阶层）" if s == "all" else f"{s} ({STRATA_LABELS[s]})",
        key="ag_target_strata",
    )

    ag_fill_col1, ag_fill_col2, ag_fill_col3 = st.columns([1, 1, 2])
    with ag_fill_col1:
        low_rank_exp = st.number_input(
            "低端幂次",
            value=float(st.session_state.get("ag_low_rank_exp", -0.35)),
            step=0.05,
            format="%.2f",
            key="ag_low_rank_exp",
        )
    with ag_fill_col2:
        high_rank_exp = st.number_input(
            "高端幂次",
            value=float(st.session_state.get("ag_high_rank_exp", 0.35)),
            step=0.05,
            format="%.2f",
            key="ag_high_rank_exp",
        )
    with ag_fill_col3:
        st.caption("系统会按当前顺序自动把 exponent 从高到低映射到上下限之间；交点高度仍由 Σα=1 与 P_g_s 自动决定。")
        ag_cfg_btn1, ag_cfg_btn2 = st.columns(2)
        with ag_cfg_btn1:
            if st.button("保存为默认生成参数", key="ag_save_defaults", use_container_width=True):
                save_alpha_generator_settings({
                    "low_rank_exp": low_rank_exp,
                    "high_rank_exp": high_rank_exp,
                    "group_order": st.session_state["ag_group_order"],
                }, strata_key=ag_target)
                label = "全部阶层" if ag_target == "all" else f"{ag_target} ({STRATA_LABELS.get(ag_target, ag_target)})"
                st.success(f"已保存 [{label}] 默认参数。")
        with ag_cfg_btn2:
            if st.button("重置为默认顺序", key="ag_reset_default_order", use_container_width=True):
                st.session_state["ag_reset_to_saved_defaults"] = True
                st.rerun()

    normalized_order = _normalize_group_order(st.session_state["ag_group_order"])
    exponents = _derive_exponents_from_order(normalized_order, high_rank_exp, low_rank_exp)

    st.markdown("#### 组顺序与派生 exponent")
    ordered_groups = [g for g in sorted(normalized_order, key=lambda g: normalized_order[g])]
    for idx, group in enumerate(ordered_groups):
        row_cols = st.columns([0.5, 1.5, 4.5, 1.2, 0.7, 0.7])
        with row_cols[0]:
            st.markdown(f"**{idx + 1}**")
        with row_cols[1]:
            color_hex = GROUP_COLORS.get(group, "#888")
            st.markdown(
                f"<span style='background-color:{color_hex};color:white;padding:2px 8px;"
                f"border-radius:4px;font-weight:bold'>{group.upper()}</span>",
                unsafe_allow_html=True,
            )
        with row_cols[2]:
            st.caption(", ".join(GROUP_GOODS.get(group, [])))
        with row_cols[3]:
            st.caption(f"exp = {exponents.get(group, 0.0):.4f}")
        with row_cols[4]:
            up_disabled = idx == 0
            if st.button("↑", key=f"ag_up_{group}", disabled=up_disabled, use_container_width=True):
                swapped = ordered_groups.copy()
                swapped[idx - 1], swapped[idx] = swapped[idx], swapped[idx - 1]
                st.session_state["ag_group_order"] = {g: pos + 1 for pos, g in enumerate(swapped)}
                st.rerun()
        with row_cols[5]:
            down_disabled = idx == len(ordered_groups) - 1
            if st.button("↓", key=f"ag_down_{group}", disabled=down_disabled, use_container_width=True):
                swapped = ordered_groups.copy()
                swapped[idx + 1], swapped[idx] = swapped[idx], swapped[idx + 1]
                st.session_state["ag_group_order"] = {g: pos + 1 for pos, g in enumerate(swapped)}
                st.rerun()

    thresholds_by_strata = {
        s: list(st.session_state["bm_thresholds"].get(s, DEFAULT_THRESHOLDS.get(s, [0.0])))
        for s in STRATA
    }
    P_values = {
        s: {
            g: (cd.groups[g].base_price_sum_per_strata.get(s, 0.0) if cd.groups.get(g) else 0.0)
            for g in SUBSTITUTE_GROUPS
        }
        for s in STRATA
    }

    generated_all = generate_power_alpha_bracket_table(
        thresholds_by_strata,
        P_values,
        exponents,
    )

    preview_strata = ag_target if ag_target != "all" else STRATA[0]
    preview_thresholds = thresholds_by_strata.get(preview_strata, DEFAULT_THRESHOLDS.get(preview_strata, [0.0]))
    preview_ref_income = compute_reference_income(preview_thresholds)
    preview_incomes = pick_bracket_sample_incomes(preview_thresholds, preview_ref_income)
    preview_income_max = max(preview_thresholds[-1] * 2.5, preview_ref_income * 2.0, 1.0)
    preview_income_pts = np.linspace(max(preview_incomes[0] * 0.25, 1e-6), preview_income_max, 400)
    preview_intersection_b = compute_intersection_b(P_values.get(preview_strata, {}))

    st.markdown(f"#### 预览 — {preview_strata} ({STRATA_LABELS[preview_strata]})")
    st.caption(
        f"共同锚点收入 y_ref = {preview_ref_income:.4f}，共同交点 b_ref = {preview_intersection_b:.6f}。"
    )

    fig_ag_b = go.Figure()
    for group in sorted(normalized_order, key=lambda g: normalized_order[g]):
        b_vals = generate_power_b_profile(
            preview_intersection_b,
            exponents.get(group, 0.0),
            list(preview_income_pts),
            preview_ref_income,
        )
        fig_ag_b.add_trace(go.Scatter(
            x=preview_income_pts,
            y=b_vals,
            name=f"{normalized_order[group]}. {group.title()}",
            line=dict(color=GROUP_COLORS.get(group, "#888"), width=2),
        ))
    fig_ag_b.add_vline(x=preview_ref_income, line_dash="dot", line_color="gray", opacity=0.7)
    fig_ag_b.update_layout(
        xaxis_title="Income (gold/月/pop-unit)",
        yaxis_title="b(y) = α / P_g_s",
        legend_title="Group",
        height=360,
    )
    st.plotly_chart(fig_ag_b, use_container_width=True)

    fig_ag_alpha = go.Figure()
    n_preview_brackets = len(preview_thresholds)
    for group in sorted(normalized_order, key=lambda g: normalized_order[g]):
        alpha_vals = np.zeros_like(preview_income_pts)
        for i, y in enumerate(preview_income_pts):
            k = sum(1 for t in preview_thresholds if t <= y) - 1
            k = max(0, min(k, n_preview_brackets - 1))
            alpha_vals[i] = generated_all.get(preview_strata, {}).get(k, {}).get(group, 0.0)
        fig_ag_alpha.add_trace(go.Scatter(
            x=preview_income_pts,
            y=alpha_vals,
            name=group.title(),
            line=dict(color=GROUP_COLORS.get(group, "#888"), width=2),
            showlegend=False,
        ))
    for thresh in preview_thresholds[1:]:
        fig_ag_alpha.add_vline(x=thresh, line_dash="dot", line_color="gray", opacity=0.5)
    fig_ag_alpha.add_vline(x=preview_ref_income, line_dash="dash", line_color="#666", opacity=0.7)
    fig_ag_alpha.update_layout(
        xaxis_title="Income (gold/月/pop-unit)",
        yaxis_title="预算份额 α_g_s",
        height=360,
    )
    st.plotly_chart(fig_ag_alpha, use_container_width=True)

    ag_summary_rows = []
    for k in range(len(preview_thresholds)):
        row = {"bracket": k, "threshold": preview_thresholds[k]}
        row["Σα"] = round(sum(generated_all.get(preview_strata, {}).get(k, {}).values()), 6)
        ag_summary_rows.append(row)
    st.dataframe(pd.DataFrame(ag_summary_rows), use_container_width=True, hide_index=True)

    def _apply_generated_alpha(save_to_csv: bool) -> None:
        if ag_target == "all":
            merged = generated_all
        else:
            merged = dict(st.session_state.get("bm_alpha", {}))
            merged[ag_target] = generated_all.get(ag_target, {})
        st.session_state["bm_alpha"] = merged
        st.session_state["bm_thresholds"] = thresholds_by_strata
        st.session_state["bm_initialized"] = True
        for key in list(st.session_state.keys()):
            if key == "_bm_last_context" or key.startswith("bm_share_") or key.startswith("bm_fine_") or key.startswith("bm_b_"):
                del st.session_state[key]
        if save_to_csv:
            save_bracket_table(st.session_state["bm_alpha"], st.session_state["bm_thresholds"], BRACKET_TABLE)

    ag_btn1, ag_btn2 = st.columns(2)
    with ag_btn1:
        if st.button("传递到 Tab 2（仅本次）", key="ag_apply_session", type="primary", use_container_width=True):
            _apply_generated_alpha(save_to_csv=False)
            st.success("已传递到 Tab 2，请切换过去继续微调。")
    with ag_btn2:
        if st.button("保存并传递到 Tab 2", key="ag_apply_csv", use_container_width=True):
            _apply_generated_alpha(save_to_csv=True)
            st.success("已保存并传递到 Tab 2，请切换过去继续微调。")

# ===========================================================================
# TAB 2: Alpha Adjustment (piecewise Engel curve / budget share designer)
# ===========================================================================
with tab2:

    st.caption(
        "为每个收入分档分别设定 α_g_s 值，使消费结构随财富变化（恩格尔定律）。"
        "设计完成后点击「写入 mod 文件」，一次性生成所有 EU5 script_values 文件。"
    )

    bm_init_col, bm_init_info_col = st.columns([1, 3])
    with bm_init_col:
        if st.button(
            "初始化分档数据",
            key="bm_init_btn",
            help="从 alpha_table.csv 生成初始 alpha_bracket_table.csv（各档相同——退化为线性）",
        ):
            init_bracket_table_from_alpha_table()
            for key in list(st.session_state.keys()):
                if key.startswith("bm_"):
                    del st.session_state[key]
            st.rerun()
    with bm_init_info_col:
        if BRACKET_TABLE.exists():
            st.caption(f"数据文件: `{BRACKET_TABLE.relative_to(REPO_ROOT)}`")
        else:
            st.info("尚未生成分档数据。请点击左侧按钮初始化。")

    if BRACKET_TABLE.exists():
        # ---- Load / cache bracket state ----
        if "bm_initialized" not in st.session_state:
            st.session_state["bm_thresholds"] = load_bracket_thresholds(BRACKET_TABLE)
            st.session_state["bm_alpha"]      = load_bracket_table(BRACKET_TABLE)
            st.session_state["bm_initialized"] = True

        bm_thresholds: dict = st.session_state["bm_thresholds"]
        bm_alpha: dict      = st.session_state["bm_alpha"]

        # ---- Strata + bracket selectors ----
        bm_sel_col1, bm_sel_col2 = st.columns([1, 2])
        with bm_sel_col1:
            bm_strata = st.selectbox(
                "阶层",
                options=STRATA,
                format_func=lambda s: f"{s} ({STRATA_LABELS[s]})",
                key="bm_strata",
            )
        with bm_sel_col2:
            bm_s_thresholds = list(bm_thresholds.get(bm_strata, DEFAULT_THRESHOLDS.get(bm_strata, [0.0])))
            n_brackets = len(bm_s_thresholds)
            def _bracket_label(k: int) -> str:
                lo = bm_s_thresholds[k]
                hi = bm_s_thresholds[k + 1] if k + 1 < n_brackets else "∞"
                return f"bracket {k}: [{lo}, {hi})"
            bm_bracket = st.selectbox(
                "当前编辑分档",
                options=list(range(n_brackets)),
                format_func=_bracket_label,
                key="bm_bracket",
            )

        # ---- Threshold editor ----
        st.markdown(f"**{bm_strata} 分档阈值（income gold/月/pop-unit，bracket 0 固定为 0）**")
        thresh_cols = st.columns(n_brackets)
        new_thresholds = list(bm_s_thresholds)
        for k in range(n_brackets):
            with thresh_cols[k]:
                new_thresholds[k] = st.number_input(
                    f"b{k}",
                    value=float(bm_s_thresholds[k]),
                    min_value=0.0,
                    max_value=1000.0,
                    step=0.5,
                    key=f"bm_thresh_{bm_strata}_{k}",
                    disabled=(k == 0),
                )
        if new_thresholds != bm_s_thresholds:
            st.session_state["bm_thresholds"][bm_strata] = new_thresholds
            bm_s_thresholds = new_thresholds

        st.divider()

        # ---- Bracket α overview table ----
        st.markdown(f"**全分档 α 概览 — {bm_strata}**")
        overview_rows = []
        for k in range(n_brackets):
            ka = bm_alpha.get(bm_strata, {}).get(k, {})
            row = {"bracket": _bracket_label(k)}
            row.update({g: round(ka.get(g, 0.0), 5) for g in luxury_sorted_groups()})
            row["Σα"] = round(sum(ka.get(g, 0.0) for g in SUBSTITUTE_GROUPS), 5)
            overview_rows.append(row)
        ov_df = pd.DataFrame(overview_rows)
        st.dataframe(
            ov_df,
            use_container_width=True,
            hide_index=True,
            column_config={"Σα": st.column_config.NumberColumn(format="%.5f")},
        )

        st.divider()

        # ---- Per-bracket α sliders ----
        st.markdown(f"#### 分档 α 编辑器 — {bm_strata} / {_bracket_label(bm_bracket)}")
        st.caption("调整后其他未锁定组自动再分配，确保每档 Σα = 1。")

        def _P(g: str, strata: str) -> float:
            obj = cd.groups.get(g)
            return obj.base_price_sum_per_strata.get(strata, 0.0) if obj else 0.0

        # Sync slider + fine-α + fine-b keys when strata or bracket changes
        _bm_last = st.session_state.get("_bm_last_context", "")
        _bm_cur  = f"{bm_strata}_{bm_bracket}"
        if _bm_last != _bm_cur:
            bracket_init = bm_alpha.get(bm_strata, {}).get(bm_bracket, {})
            for _g in SUBSTITUTE_GROUPS:
                _a = float(bracket_init.get(_g, 0.0))
                _p = _P(_g, bm_strata)
                _b = _a / _p if _p > 0 else 0.0
                st.session_state[f"bm_share_{bm_strata}_{bm_bracket}_{_g}"] = _a
                st.session_state[f"bm_fine_{bm_strata}_{bm_bracket}_{_g}"]  = _a
                st.session_state[f"bm_b_{bm_strata}_{bm_bracket}_{_g}"]     = _b
            st.session_state["_bm_last_context"] = _bm_cur

        def _bm_apply(g_name: str, strata: str, bracket: int, new_alpha: float) -> None:
            locked = {g: st.session_state.get(f"bm_lock_{g}", False) for g in SUBSTITUTE_GROUPS}
            P_gs = {g: _P(g, strata) for g in SUBSTITUTE_GROUPS}
            temp = CurveDesignerState()
            current = st.session_state["bm_alpha"].get(strata, {}).get(bracket, {})
            temp.set_strata_shares(strata, current)
            updated = temp.apply_delta_with_locks(strata, g_name, new_alpha, locked, P_gs=P_gs)
            st.session_state["bm_alpha"][strata][bracket] = updated
            for _g, _a in updated.items():
                _a = float(_a)
                _p = _P(_g, strata)
                st.session_state[f"bm_share_{strata}_{bracket}_{_g}"] = _a
                st.session_state[f"bm_fine_{strata}_{bracket}_{_g}"]  = _a
                st.session_state[f"bm_b_{strata}_{bracket}_{_g}"]     = _a / _p if _p > 0 else 0.0

        def _bm_on_alpha_change(g_name: str, strata: str, bracket: int) -> None:
            _bm_apply(g_name, strata, bracket,
                      float(st.session_state[f"bm_share_{strata}_{bracket}_{g_name}"]))

        def _bm_on_fine_change(g_name: str, strata: str, bracket: int) -> None:
            _bm_apply(g_name, strata, bracket,
                      float(st.session_state[f"bm_fine_{strata}_{bracket}_{g_name}"]))

        def _bm_on_b_change(g_name: str, strata: str, bracket: int) -> None:
            new_b = float(st.session_state[f"bm_b_{strata}_{bracket}_{g_name}"])
            p = _P(g_name, strata)
            _bm_apply(g_name, strata, bracket, new_b * p if p > 0 else 0.0)

        bm_share_cols = st.columns(2)
        for idx, g_name in enumerate(luxury_sorted_groups()):
            with bm_share_cols[idx % 2]:
                color_hex = GROUP_COLORS.get(g_name, "#888")
                badge_col, lock_col = st.columns([0.85, 0.15])
                with badge_col:
                    goods_list = ", ".join(GROUP_GOODS.get(g_name, []))
                    st.markdown(
                        f"<span style='background-color:{color_hex};color:white;padding:2px 8px;"
                        f"border-radius:4px;font-weight:bold'>{g_name.upper()}</span> "
                        f"<small style='color:#555'>{goods_list}</small>",
                        unsafe_allow_html=True,
                    )
                with lock_col:
                    st.checkbox("🔒", key=f"bm_lock_{g_name}", label_visibility="collapsed")

                cur_alpha = bm_alpha.get(bm_strata, {}).get(bm_bracket, {}).get(g_name, 0.0)
                group_obj = cd.groups.get(g_name)
                P_g_s = group_obj.base_price_sum_per_strata.get(bm_strata, 0.0) if group_obj else 0.0
                b_g_s = (cur_alpha / P_g_s) if P_g_s > 0 else 0.0
                bm_info1, bm_info2, bm_info3 = st.columns(3)
                with bm_info1:
                    st.caption(f"α = {cur_alpha:.5f}")
                with bm_info2:
                    st.caption(f"P_g_s = {P_g_s:.4f}")
                with bm_info3:
                    st.caption(f"b = {b_g_s:.6f}")
                slider_col, fine_col, b_col = st.columns([3, 1, 1])
                with slider_col:
                    st.slider(
                        f"bm_α_{g_name}",
                        min_value=0.0,
                        max_value=1.0,
                        step=0.001,
                        key=f"bm_share_{bm_strata}_{bm_bracket}_{g_name}",
                        on_change=_bm_on_alpha_change,
                        args=(g_name, bm_strata, bm_bracket),
                        label_visibility="collapsed",
                    )
                with fine_col:
                    st.number_input(
                        "α精调",
                        min_value=0.0,
                        max_value=1.0,
                        step=0.0001,
                        format="%.5f",
                        key=f"bm_fine_{bm_strata}_{bm_bracket}_{g_name}",
                        on_change=_bm_on_fine_change,
                        args=(g_name, bm_strata, bm_bracket),
                        label_visibility="visible",
                    )
                with b_col:
                    st.number_input(
                        "b精调",
                        min_value=0.0,
                        max_value=1000.0,
                        step=0.000001,
                        format="%.6f",
                        key=f"bm_b_{bm_strata}_{bm_bracket}_{g_name}",
                        on_change=_bm_on_b_change,
                        args=(g_name, bm_strata, bm_bracket),
                        label_visibility="visible",
                    )

        bm_cur_shares = bm_alpha.get(bm_strata, {}).get(bm_bracket, {})
        bm_total = sum(bm_cur_shares.values())
        bm_valid = abs(bm_total - 1.0) < 1e-5
        st.markdown(
            f"**约束状态:** Σα = **{bm_total:.6f}** "
            f"{'✓ 满足' if bm_valid else '✗ 不满足（需重新分配）'}"
        )

        st.divider()

        # ---- View mode toggle ----
        bm_view_mode = st.radio(
            "View Mode",
            options=["per_group", "per_good"],
            format_func=lambda v: "按组 Engel 曲线 (Per-Group)" if v == "per_group" else "按商品曲线 (Per-Good)",
            horizontal=True,
            key="bm_view_mode",
        )

        income_max = max(bm_s_thresholds[-1] * 2.5, 20.0)
        income_pts = np.linspace(0, income_max, 500)

        if bm_view_mode == "per_group":
            # ===================================================================
            # PER-GROUP charts (existing behavior)
            # ===================================================================

            # ---- α(y) staircase chart ----
            st.markdown(f"#### α(y) 阶跃曲线 — {bm_strata}")
            st.caption(
                "横轴：收入；纵轴：预算份额 α_g_s。"
                "斜率跳变位置 = 分档阈值。必需品下降，奢侈品上升。"
            )
            fig_alpha = go.Figure()
            for g_name in luxury_sorted_groups():
                color = GROUP_COLORS.get(g_name, "#888")
                alpha_vals = np.zeros_like(income_pts)
                for i, y in enumerate(income_pts):
                    k = sum(1 for t in bm_s_thresholds if t <= y) - 1
                    k = max(0, min(k, n_brackets - 1))
                    alpha_vals[i] = bm_alpha.get(bm_strata, {}).get(k, {}).get(g_name, 0.0)
                fig_alpha.add_trace(go.Scatter(
                    x=income_pts, y=alpha_vals,
                    name=g_name.title(),
                    line=dict(color=color, width=2),
                    mode="lines",
                ))
            for thresh in bm_s_thresholds[1:]:
                fig_alpha.add_vline(x=thresh, line_dash="dot", line_color="gray", opacity=0.5)
            fig_alpha.update_layout(
                xaxis_title="Income (gold/月/pop-unit)",
                yaxis_title="预算份额 α_g_s",
                legend_title="Group",
                height=380,
            )
            st.plotly_chart(fig_alpha, use_container_width=True)

            # ---- Piecewise Engel demand curve ----
            st.markdown(f"#### 分档 Engel 需求曲线 — {bm_strata}")
            st.caption(
                "d_g_s(y) = (α_g_s(y) / P_g_s) × y + c_g_s(y)。"
                "d(0)=0；连续分段线性：c 保证各分档在阈值处等值，所有组需求曲线在 income=0 处共同经过 (0, 0)。"
            )
            fig_bm_engel = go.Figure()
            _bm_P_vals = {
                g: (cd.groups[g].base_price_sum_per_strata.get(bm_strata, 0.0) if cd.groups.get(g) else 0.0)
                for g in SUBSTITUTE_GROUPS
            }
            for g_name in luxury_sorted_groups():
                color = GROUP_COLORS.get(g_name, "#888")
                demand_vals = np.zeros_like(income_pts)
                group_obj = cd.groups.get(g_name)
                P_g_s = group_obj.base_price_sum_per_strata.get(bm_strata, 0.0) if group_obj else 0.0
                alpha_brackets = [
                    bm_alpha.get(bm_strata, {}).get(k, {}).get(g_name, 0.0)
                    for k in range(n_brackets)
                ]
                c_vals = compute_piecewise_offsets(alpha_brackets, bm_s_thresholds, P_g_s, d_ref=None)
                for i, y in enumerate(income_pts):
                    k = sum(1 for t in bm_s_thresholds if t <= y) - 1
                    k = max(0, min(k, n_brackets - 1))
                    demand_vals[i] = (alpha_brackets[k] / P_g_s * y + c_vals[k]) if P_g_s > 0 else 0.0
                fig_bm_engel.add_trace(go.Scatter(
                    x=income_pts, y=demand_vals,
                    name=g_name.title(),
                    line=dict(color=color, width=2),
                ))
            for thresh in bm_s_thresholds[1:]:
                fig_bm_engel.add_vline(x=thresh, line_dash="dot", line_color="gray", opacity=0.5)
            fig_bm_engel.update_layout(
                xaxis_title="Income (gold/月/pop-unit)",
                yaxis_title=f"Group Demand ({bm_strata})",
                legend_title="Group",
                height=380,
            )
            st.plotly_chart(fig_bm_engel, use_container_width=True)

        else:
            # ===================================================================
            # PER-GOOD charts (new)
            # ===================================================================

            # ---- Per-good demand share bar chart ----
            st.markdown(f"#### 商品需求份额 — {bm_strata} / {_bracket_label(bm_bracket)}")
            st.caption("每组的 budget share (α_g_s) 按 k-factor 权重分配到组内各商品。")

            bracket_alphas = bm_alpha.get(bm_strata, {}).get(bm_bracket, {})
            fig_share = go.Figure()
            for g_name in luxury_sorted_groups():
                alpha_g = bracket_alphas.get(g_name, 0.0)
                if alpha_g <= 0:
                    continue
                group_goods = GROUP_GOODS.get(g_name, [])
                color = GROUP_COLORS.get(g_name, "#888")
                for good in group_goods:
                    share = cd.goods_weight_store.good_share_in_group(good, g_name)
                    goods_label = f"{good} ({g_name})" if len(groups_for_good(good)) > 1 else good
                    fig_share.add_trace(go.Bar(
                        name=goods_label,
                        y=[g_name.replace("_", " ").title()],
                        x=[share * alpha_g],
                        orientation="h",
                        marker=dict(color=color, opacity=0.7 + 0.3 * share),
                        text=f"{good} {share*100:.0f}%",
                        textposition="inside",
                        insidetextanchor="middle",
                        legendgroup=g_name,
                        showlegend=False,
                    ))
            if len(fig_share.data) == 0:
                st.info("当前分档无有效 alpha 值。")
            else:
                fig_share.update_layout(
                    barmode="stack",
                    xaxis_title="Demand Share (share × α_g_s)",
                    height=420,
                    showlegend=False,
                    margin=dict(l=20, r=20, t=20, b=40),
                )
                st.plotly_chart(fig_share, use_container_width=True)

            # ---- Per-good Engel demand curves ----
            st.markdown(f"#### 分档商品 Engel 需求曲线 — {bm_strata}")
            st.caption(
                "d_i(y) = Σ_g share_i_g × (α_g_s(y) / P_g_s × y + c_g_s(y))。"
                "跨组商品（如 cloth, wine 等）自动汇总所有所在组的贡献。"
            )

            alpha_brackets_list = [
                bm_alpha.get(bm_strata, {}).get(k, {})
                for k in range(n_brackets)
            ]

            per_good_curves = cd.compute_per_good_curve_points(
                bm_strata, income_pts, alpha_brackets_list, list(bm_s_thresholds),
            )

            # Prepare per-good curves; sort by max demand (for filter)
            good_demand_at_max = sorted(
                [(good, float(curve[-1])) for good, curve in per_good_curves.items()],
                key=lambda x: -x[1],
            )
            top_n = 15
            top_goods = [g for g, _ in good_demand_at_max[:top_n] if good_demand_at_max[0][1] > 0]
            selected_goods = st.multiselect(
                "显示商品（默认按需求排序前15）",
                options=[g for g, _ in good_demand_at_max],
                default=top_goods,
                key="bm_goods_filter",
            )

            fig_good_engel = go.Figure()
            # Color palette for per-good: use the first group's color for each good
            for good in selected_goods:
                primary_group = groups_for_good(good)[0] if groups_for_good(good) else ""
                color = GROUP_COLORS.get(primary_group, "#888")
                curve = per_good_curves[good]
                label = f"{good}" + ("†" if len(groups_for_good(good)) > 1 else "")
                fig_good_engel.add_trace(go.Scatter(
                    x=income_pts, y=curve,
                    name=label,
                    line=dict(color=color, width=2 if len(groups_for_good(good)) > 1 else 1.5),
                ))
            for thresh in bm_s_thresholds[1:]:
                fig_good_engel.add_vline(x=thresh, line_dash="dot", line_color="gray", opacity=0.5)
            fig_good_engel.update_layout(
                xaxis_title="Income (gold/月/pop-unit)",
                yaxis_title=f"Good Demand ({bm_strata})",
                legend_title="Good († = multi-group)",
                height=420,
            )
            st.plotly_chart(fig_good_engel, use_container_width=True)

        st.divider()

        # ---- Write to mod ----
        if st.button("写入 mod 文件", type="primary", use_container_width=True, key="bm_write_btn",
                     help="保存 CSV → 写入 group_prices + budget_shares + demand_offsets + demand_base + demand_scales"):
            errs = validate_all_bracket_constraints(bm_alpha)
            if errs:
                for e in errs:
                    st.error(e)
                st.error("存在约束违反，请修复后再写入。")
            else:
                try:
                    save_bracket_table(bm_alpha, bm_thresholds, BRACKET_TABLE)

                    out_prices = export_group_prices()
                    st.write(f"✓ `{out_prices.relative_to(REPO_ROOT)}`")

                    warns = export_bracket_budget_shares(bm_alpha, bm_thresholds, ENGEL_BUDGET_SHARES_FILE)
                    for w in warns:
                        st.warning(w)
                    st.write(f"✓ `{ENGEL_BUDGET_SHARES_FILE.relative_to(REPO_ROOT)}`")

                    P_values = {
                        s: {
                            g: (cd.groups[g].base_price_sum_per_strata.get(s, 0.0) if cd.groups.get(g) else 0.0)
                            for g in SUBSTITUTE_GROUPS
                        }
                        for s in STRATA
                    }
                    warns2 = export_demand_offsets(bm_alpha, bm_thresholds, P_values, DEMAND_OFFSETS_FILE)
                    for w in warns2:
                        st.warning(w)
                    st.write(f"✓ `{DEMAND_OFFSETS_FILE.relative_to(REPO_ROOT)}`")

                    export_demand_base(P_values, DEMAND_BASE_FILE)
                    st.write(f"✓ `{DEMAND_BASE_FILE.relative_to(REPO_ROOT)}`")

                    export_demand_scales_with_offset(DEMAND_SCALES_FILE)
                    st.write(f"✓ `{DEMAND_SCALES_FILE.relative_to(REPO_ROOT)}`")

                    st.success("全部写入完成")
                except Exception as e:
                    st.error(f"写入失败: {e}")

# ===========================================================================
# TAB 3: Savings Dynamics — simplified single-variable model
# ===========================================================================
with tab3:
    st.subheader("Savings pressure dynamics — simplified single-variable model")
    st.caption(
        "Model: Δsavings = −income × saving_pressure(savings / target − 1). "
        "Saving pressure recalculates every N months (update frequency); held constant between updates."
    )

    ctrl_col, mode_col = st.columns([1, 1])

    with ctrl_col:
        st.markdown("**Simulation Parameters**")
        sd_income  = st.number_input("Income (per month)", value=10.0, min_value=0.01, step=1.0, key="sd_income")
        sd_target  = st.number_input("Savings target",     value=100.0, min_value=1.0, step=10.0, key="sd_target")
        sd_initial = st.number_input("Initial savings",    value=0.0, step=10.0, key="sd_initial")
        sd_months  = st.slider("Duration (months)", min_value=12, max_value=480, value=120, step=12, key="sd_months")
        sd_freq    = st.slider("Update frequency (months)", min_value=1, max_value=60, value=12, key="sd_freq")

    with mode_col:
        st.markdown("**Pressure Function**")
        sd_mode = st.selectbox(
            "Mode", options=list(PRESSURE_MODES.keys()),
            format_func=lambda k: PRESSURE_MODES[k], key="sd_mode",
        )
        sd_pmin = st.number_input("pmin", value=-0.50, min_value=-5.0, max_value=0.0,
                                   step=0.1, format="%.2f", key="sd_pmin")
        sd_pmax = st.number_input("pmax", value=2.00, min_value=0.01, max_value=10.0,
                                   step=0.1, format="%.2f", key="sd_pmax")
        sd_slope = sd_k = sd_norm = sd_delta = 0.0
        if sd_mode == "linear":
            sd_slope = st.number_input("Slope", value=0.50, min_value=0.0, max_value=10.0,
                                        step=0.1, key="sd_slope_linear")
        elif sd_mode == "tanh":
            sd_k = st.number_input("Steepness k", value=1.0, min_value=0.01, max_value=20.0,
                                    step=0.1, key="sd_k")
        elif sd_mode == "quadratic":
            sd_norm = st.number_input("Norm", value=2.0, min_value=0.1, max_value=20.0,
                                       step=0.1, key="sd_norm")
        else:  # deadband
            sd_delta = st.number_input("Deadband δ", value=0.15, min_value=0.0, max_value=1.0,
                                        step=0.01, format="%.2f", key="sd_delta")
            sd_slope = st.number_input("Slope (outside band)", value=0.50, min_value=0.0,
                                        max_value=10.0, step=0.1, key="sd_slope_deadband")

    # --- Simulation ---
    def _run_savings_sim(income, target, initial, n_months, freq, mode, pmin, pmax, slope, k, norm, delta):
        rows, savings, sp = [], float(initial), 0.0
        for t in range(int(n_months)):
            if t % max(1, int(freq)) == 0:
                ratio = savings / max(1e-9, float(target))
                sp = float(savings_pressure_curve_np(
                    np.array([ratio]), pmin, pmax, mode, slope, k, norm, delta
                )[0])
            rows.append({"month": t + 1, "savings": savings, "saving_pressure": sp})
            savings += -float(income) * sp
        return pd.DataFrame(rows)

    df_sd = _run_savings_sim(
        sd_income, sd_target, sd_initial, sd_months, sd_freq,
        sd_mode, sd_pmin, sd_pmax, sd_slope, sd_k, sd_norm, sd_delta,
    )

    # --- Chart 1: Savings over time ---
    fig_sav = go.Figure()
    fig_sav.add_trace(go.Scatter(
        x=df_sd["month"], y=df_sd["savings"],
        name="Savings", line=dict(color="#4e9af1", width=2),
    ))
    fig_sav.add_hline(y=sd_target, line_dash="dash", line_color="gray",
                       annotation_text="Target", annotation_position="right")
    fig_sav.update_layout(
        xaxis_title="Month", yaxis_title="Savings",
        title="Savings over time", height=320,
    )
    st.plotly_chart(fig_sav, use_container_width=True)

    # --- Chart 2: Saving pressure over time ---
    fig_sp = go.Figure()
    fig_sp.add_trace(go.Scatter(
        x=df_sd["month"], y=df_sd["saving_pressure"],
        name="Saving pressure", line=dict(color="#e8b84b", width=2, shape="hv"),
    ))
    fig_sp.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_sp.update_layout(
        xaxis_title="Month", yaxis_title="Saving pressure",
        title="Saving pressure over time (staircase = update interval)", height=250,
    )
    st.plotly_chart(fig_sp, use_container_width=True)

    # --- Chart 3: Pressure curve preview ---
    x_ratio = np.linspace(0.0, 3.0, 500)
    y_curve = savings_pressure_curve_np(x_ratio, sd_pmin, sd_pmax, sd_mode, sd_slope, sd_k, sd_norm, sd_delta)
    final_ratio = float(df_sd["savings"].iloc[-1]) / max(1e-9, sd_target)
    fig_curve = go.Figure()
    fig_curve.add_trace(go.Scatter(
        x=x_ratio, y=y_curve,
        name="Pressure curve", line=dict(color="#6ab04c", width=2),
    ))
    fig_curve.add_vline(x=final_ratio, line_dash="dot", line_color="#c0392b",
                         annotation_text=f"Final ratio={final_ratio:.2f}",
                         annotation_position="top right")
    fig_curve.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_curve.update_layout(
        xaxis_title="savings / target",
        yaxis_title="saving_pressure",
        title="Pressure curve (marker = final state)",
        height=280,
    )
    st.plotly_chart(fig_curve, use_container_width=True)

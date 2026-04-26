"""
EU5 SOL Demand Simulator — Streamlit UI (v2)

Two tabs:
  Tab 1 — Alpha Adjustment: piecewise Engel curve / budget share designer
  Tab 2 — Savings Dynamics: simplified single-variable savings pressure simulator

Run:
    cd tools/sol_demand_simulator
    pip install -r requirements.txt
    streamlit run app.py
"""
from __future__ import annotations

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
    CurveDesignerState,
    luxury_sorted_groups,
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
demand_matrix_w = _reweight_commoners(demand_matrix, 400.0, 500.0, 100.0)

STRATA_LABELS = {
    "nobles":    "贵族 Nobles",
    "clergy":    "教士 Clergy",
    "burghers":  "商人 Burghers",
    "commoners": "平民 Commoners",
    "tribesmen": "部落民 Tribesmen",
}

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------

tab1, tab2 = st.tabs([
    "Tab 1 — Alpha Adjustment",
    "Tab 2 — Savings Dynamics",
])

# ===========================================================================
# TAB 1: Alpha Adjustment (piecewise Engel curve / budget share designer)
# ===========================================================================
with tab1:
    # Silent init — needed for P_g_s access in bracket charts
    if "curve_designer" not in st.session_state:
        cd = CurveDesignerState()
        cd.init_from_demand_matrix(demand_matrix_w)
        st.session_state["curve_designer"] = cd
    cd: CurveDesignerState = st.session_state["curve_designer"]

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

        # ---- α(y) staircase chart ----
        st.markdown(f"#### α(y) 阶跃曲线 — {bm_strata}")
        st.caption(
            "横轴：收入；纵轴：预算份额 α_g_s。"
            "斜率跳变位置 = 分档阈值。必需品下降，奢侈品上升。"
        )
        income_max = max(bm_s_thresholds[-1] * 2.5, 20.0)
        income_pts = np.linspace(0, income_max, 500)
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
            "连续分段线性：c 保证各分档在阈值处等值（c_0 = 0）。"
        )
        fig_bm_engel = go.Figure()
        for g_name in luxury_sorted_groups():
            color = GROUP_COLORS.get(g_name, "#888")
            demand_vals = np.zeros_like(income_pts)
            group_obj = cd.groups.get(g_name)
            P_g_s = group_obj.base_price_sum_per_strata.get(bm_strata, 0.0) if group_obj else 0.0
            alpha_brackets = [
                bm_alpha.get(bm_strata, {}).get(k, {}).get(g_name, 0.0)
                for k in range(n_brackets)
            ]
            c_vals = compute_piecewise_offsets(alpha_brackets, bm_s_thresholds, P_g_s)
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
# TAB 2: Savings Dynamics — simplified single-variable model
# ===========================================================================
with tab2:
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

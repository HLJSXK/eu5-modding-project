"""
EU5 SOL Demand Simulator — Streamlit UI

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

# Ensure local imports resolve when launched from any CWD
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from parser import EU5_POP_TYPES, STRATA, STRATA_TO_POP_TYPES, load_demand_matrix, load_goods_prices
from simulator import (
    PRESETS,
    STRATA_PARAMS,
    ScenarioParams,
    StrataState,
    compute_base_demand_index,
    compute_demand_scale,
    compute_monthly_income_from_gdp,
    compute_savings_targets,
    fn1_gdp_per_capita,
    fn2_gdp_nonlinear,
    fn3_savings_pressure,
    simulate,
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
st.caption(
    "Offline visualizer for the Standard of Living (SOL) mod demand system. "
    "Reads live mod files — no hardcoded values."
)

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading goods prices…")
def _load_prices():
    return load_goods_prices()

@st.cache_data(show_spinner="Parsing demand file…")
def _load_matrix():
    return load_demand_matrix()

prices        = _load_prices()
demand_matrix = _load_matrix()


def _reweight_commoners(dm: dict, pop_lab: float, pop_peas: float, pop_sold: float) -> dict:
    """
    Return a copy of the demand matrix where strata_demand["commoners"] is
    recomputed as a population-weighted average of laborers / peasants / soldiers
    demands instead of the default arithmetic mean.
    """
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

# ---------------------------------------------------------------------------
# User preset persistence
# ---------------------------------------------------------------------------

PRESETS_FILE = Path(__file__).parent / "user_presets.json"


def load_user_presets() -> dict:
    if not PRESETS_FILE.exists():
        return {}
    try:
        return json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_user_presets(presets: dict) -> None:
    PRESETS_FILE.write_text(json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8")


def dict_to_params(d: dict) -> ScenarioParams:
    comm_total = d["strata"].get("commoners", {}).get("pop_count", 0.0)
    each = comm_total / 3.0
    return ScenarioParams(
        monthly_income          = d["monthly_income"],
        num_institutions        = d["num_institutions"],
        tax_base                = d["tax_base"],
        effective_control       = d["effective_control"],
        peasant_enfranchisement = d["peasant_enfranchisement"],
        pop_laborers            = d.get("pop_laborers", each),
        pop_peasants            = d.get("pop_peasants", each),
        pop_soldiers            = d.get("pop_soldiers", each),
        update_interval_years   = d["update_interval_years"],
        sim_years               = d["sim_years"],
        ema_alpha               = d.get("ema_alpha", 1.0),
        strata = {
            s: StrataState(v["pop_count"], v["tax_rate"], v["savings"])
            for s, v in d["strata"].items()
        },
    )

# ---------------------------------------------------------------------------
# Sidebar — Scenario configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Scenario Setup")

    # ---- Preset management ----
    user_presets  = load_user_presets()
    builtin_names = list(PRESETS.keys())
    user_names    = list(user_presets.keys())

    # Built-ins shown plain; user presets prefixed with "★ "
    all_options  = ["(custom)"] + builtin_names + [f"★ {n}" for n in user_names]
    selected_opt = st.selectbox("Presets", all_options, key="preset_select")

    is_custom   = selected_opt == "(custom)"
    is_user     = selected_opt.startswith("★ ")
    actual_name = selected_opt[2:] if is_user else selected_opt

    col_load, col_del = st.columns([3, 2])
    with col_load:
        load_clicked = st.button("Load", disabled=is_custom, use_container_width=True)
    with col_del:
        del_clicked  = st.button("Delete", disabled=not is_user, use_container_width=True)

    if load_clicked:
        st.session_state["_preset"] = (
            dict_to_params(user_presets[actual_name]) if is_user
            else PRESETS[actual_name]()
        )
        st.rerun()

    if del_clicked:
        ups = load_user_presets()
        ups.pop(actual_name, None)
        save_user_presets(ups)
        st.session_state.pop("_preset", None)
        st.rerun()

    preset: ScenarioParams | None = st.session_state.get("_preset")

    def _pv(key, default):
        """Get preset value or default."""
        if preset is None:
            return default
        return getattr(preset, key, default)

    def _sv(strata_key, attr, default):
        """Get preset strata value or default."""
        if preset is None or preset.strata.get(strata_key) is None:
            return default
        return getattr(preset.strata[strata_key], attr, default)

    st.subheader("Country")
    monthly_income   = st.number_input("Monthly income (gold/month)",
                                       min_value=0.0,
                                       value=float(_pv("monthly_income", 30)),
                                       step=5.0, help="owner.monthly_income_trade_and_tax — drives savings targets")
    num_institutions = st.slider("Embraced institutions", 0, 10,
                                 int(_pv("num_institutions", 2)),
                                 help="+5% demand per institution")

    st.subheader("Location")
    tax_base          = st.number_input("Tax base (gold/month)",
                                        min_value=0.0,
                                        value=float(_pv("tax_base", 8)),
                                        step=1.0, help="location_tax_base")
    effective_control = st.slider("Effective control (%)", 1, 100,
                                  int(_pv("effective_control", 0.75) * 100),
                                  help="local_effective_control") / 100.0
    enfranchisement   = st.slider("Peasant enfranchisement", 0.1, 1.0,
                                  float(_pv("peasant_enfranchisement", 0.5)),
                                  step=0.05,
                                  help="1.0 = full freedom; 0.1 = maximum serfdom (commoner wealth → nobles)")

    st.subheader("Pop Counts (per strata)")
    pop_nobles    = st.number_input("Nobles",    min_value=0.0, value=float(_sv("nobles",    "pop_count", 0.2)),  step=0.05)
    pop_clergy    = st.number_input("Clergy",    min_value=0.0, value=float(_sv("clergy",    "pop_count", 0.15)), step=0.05)
    pop_burghers  = st.number_input("Burghers",  min_value=0.0, value=float(_sv("burghers",  "pop_count", 0.15)), step=0.05)
    _comm_total = float(_sv("commoners", "pop_count", 2.0))
    _comm_each  = round(_comm_total / 3, 4)
    pop_laborers  = st.number_input("  Laborers",  min_value=0.0, value=float(_pv("pop_laborers",  _comm_each)), step=0.05)
    pop_peasants  = st.number_input("  Peasants",  min_value=0.0, value=float(_pv("pop_peasants",  _comm_each)), step=0.05)
    pop_soldiers  = st.number_input("  Soldiers",  min_value=0.0, value=float(_pv("pop_soldiers",  _comm_each)), step=0.05)
    pop_commoners = pop_laborers + pop_peasants + pop_soldiers
    st.caption(f"Commoners total: {pop_commoners:.3f}")
    pop_tribesmen = st.number_input("Tribesmen", min_value=0.0, value=float(_sv("tribesmen", "pop_count", 0.0)),  step=0.05)

    st.subheader("Tax Rates (% of income to crown)")
    tr_nobles    = st.slider("Nobles tax",    0, 100, int(_sv("nobles",    "tax_rate", 0.15) * 100)) / 100
    tr_clergy    = st.slider("Clergy tax",    0, 100, int(_sv("clergy",    "tax_rate", 0.10) * 100)) / 100
    tr_burghers  = st.slider("Burghers tax",  0, 100, int(_sv("burghers",  "tax_rate", 0.10) * 100)) / 100
    tr_commoners = st.slider("Commoners tax", 0, 100, int(_sv("commoners", "tax_rate", 0.05) * 100)) / 100
    tr_tribesmen = st.slider("Tribesmen tax", 0, 100, int(_sv("tribesmen", "tax_rate", 0.00) * 100)) / 100

    st.subheader("Initial Savings (estate gold)")
    sv_nobles    = st.number_input("Nobles savings",    min_value=0.0, value=float(_sv("nobles",    "savings", 0)), step=50.0)
    sv_clergy    = st.number_input("Clergy savings",    min_value=0.0, value=float(_sv("clergy",    "savings", 0)), step=50.0)
    sv_burghers  = st.number_input("Burghers savings",  min_value=0.0, value=float(_sv("burghers",  "savings", 0)), step=50.0)
    sv_commoners = st.number_input("Commoners savings", min_value=0.0, value=float(_sv("commoners", "savings", 0)), step=50.0)
    sv_tribesmen = st.number_input("Tribesmen savings", min_value=0.0, value=float(_sv("tribesmen", "savings", 0)), step=50.0)

    st.subheader("Simulation Settings")
    update_interval  = st.radio("Demand update interval (years)", [1, 2, 3],
                                index=int(_pv("update_interval_years", 2)) - 1,
                                horizontal=True)
    _sim_opts = [10, 25, 50, 100]
    _sim_raw  = int(_pv("sim_years", 25))
    _sim_val  = min(_sim_opts, key=lambda x: abs(x - _sim_raw))  # snap to nearest valid
    sim_years = st.select_slider("Simulation duration (years)", _sim_opts, value=_sim_val)
    ema_alpha = st.slider(
        "EMA smoothing α",
        min_value=0.05, max_value=1.0,
        value=float(_pv("ema_alpha", 1.0)),
        step=0.05,
        help="d_new = α × d_computed + (1−α) × d_old  |  1.0 = no smoothing (vanilla); lower values damp oscillation",
    )

    # ---- Save / overwrite user preset ----
    st.divider()
    st.markdown("**Save current scenario as preset**")
    _default_name   = actual_name if is_user else ""
    save_name_input = st.text_input("Name", value=_default_name,
                                    placeholder="Preset name…",
                                    label_visibility="collapsed")
    _name     = save_name_input.strip()
    _btn_label = "Overwrite" if _name in user_presets else "Save"
    if _name in builtin_names and _name not in user_presets:
        st.caption("⚠️ Same name as a built-in preset.")

    if st.button(_btn_label, disabled=not _name, use_container_width=True, type="primary"):
        ups = load_user_presets()
        ups[_name] = {
            "monthly_income":        monthly_income,
            "num_institutions":      num_institutions,
            "tax_base":              tax_base,
            "effective_control":     effective_control,
            "peasant_enfranchisement": enfranchisement,
            "update_interval_years": int(update_interval),
            "sim_years":             int(sim_years),
            "ema_alpha":             float(ema_alpha),
            "pop_laborers":          pop_laborers,
            "pop_peasants":          pop_peasants,
            "pop_soldiers":          pop_soldiers,
            "strata": {
                "nobles":    {"pop_count": pop_nobles,    "tax_rate": tr_nobles,    "savings": sv_nobles},
                "clergy":    {"pop_count": pop_clergy,    "tax_rate": tr_clergy,    "savings": sv_clergy},
                "burghers":  {"pop_count": pop_burghers,  "tax_rate": tr_burghers,  "savings": sv_burghers},
                "commoners": {"pop_count": pop_commoners, "tax_rate": tr_commoners, "savings": sv_commoners},
                "tribesmen": {"pop_count": pop_tribesmen, "tax_rate": tr_tribesmen, "savings": sv_tribesmen},
            },
        }
        save_user_presets(ups)
        st.success(f"Saved '{_name}'")
        st.rerun()

    col_clr, col_rel = st.columns(2)
    with col_clr:
        if st.button("Clear / Reset", use_container_width=True):
            st.session_state.pop("_preset", None)
            st.rerun()
    with col_rel:
        if st.button("Reload files", use_container_width=True,
                     help="Re-parse mod files (use after editing demand values)"):
            st.cache_data.clear()
            st.rerun()

# ---------------------------------------------------------------------------
# Build scenario from sidebar
# ---------------------------------------------------------------------------

params = ScenarioParams(
    monthly_income          = monthly_income,
    num_institutions        = num_institutions,
    tax_base                = tax_base,
    effective_control       = effective_control,
    peasant_enfranchisement = enfranchisement,
    pop_laborers            = pop_laborers,
    pop_peasants            = pop_peasants,
    pop_soldiers            = pop_soldiers,
    strata = {
        "nobles":    StrataState(pop_nobles,    tr_nobles,    sv_nobles),
        "clergy":    StrataState(pop_clergy,    tr_clergy,    sv_clergy),
        "burghers":  StrataState(pop_burghers,  tr_burghers,  sv_burghers),
        "commoners": StrataState(pop_commoners, tr_commoners, sv_commoners),
        "tribesmen": StrataState(pop_tribesmen, tr_tribesmen, sv_tribesmen),
    },
    update_interval_years = int(update_interval),
    sim_years             = int(sim_years),
    ema_alpha             = float(ema_alpha),
)

# ---------------------------------------------------------------------------
# Reweight commoners demand by actual sub-pop counts, then compute state
# ---------------------------------------------------------------------------

demand_matrix_w = _reweight_commoners(demand_matrix, pop_laborers, pop_peasants, pop_soldiers)

gdp_pc       = fn1_gdp_per_capita(params)
nl           = fn2_gdp_nonlinear(gdp_pc)
sp_pressure  = fn3_savings_pressure(params, {s: params.strata[s].savings for s in STRATA})
d_scale      = compute_demand_scale(params)
sav_targets  = compute_savings_targets(params)
income_est   = compute_monthly_income_from_gdp(params)
base_idx     = compute_base_demand_index(demand_matrix_w)

STRATA_COLORS = {
    "nobles":    "#e8b84b",
    "clergy":    "#8e7ab5",
    "burghers":  "#4e9af1",
    "commoners": "#6ab04c",
    "tribesmen": "#c0392b",
}
STRATA_LABELS = {
    "nobles":    "贵族 Nobles",
    "clergy":    "教士 Clergy",
    "burghers":  "商人 Burghers",
    "commoners": "平民 Commoners",
    "tribesmen": "部落民 Tribesmen",
}

# ---------------------------------------------------------------------------
# Global strata filter
# ---------------------------------------------------------------------------

active_strata = st.multiselect(
    "Display strata",
    options=STRATA,
    default=STRATA,
    format_func=lambda s: STRATA_LABELS[s],
    key="active_strata_filter",
)
if not active_strata:
    active_strata = list(STRATA)

# EU5 pop types that belong to the selected strata (for Tab 1 detail table)
active_pop_types = [pt for s in active_strata for pt in STRATA_TO_POP_TYPES[s]]

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    "Tab 1 — Base Goods Demand",
    "Tab 2 — Scaling Functions",
    "Tab 3 — Time Simulation",
])

# ===========================================================================
# TAB 1: Base Goods Demand Table
# ===========================================================================
with tab1:
    st.subheader("Base goods demand per 1000 pops (vanilla + inject, before SOL scaling)")
    st.caption(
        "Formula: **(vanilla_demand_add × vanilla_demand_multiply + inject_demand_add) × inject_demand_multiply**  |  "
        "Values = units consumed per 1000 pops per month at demand_scale = 1.  "
        "Price-weighted spend = demand × price."
    )

    # ---- Per-pop-type detail table ----
    st.markdown("#### By EU5 pop type (full breakdown)")
    rows_pt = []
    for good, entry in demand_matrix_w.items():
        row: dict = {"Good": good, "Price": entry.price, "Category": entry.category}
        total_spend = 0.0
        for pt in EU5_POP_TYPES:
            d = entry.demand_per_pop_type.get(pt, 0.0)
            row[pt]              = round(d, 6)
            row[f"spend_{pt}"]   = round(d * entry.price, 6)
            total_spend += d * entry.price
        row["Spend/pop avg"] = round(total_spend / len(EU5_POP_TYPES), 6)
        rows_pt.append(row)

    df_pt = pd.DataFrame(rows_pt).sort_values("Spend/pop avg", ascending=False)

    # Only show demand columns for pop types belonging to selected strata
    pt_display_cols = ["Good", "Category", "Price"] + active_pop_types + ["Spend/pop avg"]
    st.dataframe(
        df_pt[pt_display_cols].reset_index(drop=True),
        use_container_width=True,
        height=420,
        column_config={
            "Price":         st.column_config.NumberColumn(format="%.2f"),
            "Spend/pop avg": st.column_config.ProgressColumn(
                min_value=0, max_value=df_pt["Spend/pop avg"].max() * 1.05,
                format="%.5f",
            ),
        },
    )

    st.divider()

    # ---- Aggregated strata table with current demand_scale applied ----
    st.markdown("#### By simulator strata (aggregated), with current demand_scale")
    st.caption(
        "Base = (vanilla × mult + inject) × inject_mult per strata aggregate  |  "
        "Scaled = Base × sol_gdp_per_capita_scale at current scenario state"
    )

    # Summary metrics row
    col_headers = st.columns(len(active_strata) + 1)
    col_headers[0].metric("Goods with demand", len(demand_matrix))
    for i, s in enumerate(active_strata):
        base_annual = base_idx[s]
        scaled      = base_annual * d_scale[s]
        col_headers[i + 1].metric(
            label=STRATA_LABELS[s],
            value=f"{scaled:.4f}",
            delta=f"×{d_scale[s]:.2f} scale",
            help=f"Σ(demand × price) at scale=1: {base_annual:.5f}",
        )

    rows_strata = []
    for good, entry in demand_matrix_w.items():
        row = {"Good": good, "Price": entry.price, "Category": entry.category}
        spend_sum = 0.0
        for s in STRATA:
            base_d   = entry.strata_demand[s]
            scaled_d = base_d * d_scale[s]
            spend_sum += scaled_d * entry.price
            row[f"Base ({s[:3].title()})"]   = round(base_d,   6)
            row[f"Scaled ({s[:3].title()})"] = round(scaled_d, 6)
        row["Scaled spend sum"] = round(spend_sum, 5)
        rows_strata.append(row)

    df_strata = pd.DataFrame(rows_strata).sort_values("Scaled spend sum", ascending=False)
    display_cols = ["Good", "Category", "Price"]
    for s in active_strata:
        display_cols.append(f"Base ({s[:3].title()})")
    display_cols.append("Scaled spend sum")

    st.dataframe(
        df_strata[display_cols].reset_index(drop=True),
        use_container_width=True,
        height=420,
        column_config={
            "Price":            st.column_config.NumberColumn(format="%.2f"),
            "Scaled spend sum": st.column_config.ProgressColumn(
                min_value=0, max_value=df_strata["Scaled spend sum"].max() * 1.05,
                format="%.4f",
            ),
        },
    )

    st.subheader("Current demand scale (at scenario state)")
    ds_df = pd.DataFrame({
        "Strata":           [STRATA_LABELS[s] for s in active_strata],
        "GDP/cap":          [round(gdp_pc[s], 3)    for s in active_strata],
        "GDP nonlinear":    [round(nl[s], 3)         for s in active_strata],
        "Savings pressure": [round(sp_pressure[s], 3) for s in active_strata],
        "Demand scale":     [round(d_scale[s], 3)    for s in active_strata],
        "Savings":          [round(params.strata[s].savings, 1) for s in active_strata],
        "Savings target":   [round(sav_targets[s], 1) for s in active_strata],
        "Savings ratio":    [round(params.strata[s].savings / max(1e-9, sav_targets[s]), 2) for s in active_strata],
    })
    st.dataframe(ds_df, use_container_width=True, hide_index=True)


# ===========================================================================
# TAB 2: Scaling Function Explorer
# ===========================================================================
with tab2:
    st.subheader("Scaling function curves")
    st.caption(
        "These charts show the three mathematical functions from **SOL_pop_values.txt** "
        "across the full input range. The vertical marker shows the current scenario value."
    )

    # ---- Chart 1: GDP nonlinear component vs GDP per capita ----
    st.markdown("#### Function 2 — Nonlinear GDP component  `local_*_gdp_nonlinear_component`")
    st.caption(
        "`sol_pressure = gdp_per_cap × sensitivity − threshold`  →  "
        "`nonlinear = sol_pressure / (1 + sol_pressure × 0.45)`"
    )

    x_gdp = np.linspace(0, 15, 400)
    fig1 = go.Figure()
    for s in active_strata:
        sens, thresh, _, _ = STRATA_PARAMS[s]
        sp   = x_gdp * sens - thresh
        denom = np.maximum(0.05, 1.0 + sp * 0.45)
        y_nl = sp / denom
        fig1.add_trace(go.Scatter(
            x=x_gdp, y=y_nl,
            name=STRATA_LABELS[s],
            line=dict(color=STRATA_COLORS[s], width=2),
        ))
        # Mark current scenario position
        current_x = gdp_pc[s]
        current_y = nl[s]
        fig1.add_trace(go.Scatter(
            x=[current_x], y=[current_y],
            mode="markers", marker=dict(size=10, color=STRATA_COLORS[s], symbol="diamond"),
            showlegend=False, name=f"{s} (current)",
        ))

    fig1.add_hline(y=0, line_dash="dot", line_color="gray")
    fig1.update_layout(
        xaxis_title="GDP per capita (gold/month per pop-unit)",
        yaxis_title="GDP nonlinear component",
        legend_title="Strata",
        height=380,
    )
    st.plotly_chart(fig1, use_container_width=True)

    # ---- Chart 2: Savings pressure vs savings/target ratio ----
    st.markdown("#### Function 3 — Savings pressure  `local_*_savings_pressure`")
    st.caption(
        "`pressure = clamp( (savings/target − 1) × 0.50,  −0.50,  max )`"
    )

    x_ratio = np.linspace(0, 8, 400)
    fig2 = go.Figure()
    for s in active_strata:
        _, _, pmin, pmax = STRATA_PARAMS[s]
        raw  = (x_ratio - 1.0) * 0.50
        y_sp = np.clip(raw, pmin, pmax)
        fig2.add_trace(go.Scatter(
            x=x_ratio, y=y_sp,
            name=STRATA_LABELS[s],
            line=dict(color=STRATA_COLORS[s], width=2),
        ))
        # Mark current
        current_ratio = params.strata[s].savings / max(1e-9, sav_targets[s])
        current_sp    = sp_pressure[s]
        fig2.add_trace(go.Scatter(
            x=[current_ratio], y=[current_sp],
            mode="markers", marker=dict(size=10, color=STRATA_COLORS[s], symbol="diamond"),
            showlegend=False,
        ))

    fig2.add_hline(y=0, line_dash="dot", line_color="gray")
    fig2.update_layout(
        xaxis_title="Savings / Savings Target ratio",
        yaxis_title="Savings pressure",
        legend_title="Strata",
        height=380,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ---- Chart 3: Combined demand scale vs savings ratio ----
    st.markdown("#### Combined — `sol_gdp_per_capita_scale` vs savings ratio")
    st.caption(
        "`scale = 1 + institutions×0.05 + gdp_nonlinear + savings_pressure`  "
        "(gdp_nonlinear is fixed at the current scenario GDP; savings ratio varies)"
    )

    fig3 = go.Figure()
    for s in active_strata:
        _, _, pmin, pmax = STRATA_PARAMS[s]
        inst_bon = num_institutions * 0.05
        raw  = (x_ratio - 1.0) * 0.50
        y_sp = np.clip(raw, pmin, pmax)
        y_sc = 1.0 + inst_bon + nl[s] + y_sp
        fig3.add_trace(go.Scatter(
            x=x_ratio, y=y_sc,
            name=STRATA_LABELS[s],
            line=dict(color=STRATA_COLORS[s], width=2),
        ))
        # Mark current
        current_ratio = params.strata[s].savings / max(1e-9, sav_targets[s])
        current_scale = d_scale[s]
        fig3.add_trace(go.Scatter(
            x=[current_ratio], y=[current_scale],
            mode="markers", marker=dict(size=10, color=STRATA_COLORS[s], symbol="diamond"),
            showlegend=False,
        ))

    fig3.add_hline(y=1.0, line_dash="dot", line_color="gray", annotation_text="scale=1 baseline")
    fig3.update_layout(
        xaxis_title="Savings / Savings Target ratio",
        yaxis_title="sol_gdp_per_capita_scale",
        legend_title="Strata",
        height=380,
    )
    st.plotly_chart(fig3, use_container_width=True)

    # Summary table
    st.subheader("Current scenario breakdown")
    summary = []
    for s in active_strata:
        sav_ratio = params.strata[s].savings / max(1e-9, sav_targets[s])
        summary.append({
            "Strata":            STRATA_LABELS[s],
            "GDP/cap":           round(gdp_pc[s], 3),
            "sol_pressure":      round(gdp_pc[s] * STRATA_PARAMS[s][0] - STRATA_PARAMS[s][1], 3),
            "GDP nonlinear":     round(nl[s], 3),
            "Savings ratio":     round(sav_ratio, 3),
            "Savings pressure":  round(sp_pressure[s], 3),
            "Inst bonus":        round(num_institutions * 0.05, 3),
            "Demand scale":      round(d_scale[s], 3),
        })
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)


# ===========================================================================
# TAB 3: Time Simulation
# ===========================================================================
with tab3:
    st.subheader("Month-by-month simulation")
    st.caption(
        f"Update interval: **{update_interval} year(s)**  |  "
        f"Duration: **{sim_years} years**  |  "
        f"Demand scale is **frozen** between update ticks (step function)."
    )

    with st.spinner("Running simulation…"):
        df_sim = simulate(params, demand_matrix_w)

    update_tick_years = df_sim[df_sim["update_tick"]]["year"].tolist()

    # ---- Savings over time ----
    st.markdown("#### Savings over time (estate gold)")
    fig_sav = go.Figure()
    for s in active_strata:
        df_s = df_sim[df_sim["strata"] == s]
        if df_s.empty:
            continue
        fig_sav.add_trace(go.Scatter(
            x=df_s["year"], y=df_s["savings"],
            name=STRATA_LABELS[s],
            line=dict(color=STRATA_COLORS[s], width=2),
        ))
        # Savings target line (dashed)
        fig_sav.add_trace(go.Scatter(
            x=[df_s["year"].iloc[0], df_s["year"].iloc[-1]],
            y=[sav_targets[s], sav_targets[s]],
            name=f"Target ({s[:3].title()})",
            line=dict(color=STRATA_COLORS[s], width=1, dash="dot"),
            showlegend=False,
        ))

    # Update tick markers
    for yt in update_tick_years:
        fig_sav.add_vline(x=yt, line_color="rgba(200,200,200,0.5)", line_dash="dash")

    fig_sav.update_layout(
        xaxis_title="Year", yaxis_title="Estate gold",
        legend_title="Strata", height=380,
    )
    st.plotly_chart(fig_sav, use_container_width=True)

    # ---- Savings ratio over time ----
    st.markdown("#### Savings ratio (savings / savings_target)")
    fig_ratio = go.Figure()
    for s in active_strata:
        df_s = df_sim[df_sim["strata"] == s]
        if df_s.empty:
            continue
        fig_ratio.add_trace(go.Scatter(
            x=df_s["year"], y=df_s["savings_ratio"],
            name=STRATA_LABELS[s],
            line=dict(color=STRATA_COLORS[s], width=2),
        ))

    fig_ratio.add_hline(y=1.0, line_dash="dot", line_color="gray",
                        annotation_text="target ratio=1")
    for yt in update_tick_years:
        fig_ratio.add_vline(x=yt, line_color="rgba(200,200,200,0.5)", line_dash="dash")

    fig_ratio.update_layout(
        xaxis_title="Year", yaxis_title="Savings ratio (s/target)",
        legend_title="Strata", height=350,
    )
    st.plotly_chart(fig_ratio, use_container_width=True)

    # ---- Demand scale over time (step function) ----
    st.markdown("#### Demand scale over time  `sol_gdp_per_capita_scale`")
    st.caption("Step function — only updates at the vertical tick marks (SOL situation pulse).")
    fig_ds = go.Figure()
    for s in active_strata:
        df_s = df_sim[df_sim["strata"] == s]
        if df_s.empty:
            continue
        fig_ds.add_trace(go.Scatter(
            x=df_s["year"], y=df_s["demand_scale"],
            name=STRATA_LABELS[s],
            line=dict(color=STRATA_COLORS[s], width=2, shape="hv"),  # step
        ))

    fig_ds.add_hline(y=1.0, line_dash="dot", line_color="gray")
    for yt in update_tick_years:
        fig_ds.add_vline(x=yt, line_color="rgba(200,200,200,0.5)", line_dash="dash")

    fig_ds.update_layout(
        xaxis_title="Year", yaxis_title="Demand scale",
        legend_title="Strata", height=350,
    )
    st.plotly_chart(fig_ds, use_container_width=True)

    # ---- Monthly income vs spending ----
    st.markdown("#### Monthly income vs spending (end state)")
    last_month = df_sim[df_sim["month"] == df_sim["month"].max()]
    bar_data = []
    for s in active_strata:
        row = last_month[last_month["strata"] == s]
        if row.empty:
            continue
        bar_data.append({
            "Strata":     STRATA_LABELS[s],
            "Income":     row["monthly_income"].values[0],
            "Spending":   row["monthly_spending"].values[0],
            "Net flow":   row["net_flow"].values[0],
        })
    df_bar = pd.DataFrame(bar_data)
    if not df_bar.empty:
        fig_bar = go.Figure()
        fig_bar.add_bar(x=df_bar["Strata"], y=df_bar["Income"],   name="Income",   marker_color="#2ecc71")
        fig_bar.add_bar(x=df_bar["Strata"], y=df_bar["Spending"], name="Spending", marker_color="#e74c3c")
        fig_bar.update_layout(
            barmode="group", xaxis_title="Strata", yaxis_title="Gold / month",
            legend_title="", height=320,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ---- Summary statistics ----
    st.subheader("End-state summary")
    end_state = df_sim[df_sim["month"] == df_sim["month"].max()].copy()
    summary_rows = []
    for s in active_strata:
        row = end_state[end_state["strata"] == s]
        if row.empty:
            continue
        m_income  = row["monthly_income"].values[0]
        m_spend   = row["monthly_spending"].values[0]
        spend_pct = (m_spend / m_income * 100) if m_income > 1e-9 else 0.0
        summary_rows.append({
            "Strata":              STRATA_LABELS[s],
            "Final savings":       round(row["savings"].values[0], 1),
            "Target savings":      round(sav_targets[s], 1),
            "Savings ratio":       round(row["savings_ratio"].values[0], 3),
            "Final demand scale":  round(row["demand_scale"].values[0], 3),
            "Monthly income":      round(m_income, 3),
            "Monthly spending":    round(m_spend, 3),
            "Spend % of income":   round(spend_pct, 1),
            "Net flow (gold/mo)":  round(row["net_flow"].values[0], 4),
        })
    if summary_rows:
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # Interpretation note
    with st.expander("How to read the simulation"):
        st.markdown("""
**Spending model** (direct):
```
monthly_spending[s] = base_demand_index[s] × pop_count[s] × demand_scale[s]
```
`base_demand_index[s]` = Σ(good_demand × price) per pop-unit per month at scale=1, derived from the actual mod files.

**Spend % of income** shows what fraction of strata income goes to goods — this is a balance measurement, not a parameter. Values > 100% mean the strata runs a deficit and will eventually deplete savings.

**Equilibrium**: Reached when net_flow ≈ 0 (spending = income). This happens when `savings_pressure` converges to the value that makes demand_scale produce exact income-matching spend.

**Update interval effect**: Demand scale is frozen between SOL pulse ticks. Longer intervals create more "sawtooth" oscillation in the spending curve.

**What the curves mean**:
- Savings below target (ratio < 1) → savings_pressure < 0 → demand_scale depressed → pops buy less
- Savings above target (ratio > 1) → savings_pressure > 0 → demand_scale elevated → pops buy more
- This feedback drives savings toward target over time
        """)

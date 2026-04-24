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

from simulator import (
    PRESSURE_MODES,
    STRATA_PARAMS,
    ScenarioParams,
    StrataState,
    compute_base_demand_index,
    compute_demand_scale,
    compute_monthly_income_from_gdp,
    compute_savings_targets,
    compute_engel_demand_scale,
    fn1_gdp_per_capita,
    fn2_gdp_nonlinear,
    fn3_savings_pressure,
    savings_pressure_curve_np,
    simulate,
    _build_engel_P_strata,
    _build_engel_alpha,
)
from parser import (
    EU5_POP_TYPES, STRATA, STRATA_TO_POP_TYPES, load_demand_matrix, load_goods_prices,
    export_budget_shares_jomini,
    GROUP_PRICES_FILE, BUDGET_SHARES_FILE,
    _GROUPS as ENGEL_GROUPS, _STRATA_KEYS as ENGEL_STRATA_KEYS,
)

from curve_designer import (
    SUBSTITUTE_GROUPS,
    GROUP_GOODS,
    GROUP_COLORS,
    ALPHA_TABLE,
    CurveDesignerState,
    compute_demand_curve,
    compute_demand_curve_per_strata,
    compute_equilibrium_spend,
    validate_budget_constraint,
    suggest_budget_correction,
    compute_engel_curve_points,
    compute_engel_curve_points_per_strata,
    compute_spend_curve_points,
    compute_total_spend_curve,
    luxury_sorted_groups,
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
    each = comm_total / 2.0
    return ScenarioParams(
        monthly_income          = d["monthly_income"],
        num_institutions        = d["num_institutions"],
        tax_base                = d["tax_base"],
        effective_control       = d["effective_control"],
        peasant_enfranchisement = d["peasant_enfranchisement"],
        pop_laborers            = d.get("pop_laborers", each),
        pop_peasants            = d.get("pop_peasants", each),
        pop_soldiers            = d.get("pop_soldiers", 0.0),
        update_interval_years   = d["update_interval_years"],
        sim_years               = d["sim_years"],
        ema_alpha               = d.get("ema_alpha", 1.0),
        pressure_mode           = d.get("pressure_mode",           "linear"),
        pressure_linear_slope   = d.get("pressure_linear_slope",   0.50),
        pressure_tanh_k         = d.get("pressure_tanh_k",         1.0),
        pressure_quadratic_norm = d.get("pressure_quadratic_norm", 2.0),
        pressure_deadband_delta = d.get("pressure_deadband_delta", 0.15),
        pressure_deadband_slope = d.get("pressure_deadband_slope", 0.50),
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
    user_presets = load_user_presets()
    user_names   = list(user_presets.keys())

    all_options  = ["(custom)"] + [f"★ {n}" for n in user_names]
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
        p = dict_to_params(user_presets[actual_name])
        st.session_state["_preset"] = p
        # Push preset values directly into widget session state so Streamlit
        # honours them even when the widgets have already been interacted with.
        comm = p.strata.get("commoners")
        st.session_state.update({
            "w_monthly_income":            float(p.monthly_income),
            "w_num_institutions":          int(p.num_institutions),
            "w_tax_base":                  float(p.tax_base),
            "w_effective_control":         int(round(p.effective_control * 100)),
            "w_enfranchisement":           float(p.peasant_enfranchisement),
            "w_pop_nobles":                float(p.strata["nobles"].pop_count),
            "w_pop_clergy":                float(p.strata["clergy"].pop_count),
            "w_pop_burghers":              float(p.strata["burghers"].pop_count),
            "w_pop_laborers":              float(p.pop_laborers),
            "w_pop_peasants":              float(p.pop_peasants),
            "w_pop_soldiers":              float(p.pop_soldiers),
            "w_pop_tribesmen":             float(p.strata["tribesmen"].pop_count),
            "w_tr_nobles":                 int(round(p.strata["nobles"].tax_rate    * 100)),
            "w_tr_clergy":                 int(round(p.strata["clergy"].tax_rate    * 100)),
            "w_tr_burghers":               int(round(p.strata["burghers"].tax_rate  * 100)),
            "w_tr_commoners":              int(round((comm.tax_rate if comm else 0.05) * 100)),
            "w_tr_tribesmen":              int(round(p.strata["tribesmen"].tax_rate * 100)),
            "w_sv_nobles":                 float(p.strata["nobles"].savings),
            "w_sv_clergy":                 float(p.strata["clergy"].savings),
            "w_sv_burghers":               float(p.strata["burghers"].savings),
            "w_sv_commoners":              float(comm.savings if comm else 0.0),
            "w_sv_tribesmen":              float(p.strata["tribesmen"].savings),
            "w_update_interval":           p.update_interval_years,
            "w_sim_years":                 min([10,25,50,100], key=lambda x: abs(x - p.sim_years)),
            "w_ema_alpha":                 float(p.ema_alpha),
            "w_pressure_mode":             p.pressure_mode,
            "w_pressure_linear_slope":     float(p.pressure_linear_slope),
            "w_pressure_tanh_k":           float(p.pressure_tanh_k),
            "w_pressure_quadratic_norm":   float(p.pressure_quadratic_norm),
            "w_pressure_deadband_delta":   float(p.pressure_deadband_delta),
            "w_pressure_deadband_slope":   float(p.pressure_deadband_slope),
        })
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
                                       step=5.0, key="w_monthly_income",
                                       help="owner.monthly_income_trade_and_tax — drives savings targets")
    num_institutions = st.slider("Embraced institutions", 0, 10,
                                 int(_pv("num_institutions", 2)),
                                 key="w_num_institutions",
                                 help="+5% demand per institution")

    st.subheader("Location")
    tax_base          = st.number_input("Tax base (gold/month)",
                                        min_value=0.0,
                                        value=float(_pv("tax_base", 8)),
                                        step=1.0, key="w_tax_base",
                                        help="location_tax_base")
    effective_control = st.slider("Effective control (%)", 1, 100,
                                  int(_pv("effective_control", 0.75) * 100),
                                  key="w_effective_control",
                                  help="local_effective_control") / 100.0
    enfranchisement   = st.slider("Peasant enfranchisement", 0.1, 1.0,
                                  float(_pv("peasant_enfranchisement", 0.5)),
                                  step=0.05, key="w_enfranchisement",
                                  help="1.0 = full freedom; 0.1 = maximum serfdom (commoner wealth → nobles)")

    st.subheader("Pop Counts (per strata)")
    pop_nobles    = st.number_input("Nobles",    min_value=0.0, value=float(_sv("nobles",    "pop_count", 0.2)),  step=0.05, key="w_pop_nobles")
    pop_clergy    = st.number_input("Clergy",    min_value=0.0, value=float(_sv("clergy",    "pop_count", 0.15)), step=0.05, key="w_pop_clergy")
    pop_burghers  = st.number_input("Burghers",  min_value=0.0, value=float(_sv("burghers",  "pop_count", 0.15)), step=0.05, key="w_pop_burghers")
    _comm_total = float(_sv("commoners", "pop_count", 2.0))
    _comm_each  = round(_comm_total / 2, 4)
    pop_laborers  = st.number_input("  Laborers",  min_value=0.0, value=float(_pv("pop_laborers",  _comm_each)), step=0.05, key="w_pop_laborers")
    pop_peasants  = st.number_input("  Peasants",  min_value=0.0, value=float(_pv("pop_peasants",  _comm_each)), step=0.05, key="w_pop_peasants")
    pop_soldiers  = st.number_input("  Soldiers",  min_value=0.0, value=float(_pv("pop_soldiers",  0.0)),        step=0.05, key="w_pop_soldiers")
    pop_commoners = pop_laborers + pop_peasants + pop_soldiers
    st.caption(f"Commoners total: {pop_commoners:.3f}")
    pop_tribesmen = st.number_input("Tribesmen", min_value=0.0, value=float(_sv("tribesmen", "pop_count", 0.0)),  step=0.05, key="w_pop_tribesmen")

    st.subheader("Tax Rates (% of income to crown)")
    tr_nobles    = st.slider("Nobles tax",    0, 100, int(_sv("nobles",    "tax_rate", 0.15) * 100), key="w_tr_nobles")    / 100
    tr_clergy    = st.slider("Clergy tax",    0, 100, int(_sv("clergy",    "tax_rate", 0.10) * 100), key="w_tr_clergy")    / 100
    tr_burghers  = st.slider("Burghers tax",  0, 100, int(_sv("burghers",  "tax_rate", 0.10) * 100), key="w_tr_burghers")  / 100
    tr_commoners = st.slider("Commoners tax", 0, 100, int(_sv("commoners", "tax_rate", 0.05) * 100), key="w_tr_commoners") / 100
    tr_tribesmen = st.slider("Tribesmen tax", 0, 100, int(_sv("tribesmen", "tax_rate", 0.00) * 100), key="w_tr_tribesmen") / 100

    st.subheader("Initial Savings (estate gold)")
    sv_nobles    = st.number_input("Nobles savings",    min_value=0.0, value=float(_sv("nobles",    "savings", 0)), step=50.0, key="w_sv_nobles")
    sv_clergy    = st.number_input("Clergy savings",    min_value=0.0, value=float(_sv("clergy",    "savings", 0)), step=50.0, key="w_sv_clergy")
    sv_burghers  = st.number_input("Burghers savings",  min_value=0.0, value=float(_sv("burghers",  "savings", 0)), step=50.0, key="w_sv_burghers")
    sv_commoners = st.number_input("Commoners savings", min_value=0.0, value=float(_sv("commoners", "savings", 0)), step=50.0, key="w_sv_commoners")
    sv_tribesmen = st.number_input("Tribesmen savings", min_value=0.0, value=float(_sv("tribesmen", "savings", 0)), step=50.0, key="w_sv_tribesmen")

    st.subheader("Simulation Settings")
    update_interval  = st.radio("Demand update interval (years)", [1, 2, 3],
                                index=int(_pv("update_interval_years", 2)) - 1,
                                horizontal=True, key="w_update_interval")
    _sim_opts = [10, 25, 50, 100]
    _sim_raw  = int(_pv("sim_years", 25))
    _sim_val  = min(_sim_opts, key=lambda x: abs(x - _sim_raw))  # snap to nearest valid
    sim_years = st.select_slider("Simulation duration (years)", _sim_opts, value=_sim_val, key="w_sim_years")
    ema_alpha = st.slider(
        "EMA smoothing α",
        min_value=0.05, max_value=1.0,
        value=float(_pv("ema_alpha", 1.0)),
        step=0.05, key="w_ema_alpha",
        help="d_new = α × d_computed + (1−α) × d_old  |  1.0 = no smoothing (vanilla); lower values damp oscillation",
    )
    _pm_keys = list(PRESSURE_MODES.keys())
    pressure_mode = st.selectbox(
        "Savings pressure function",
        options=_pm_keys,
        format_func=lambda k: PRESSURE_MODES[k],
        index=_pm_keys.index(_pv("pressure_mode", "linear")),
        key="w_pressure_mode",
        help="Shape of the savings→demand feedback curve (fn3). See Tab 2 for the curves.",
    )

    # Initialize all params from preset/defaults
    pressure_linear_slope   = float(_pv("pressure_linear_slope",   0.50))
    pressure_tanh_k         = float(_pv("pressure_tanh_k",         1.0))
    pressure_quadratic_norm = float(_pv("pressure_quadratic_norm", 2.0))
    pressure_deadband_delta = float(_pv("pressure_deadband_delta", 0.15))
    pressure_deadband_slope = float(_pv("pressure_deadband_slope", 0.50))

    # Show sliders only for the active mode
    if pressure_mode == "linear":
        pressure_linear_slope   = st.slider("Slope", 0.05, 2.0, pressure_linear_slope, 0.05,
                                            key="w_pressure_linear_slope",
                                            help="Multiplier on (r−1). Vanilla = 0.5")
    elif pressure_mode == "tanh":
        pressure_tanh_k         = st.slider("k (steepness)", 0.1, 5.0, pressure_tanh_k, 0.1,
                                            key="w_pressure_tanh_k",
                                            help="tanh(k·(r−1)). Higher k = faster saturation.")
    elif pressure_mode == "quadratic":
        pressure_quadratic_norm = st.slider("Norm", 0.5, 5.0, pressure_quadratic_norm, 0.25,
                                            key="w_pressure_quadratic_norm",
                                            help="|r−1| = norm → pressure reaches pmax.")
    elif pressure_mode == "deadband":
        pressure_deadband_delta = st.slider("δ (dead-zone half-width)", 0.02, 0.50,
                                            pressure_deadband_delta, 0.02,
                                            key="w_pressure_deadband_delta",
                                            help="No response when |r−1| < δ.")
        pressure_deadband_slope = st.slider("Slope (outside dead zone)", 0.05, 2.0,
                                            pressure_deadband_slope, 0.05,
                                            key="w_pressure_deadband_slope")

    # ---- Save / overwrite user preset ----
    st.divider()
    st.markdown("**Save current scenario as preset**")
    _default_name   = actual_name if is_user else ""
    save_name_input = st.text_input("Name", value=_default_name,
                                    placeholder="Preset name…",
                                    label_visibility="collapsed")
    _name     = save_name_input.strip()
    _btn_label = "Overwrite" if _name in user_presets else "Save"

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
            "pressure_mode":           pressure_mode,
            "pressure_linear_slope":   pressure_linear_slope,
            "pressure_tanh_k":         pressure_tanh_k,
            "pressure_quadratic_norm": pressure_quadratic_norm,
            "pressure_deadband_delta": pressure_deadband_delta,
            "pressure_deadband_slope": pressure_deadband_slope,
            "pop_laborers":            pop_laborers,
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
    pressure_mode           = pressure_mode,
    pressure_linear_slope   = pressure_linear_slope,
    pressure_tanh_k         = pressure_tanh_k,
    pressure_quadratic_norm = pressure_quadratic_norm,
    pressure_deadband_delta = pressure_deadband_delta,
    pressure_deadband_slope = pressure_deadband_slope,
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

tab1, tab2, tab3, tab4 = st.tabs([
    "Tab 1 — Base Goods Demand",
    "Tab 2 — Scaling Functions",
    "Tab 3 — Time Simulation",
    "Tab 4 — Substitute Group Curves",
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

    x_ratio = np.linspace(0, 8, 400)
    x_gdp   = np.linspace(0, 15, 400)

    # ---- Chart 1: Combined demand scale vs savings ratio (primary output) ----
    st.markdown("#### `sol_gdp_per_capita_scale` vs savings/target ratio")
    st.caption(
        "`scale = 1 + institutions×0.05 + gdp_nonlinear + savings_pressure`  "
        "— gdp_nonlinear fixed at current GDP; diamond = current scenario state."
    )

    fig3 = go.Figure()
    for s in active_strata:
        _, _, pmin, pmax = STRATA_PARAMS[s]
        inst_bon = num_institutions * 0.05
        y_sp = savings_pressure_curve_np(
            x_ratio, pmin, pmax, pressure_mode,
            slope=pressure_linear_slope,
            k=pressure_tanh_k,
            norm=pressure_quadratic_norm,
            delta=pressure_deadband_delta,
        )
        y_sc = 1.0 + inst_bon + nl[s] + y_sp
        fig3.add_trace(go.Scatter(
            x=x_ratio, y=y_sc,
            name=STRATA_LABELS[s],
            line=dict(color=STRATA_COLORS[s], width=2),
        ))
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
        height=400,
    )
    st.plotly_chart(fig3, use_container_width=True)

    # ---- Chart 2: Savings pressure vs savings/target ratio ----
    st.markdown("#### Savings pressure component  `local_*_savings_pressure`")
    st.caption(
        f"Current mode: **{PRESSURE_MODES[pressure_mode]}**  |  "
        "`pmin = −0.50` for all strata; `pmax` varies."
    )

    fig2 = go.Figure()
    for s in active_strata:
        _, _, pmin, pmax = STRATA_PARAMS[s]
        y_sp = savings_pressure_curve_np(
            x_ratio, pmin, pmax, pressure_mode,
            slope=pressure_linear_slope,
            k=pressure_tanh_k,
            norm=pressure_quadratic_norm,
            delta=pressure_deadband_delta,
        )
        fig2.add_trace(go.Scatter(
            x=x_ratio, y=y_sp,
            name=STRATA_LABELS[s],
            line=dict(color=STRATA_COLORS[s], width=2),
        ))
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
        height=360,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ---- Chart 3: GDP nonlinear component vs GDP per capita ----
    st.markdown("#### GDP nonlinear component  `local_*_gdp_nonlinear_component`")
    st.caption(
        "`sol_pressure = gdp_per_cap × sensitivity − threshold`  →  "
        "`nonlinear = sol_pressure / (1 + sol_pressure × 0.45)`"
    )

    fig1 = go.Figure()
    for s in active_strata:
        sens, thresh, _, _ = STRATA_PARAMS[s]
        sp    = x_gdp * sens - thresh
        denom = np.maximum(0.05, 1.0 + sp * 0.45)
        y_nl  = sp / denom
        fig1.add_trace(go.Scatter(
            x=x_gdp, y=y_nl,
            name=STRATA_LABELS[s],
            line=dict(color=STRATA_COLORS[s], width=2),
        ))
        fig1.add_trace(go.Scatter(
            x=[gdp_pc[s]], y=[nl[s]],
            mode="markers", marker=dict(size=10, color=STRATA_COLORS[s], symbol="diamond"),
            showlegend=False, name=f"{s} (current)",
        ))

    fig1.add_hline(y=0, line_dash="dot", line_color="gray")
    fig1.update_layout(
        xaxis_title="GDP per capita (gold/month per pop-unit)",
        yaxis_title="GDP nonlinear component",
        legend_title="Strata",
        height=360,
    )
    st.plotly_chart(fig1, use_container_width=True)

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

    sim_mode = st.radio(
        "Demand mode",
        options=["unified_scale", "engel_curve"],
        format_func=lambda m: "Unified scale (current)" if m == "unified_scale" else "Engel curves (per-group)",
        horizontal=True,
        key="t3_sim_mode",
        help=(
            "**Unified scale**: all goods share one sol_gdp_per_capita_scale (old system).\n\n"
            "**Engel curves**: each substitute group gets its own linear demand scale driven "
            "by income × budget share (new system). Spending = income × Σα_g at equilibrium."
        ),
    )

    engel_P_sim = _build_engel_P_strata(demand_matrix_w) if sim_mode == "engel_curve" else None
    cd_state_for_sim = st.session_state.get("curve_designer")
    engel_alpha_sim: dict | None = None
    if sim_mode == "engel_curve" and cd_state_for_sim is not None:
        engel_alpha_sim = {
            s: cd_state_for_sim.get_strata_shares(s)
            for s in STRATA
        }
    elif sim_mode == "engel_curve":
        engel_alpha_sim = _build_engel_alpha(engel_P_sim)

    with st.spinner("Running simulation…"):
        df_sim = simulate(
            params, demand_matrix_w,
            mode=sim_mode,
            engel_alpha=engel_alpha_sim,
            engel_P=engel_P_sim,
        )

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


# ===========================================================================
# TAB 4: Substitute Group Curve Designer
# ===========================================================================
with tab4:
    st.subheader("Per-Substitute-Group Engel Curve Designer (分阶层)")
    st.caption(
        "为10个替代组设计线性需求曲线，满足 **Σ(demand × price) = income**（恒等于收入）。"
        "每组曲线: **d_g_s(y) = (α_g / P_g_s) × y**，其中 P_g_s 是按阶层计算的。"
        "预算份额 α_g 必须总和为 1.0。"
    )

    # Initialize curve designer (one-time at startup).
    # init_from_demand_matrix loads per-strata alpha from data/alpha_table.csv if present.
    if "curve_designer" not in st.session_state:
        cd = CurveDesignerState()
        cd.init_from_demand_matrix(demand_matrix_w)
        st.session_state["_shares_source"] = "from alpha_table.csv" if ALPHA_TABLE.exists() else "auto-calibrated"
        st.session_state["curve_designer"] = cd
    if "cd_locked" not in st.session_state:
        st.session_state["cd_locked"] = {g: False for g in SUBSTITUTE_GROUPS}

    cd: CurveDesignerState = st.session_state["curve_designer"]

    # ---- Top controls: strata selector + income ----
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 1])
    with ctrl_col1:
        selected_strata = st.selectbox(
            "选择阶层 (Strata)",
            options=STRATA,
            format_func=lambda s: f"{s} ({STRATA_LABELS[s]})",
            index=0,
            key="cd_strata_selector",
        )
    with ctrl_col2:
        check_income = st.number_input(
            "收入电平 (gold/月/pop-unit)",
            min_value=0.0, max_value=50.0,
            value=5.0, step=0.5, key="cd_check_income",
        )
    with ctrl_col3:
        _cur_shares = cd.get_strata_shares(selected_strata)
        total_share = sum(_cur_shares.values())
        is_valid = abs(total_share - 1.0) < 1e-6
        st.metric(
            f"Σ α ({selected_strata})",
            f"{total_share:.4f}",
            delta=f"{total_share - 1.0:+.4f}",
            delta_color="inverse" if not is_valid else "normal",
        )

    st.divider()

    # ---- Sync slider keys when strata changes ----
    _last_strata = st.session_state.get("_cd_last_strata", "")
    if _last_strata != selected_strata:
        for _g in SUBSTITUTE_GROUPS:
            st.session_state[f"cd_share_{selected_strata}_{_g}"] = float(
                cd.get_strata_shares(selected_strata).get(_g, 0.0)
            )
        st.session_state["_cd_last_strata"] = selected_strata

    # ---- on_change callback for alpha sliders ----
    def _on_alpha_change(g_name: str, strata: str) -> None:
        _cd = st.session_state["curve_designer"]
        _locked = {g: st.session_state.get(f"cd_lock_{g}", False) for g in SUBSTITUTE_GROUPS}
        _new_val = float(st.session_state[f"cd_share_{strata}_{g_name}"])
        updated = _cd.apply_delta_with_locks(strata, g_name, _new_val, _locked)
        for _g, _v in updated.items():
            st.session_state[f"cd_share_{strata}_{_g}"] = float(_v)

    # ---- Budget Share Sliders ----
    st.markdown(f"#### 预算份额配置 — {selected_strata} (α_g_s，总和必须 = 1.0)")
    st.caption(
        "🔒 锁定后该组alpha不参与重分配。调整一个alpha时，其他未锁定组均分反向变化量。"
    )

    share_cols = st.columns(2)
    luxury_order = luxury_sorted_groups()

    for idx, g_name in enumerate(luxury_order):
        with share_cols[idx % 2]:
            group = cd.groups[g_name]
            color_hex = GROUP_COLORS.get(g_name, "#888")

            # Header row: color badge + lock checkbox
            badge_col, lock_col = st.columns([0.85, 0.15])
            with badge_col:
                goods_str = ", ".join(group.goods[:3])
                if len(group.goods) > 3:
                    goods_str += f"…(+{len(group.goods)-3})"
                st.markdown(
                    f"<span style='background-color:{color_hex};color:white;padding:2px 8px;"
                    f"border-radius:4px;font-weight:bold'>{g_name.upper()}</span> "
                    f"<small>{goods_str}</small>",
                    unsafe_allow_html=True,
                )
            with lock_col:
                st.checkbox(
                    "🔒",
                    key=f"cd_lock_{g_name}",
                    help=f"锁定 {g_name} 的 alpha，使其不参与重分配",
                    label_visibility="collapsed",
                )

            # Per-strata info
            alpha_gs = cd.get_strata_shares(selected_strata).get(g_name, 0.0)
            P_g_s = group.base_price_sum_per_strata.get(selected_strata, 0.0)
            b_g_s = group.slope_for_strata(selected_strata)
            info_col1, info_col2, info_col3 = st.columns(3)
            with info_col1:
                st.caption(f"α_g_s = {alpha_gs:.4f}")
            with info_col2:
                st.caption(f"P_g_s = {P_g_s:.4f}")
            with info_col3:
                st.caption(f"b_g_s = {b_g_s:.6f}")

            # Slider with on_change redistribution
            st.slider(
                f"α_{g_name}",
                min_value=0.0, max_value=1.0,
                step=0.001,
                key=f"cd_share_{selected_strata}_{g_name}",
                on_change=_on_alpha_change,
                args=(g_name, selected_strata),
                label_visibility="collapsed",
            )

            demand_at_income = b_g_s * check_income
            spend_at_income = alpha_gs * check_income
            st.caption(
                f"→ 需求={demand_at_income:.4f} | 支出={spend_at_income:.4f} @ {check_income}"
            )

    st.divider()

    # Source badge
    shares_source = st.session_state.get("_shares_source", "default")
    st.caption(f"Alpha 数据来源: **{shares_source}**")

    # ---- Constraint validation ----
    cur_strata_shares = cd.get_strata_shares(selected_strata)
    total_share = sum(cur_strata_shares.values())
    is_valid = abs(total_share - 1.0) < 1e-6
    st.markdown(
        f"**约束状态 ({selected_strata}):** Σα_g_s = **{total_share:.6f}** "
        f"{'✓ 满足约束' if is_valid else '✗ 不满足约束（检查alpha表格）'}"
    )

    # ---- Action Buttons ----
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([1, 1, 1, 1])
    with btn_col1:
        save_table_clicked = st.button("保存到Alpha表格", type="primary", use_container_width=True,
                                       help="将当前所有阶层的alpha值写入 data/alpha_table.csv")
    with btn_col2:
        auto_clicked = st.button("自动校准", use_container_width=True,
                                 help="按 P_g_s 比例自动计算各阶层的 alpha")
    with btn_col3:
        gen_prices_clicked = st.button("生成组价格", use_container_width=True,
                                       help="重新计算并写入 z_SOL_group_prices.txt")
    with btn_col4:
        export_shares_clicked = st.button("导出预算份额", use_container_width=True,
                                          help="从 alpha_table.csv 生成 z_SOL_group_budget_shares.txt")

    if save_table_clicked:
        try:
            cd.save_to_alpha_table(ALPHA_TABLE)
            st.session_state["_shares_source"] = "from alpha_table.csv"
            st.success(f"Alpha 表格已保存 → {ALPHA_TABLE.relative_to(ALPHA_TABLE.parent.parent)}")
        except Exception as e:
            st.error(f"保存失败: {e}")

    if auto_clicked:
        auto_per_strata = cd.auto_calibrate_budget_shares()
        cd.set_budget_shares_per_strata(auto_per_strata)
        # Force the pre-slider sync block to re-read from cd on next pass
        st.session_state["_cd_last_strata"] = ""
        st.rerun()

    if gen_prices_clicked:
        try:
            _scripts_dir = ALPHA_TABLE.parent.parent / "scripts"
            import sys as _sys
            _sys.path.insert(0, str(_scripts_dir))
            from gen_group_prices import compute_group_prices, write_group_prices  # type: ignore
            _prices = compute_group_prices()
            write_group_prices(_prices)
            st.success(f"组价格已写入 z_SOL_group_prices.txt")
        except Exception as e:
            st.error(f"生成失败: {e}")

    if export_shares_clicked:
        try:
            _scripts_dir = ALPHA_TABLE.parent.parent / "scripts"
            import sys as _sys
            _sys.path.insert(0, str(_scripts_dir))
            from gen_budget_shares import load_alpha_table, validate_alpha_sums, write_budget_shares  # type: ignore
            _alpha = load_alpha_table(ALPHA_TABLE)
            _errs = validate_alpha_sums(_alpha)
            if _errs:
                for _e in _errs:
                    st.warning(_e)
            else:
                write_budget_shares(_alpha)
                st.success("预算份额已写入 z_SOL_group_budget_shares.txt")
        except Exception as e:
            st.error(f"导出失败: {e}")

    st.divider()

    # ---- Engel Curves per Strata ----
    st.markdown(f"#### Engel 曲线: {selected_strata} ({STRATA_LABELS[selected_strata]})")
    st.caption(
        "d_g_s(y) = (α_g / P_g_s) × y，按选定阶层计算。"
        "菱形标记 = 当前收入电平。"
    )

    income_range = np.linspace(0, 20, 200)
    engel_lines_s = compute_engel_curve_points_per_strata(
        selected_strata,
        income_range,
        cd.get_strata_shares(selected_strata),
        {g: cd.groups[g].base_price_sum_per_strata for g in cd.groups},
    )

    fig_engel = go.Figure()
    for g_name in luxury_sorted_groups():
        if g_name in engel_lines_s:
            color = GROUP_COLORS.get(g_name, "#888")
            fig_engel.add_trace(go.Scatter(
                x=income_range, y=engel_lines_s[g_name],
                name=f"{g_name.title()}",
                line=dict(color=color, width=2),
            ))
            d_at_income = cd.groups[g_name].demand_at_strata(selected_strata, check_income)
            fig_engel.add_trace(go.Scatter(
                x=[check_income], y=[d_at_income],
                mode="markers",
                marker=dict(size=9, color=color, symbol="diamond"),
                showlegend=False,
            ))

    fig_engel.update_layout(
        xaxis_title="Income (gold/月/pop-unit)",
        yaxis_title=f"Group Demand ({selected_strata})",
        legend_title="Group",
        height=400,
    )
    st.plotly_chart(fig_engel, use_container_width=True)

    # ---- Spend Curves per Strata ----
    st.markdown(f"#### 支出曲线: {selected_strata}")
    st.caption(
        "spend_g_s(y) = α_g × y。注意 Σ spending = income（约束自动满足）。"
    )

    _strata_shares_for_charts = cd.get_strata_shares(selected_strata)
    spend_lines = compute_spend_curve_points(income_range, _strata_shares_for_charts)
    total_spend_range = compute_total_spend_curve(income_range, _strata_shares_for_charts)

    fig_spend = go.Figure()
    fig_spend.add_trace(go.Scatter(
        x=income_range, y=income_range,
        name="Income (参考)",
        line=dict(color="gray", width=1, dash="dot"),
    ))
    fig_spend.add_trace(go.Scatter(
        x=income_range, y=total_spend_range,
        name="Σ Spending",
        line=dict(color="black", width=2.5, dash="dash"),
    ))
    for g_name in luxury_sorted_groups():
        if g_name in spend_lines:
            color = GROUP_COLORS.get(g_name, "#888")
            fig_spend.add_trace(go.Scatter(
                x=income_range, y=spend_lines[g_name],
                name=f"{g_name.title()}",
                line=dict(color=color, width=1.5),
                opacity=0.8,
            ))

    fig_spend.update_layout(
        xaxis_title="Income (gold/月/pop-unit)",
        yaxis_title="Spending (gold/月/pop-unit)",
        legend_title="Group",
        height=400,
    )
    st.plotly_chart(fig_spend, use_container_width=True)

    st.divider()

    # ---- Equilibrium Calculator per Strata ----
    st.markdown(f"#### 均衡计算器 ({selected_strata})")
    st.caption(
        "输入收入电平，计算各替代组的均衡需求和支出。约束 Σ(demand × price) = income 自动满足。"
    )

    eq_col1, eq_col2 = st.columns([1, 2])
    with eq_col1:
        eq_income = st.number_input(
            "均衡计算收入电平",
            min_value=0.0, max_value=100.0,
            value=5.0, step=0.5, key="cd_eq_income",
        )
    with eq_col2:
        _eq_shares = cd.get_strata_shares(selected_strata)
        eq_is_valid, eq_total, eq_gap = validate_budget_constraint(_eq_shares)
        st.markdown(
            f"**预算份额 ({selected_strata}):** Σα_g_s = {eq_total:.4f} "
            f"{'✓' if eq_is_valid else '✗'}"
        )

    eq_demands_s = compute_demand_curve_per_strata(
        selected_strata,
        eq_income,
        _eq_shares,
        {g: cd.groups[g].base_price_sum_per_strata for g in cd.groups},
    )
    eq_spends = compute_equilibrium_spend(eq_income, _eq_shares)

    # Detailed table per strata
    eq_rows = []
    _eq_strata_shares = cd.get_strata_shares(selected_strata)
    for g in luxury_sorted_groups():
        group = cd.groups[g]
        alpha_gs = _eq_strata_shares.get(g, 0.0)
        P_g_s = group.base_price_sum_per_strata.get(selected_strata, 0.0)
        P_g_avg = group.base_price_sum
        b_g_s = group.slope_for_strata(selected_strata)
        d_s = eq_demands_s.get(g, 0.0)
        sp = eq_spends.get(g, 0.0)

        eq_rows.append({
            "Group": g.title(),
            f"α_g_s ({selected_strata[:3]})": round(alpha_gs, 4),
            f"P_g_s ({selected_strata[:3]})": round(P_g_s, 4),
            "P_g(avg)": round(P_g_avg, 4),
            f"b_g_s": round(b_g_s, 6),
            f"需求@{eq_income}": round(d_s, 4),
            f"支出@{eq_income}": round(sp, 4),
            "占比": f"{alpha_gs*100:.1f}%",
        })

    st.dataframe(
        pd.DataFrame(eq_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            f"α_g_s ({selected_strata[:3]})": st.column_config.NumberColumn(format="%.4f"),
            f"P_g_s ({selected_strata[:3]})": st.column_config.NumberColumn(format="%.4f"),
            "P_g(avg)": st.column_config.NumberColumn(format="%.4f"),
            "b_g_s": st.column_config.NumberColumn(format="%.6f"),
            f"需求@{eq_income}": st.column_config.NumberColumn(format="%.4f"),
            f"支出@{eq_income}": st.column_config.NumberColumn(format="%.4f"),
        },
    )

    total_eq_spend = sum(eq_spends.values())
    st.markdown(
        f"**均衡验证:** Σ支出 = **{total_eq_spend:.4f}**, 收入 = **{eq_income:.4f}**, "
        f"gap = **{total_eq_spend - eq_income:.6f}**"
    )

    st.divider()

    # ---- All Strata Comparison ----
    st.markdown("#### 全阶层 P_g 对比")
    st.caption("各替代组在不同阶层的基础价格总和 P_g_s")

    # Build comparison table
    pg_rows = []
    for g in luxury_sorted_groups():
        group = cd.groups[g]
        row = {"Group": g.title()}
        for s in STRATA:
            row[s] = round(group.base_price_sum_per_strata.get(s, 0.0), 4)
        row["avg"] = round(group.base_price_sum, 4)
        pg_rows.append(row)

    pg_df = pd.DataFrame(pg_rows)
    st.dataframe(
        pg_df,
        use_container_width=True,
        hide_index=True,
    )

    # ---- How it integrates ----
    with st.expander("如何与模拟器集成"):
        st.markdown("""
### 与 simulator.py 集成

当前模拟器使用统一的 `sol_gdp_per_capita_scale` 缩放所有商品需求。

使用分组 Engel 曲线后：

```
# 旧: 统一需求缩放
monthly_spending[s] = base_idx[s] × pop_count[s] × demand_scale[s]

# 新: 分组 Engel 曲线
monthly_spending[s] = Σ_g [ spend_g_s(income_s) × pop_count[s] ]
                     = Σ_g [ α_g × income_s × pop_count[s] ]
```

关键性质：
- Σ spending = Σ (α_g × income_s × pop_count) = income_s × pop_count ✓
- 奢侈品（高 α_g）在收入增加时获得更多支出
- 必需品（低 α_g）保持比例稳定
        """)

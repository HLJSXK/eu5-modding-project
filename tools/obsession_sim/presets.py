"""Named parameter sets. 'baseline' is the current plan; the rest are kept
only as comparisons (each documents why it was not chosen)."""

from __future__ import annotations

from .core import Params

PRESETS = {
    "baseline": dict(
        doc="现行基准：方案A队列 + δ=0.1 + 国家级时钟（首次成员后保持 T=240 月，再整组懒衰退，因子 0.98/月）",
        decay="country_clock", hold_T=240, decay_factor=0.98, rho=0.99, p=0.02, delta=0.1),
    "baseline_T120": dict(
        doc="对比：保持期 T=120 月",
        decay="country_clock", hold_T=120, decay_factor=0.98, rho=0.99, p=0.02, delta=0.1),
    "baseline_habit30": dict(
        doc="基准 + 习俗保留率 κ=0.3：退潮后各地保留峰值的 30%（习惯型商品的建议形态，待校准）",
        decay="country_clock", hold_T=240, decay_factor=0.98, habit_floor=0.3, rho=0.99, p=0.02, delta=0.1),
    "growth_only": dict(
        doc="对比：只有增长，没有退潮",
        decay="none", rho=0.99, p=0.02, delta=0.1),
    "growth_delta0": dict(
        doc="对比：方案A 但 δ=0（前沿拖尾不受抑制）",
        decay="none", rho=0.99, p=0.02, delta=0.0),
    "global_node_800": dict(
        doc="对比：第 800 月全图同时切换到逐节点退潮，δ=0.1 下冻结在成员档",
        decay="global_node", global_decay_start=800, global_rho=0.95, global_p=0.005, rho=0.99, p=0.02, delta=0.1),
    "global_lazy_800": dict(
        doc="对比：第 800 月全图同时进入一个共享 S 的懒衰退（全球均匀）",
        decay="global_lazy", global_decay_start=800, global_rho=0.95, global_p=0.005, rho=0.99, p=0.02, delta=0.1),
}


def make_params(name, center=None, **overrides) -> Params:
    spec = dict(PRESETS[name])
    spec.pop("doc", None)
    spec.update(overrides)
    if "seeds" not in spec and center is not None:
        spec["seeds"] = [(center, 0, 25.0)]
    return Params(**spec)

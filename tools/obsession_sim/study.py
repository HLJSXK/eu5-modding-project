"""Budget frontier, transport ablations and reproducible first-batch sensitivity.

Run: python -m tools.obsession_sim.study --graph <real-map.json> --out <report.json>
MC is a perturbation study (uniform +/-10 years and +/-20% initial intensity),
not a claim that a historical startup hazard has been estimated.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .batch import run_batch
from .core import Params, Simulation
from .export import export_html, export_playback
from .graph import load_json
from .historical import START, SHARED, TARGET_PATH, evaluate, prepare, scenario
from .scenario import apply_scenario


def export_study_run(sim, spec, directory, good, milestone_results):
    """Keep playable results and editable scenario inputs visibly distinct."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    kwargs = dict(title=f"{good}: first-batch transport study",
                  note="Historical network approximation; named-city timing proxies, not full L2 certification.",
                  start_year=START, milestone_results=milestone_results)
    export_html(sim, directory / f"{good}.html", **kwargs)
    export_playback(sim, directory / f"{good}.playback.json", **kwargs)
    scenario_json = json.dumps(spec, ensure_ascii=False, indent=1)
    (directory / f"{good}.scenario.json").write_text(scenario_json, encoding="utf-8")
    # Preserve the old configuration path for existing --scenario commands.
    (directory / f"{good}.json").write_text(scenario_json, encoding="utf-8")


def compact(report):
    return {"budget": report["shared_budget"]["budget"],
            "peak_U": report["shared_budget"]["peak_monthly_U"],
            "total_U": report["shared_budget"]["total_U"],
            "overruns": len(report["shared_budget"]["overruns"]),
            "all_point_targets": report["point_target_acceptance"],
            "constraints_pass": report["checked_constraints_pass"],
            "goods": {g: {"within": d["within_tolerance"], "total": len(d["milestones"]),
                           "loss": d["loss"], "p_order": d["p_order"], "p_unseeded": d["p_unseeded"],
                           "p_conn": d["p_conn"], "peak_round_delay_months": d["summary"]["peak_round_delay_months"]}
                      for g, d in report["goods"].items()}}


def run_case(graph, budget, **kwargs):
    sims, specs = prepare(graph, **kwargs)
    return evaluate(sims, specs, run_batch(sims.values(), budget))


def perturbed(graph, rng):
    sims, specs, draws = {}, {}, {}
    for good in ("coffee", "tea", "tobacco"):
        g = deepcopy(graph)
        sp = scenario(good, g)
        jitter = rng.randint(-120, 120)
        factor = rng.uniform(.8, 1.2)
        draws[good] = {"start_jitter_months": jitter, "intensity_factor": factor}
        for row in sp.get("seeds", []):
            row["value"] *= factor
        if good == "coffee":
            sp["waves"][0]["start_year"] = 1440
            for row in sp["seeds"]:
                row["year"] += jitter / 12
            for row in sp["sources"]:
                row["start_year"] += jitter / 12
                row["end_year"] += jitter / 12
        elif good == "tobacco":
            sp["waves"][0]["start_year"] = 1520
            sp["transport"]["routes"][0]["start_year"] += jitter / 12
            sp["constraints"][0]["before_year"] += jitter / 12
            for row in sp["initial"]:
                row["value"] *= factor
        else:
            sp["waves"][2]["start_year"] = 1600
            for row in sp["initial"]:
                row["value"] *= factor
            for row in sp["transport"]["routes"]:
                if row["start_year"] in (1410, 1610):
                    row["start_year"] += jitter / 12
            for row in sp["coefficient_events"]:
                if row["start_year"] == 1610:
                    row["start_year"] += jitter / 12
            sp["constraints"][0]["before_year"] += jitter / 12
        config = dict(SHARED)
        config.update(apply_scenario(g, sp, config["p"], config["rho"], START))
        sims[good], specs[good] = Simulation(g, Params(**config)), sp
    return sims, specs, draws


def percentiles(values):
    values = sorted(values)
    return {str(p): values[round((len(values) - 1) * p)] for p in (.1, .5, .9)} if values else {}


def write_markdown(report, path):
    selected = report["selected"]
    goods = selected["goods"]
    passed = sum(r["within_tolerance"] for r in goods.values())
    total = sum(len(r["milestones"]) for r in goods.values())
    free = report["budget_frontier"][-1]
    peak = selected["shared_budget"]["peak_monthly_U"]
    reduction = 100 * (1 - peak / free["peak_U"])
    adjacency_peak = report["ablations"]["adjacency only"]["peak_U"]
    lines = ["# 首批痴迷传播：贸易、走廊与 U 峰值验证", "",
             "日期：2026-10-19。实现范围：离线模拟器；没有部署 EU5 玩法脚本。", "",
             f"**城市代理目标 {passed}/{total} 通过；已实现的六项负面约束零违反。** 三商品合计峰值 **{peak:,} U/月**，"
             f"比同一模型宽预算运行的 {free['peak_U']:,} U 下降 **{reduction:.1f}%**。", "",
             f"同额度纯邻接对照峰值 {adjacency_peak:,} U；加入贸易与走廊后只增加 **{peak-adjacency_peak:,} U（{100*(peak/adjacency_peak-1):.2f}%）**。", "",
             "这是允许的静态贸易近似：1337 年所有权，有限历史港口/商队骨架，年份和路线权重中的设计假设明确标 C。"
             "城市到达不等于地区人口加权采纳；未核对每行史料、未跑真实跨洋占有/出口条件、联合咖啡/酒与烟草禁令试验，"
             "也没有独立历史快照。因此**不宣称达到 15 文档的完整 L1/L2/L3**。开发中已查看全部城市目标，所谓 holdout 只作诊断分组，不能当盲测。", "",
             "## 预算与性能", "", "| 共享预算 U/月 | 实测峰值 | 总 U | 城市通过数 | 超额月数 |", "|---:|---:|---:|---:|---:|"]
    for row in report["budget_frontier"]:
        count = sum(g["within"] for g in row["goods"].values())
        lines.append(f"| {row['budget']:,} | {row['peak_U']:,} | {row['total_U']:,} | {count}/{total} | {row['overruns']} |")
    lines += ["", "选择扫描中最小且全目标通过、负面约束通过、零超额的预算；不是数学上的全局最优证明。"
              "先计入所有商品的时钟、输入、清理与重标定，再轮转分配节点服务额度。预算过低的未到达、时效损失与维护超额全部保留。", "",
              "U 包括原 PRICE_CLOCK、每次服务额外 10+d 的系数求值审计、路线变更/源输入/系数写入/唤醒/清队列/时钟续波。"
              "图生成、最短路预编译、回放与统计是离线工作；U 仍是抽象原语，不是引擎耗时，SOL 经济聚合及实际脚本展开待实机补验。", "",
              "## 组件对照", "", "| 情景 | 通过数 | 峰值 U/月 |", "|---|---:|---:|"]
    for name, row in report["ablations"].items():
        count = sum(g["within"] for g in row["goods"].values())
        lines.append(f"| {name} | {count}/{total} | {row['peak_U']:,} |")
    lines += ["", "所有对照使用同一初值、原目标/容差、共享参数、窗口和预算；没有把目标城市直接设为成员或风尚。", "",
              "## 逐项时间目标", "", "| 商品 | 城市/指标 | 目标年 | 模拟年 | 容差 年 |", "|---|---|---:|---:|---:|"]
    for good, result in goods.items():
        for row in result["milestones"]:
            lines.append(f"| {good} | {row['name']} | {row['target_year']} | {row['simulated_year']} | {row['tolerance_months']/12:g} |")
    lines += ["", "## 稳定性与审计", "",
              f"目标文件 SHA256：`{selected['target_sha256']}`。没有修改目标年份或容差以换取通过。", "",
              f"蒙特卡洛输入敏感性共 {len(report['monte_carlo']['runs'])} 组，固定随机种子 {report['monte_carlo']['rng_seed']}；"
              "启动±10年、发源/已有习俗初值±20%，共用相同物理参数和预算；不是估计后的历史风险率模型。", "",
              f"各商品在原容差内通过比例的 P10/P50/P90：`{json.dumps(report['monte_carlo']['within_fraction_quantiles'], ensure_ascii=False)}`。", "",
              f"MC 负面约束失败 {report['monte_carlo']['any_constraint_failures']} 组，预算超额 {report['monte_carlo']['any_budget_overruns']} 组。", "",
              "| 商品 | 顺序一致率 | 无近邻入口比例 | 传播连通率 | 最大跨月轮长 |", "|---|---:|---:|---:|---:|"]
    for good, result in goods.items():
        lines.append(f"| {good} | {result['p_order']:.3f} | {result['p_unseeded']:.3f} | {result['p_conn']:.3f} | {result['summary']['peak_round_delay_months']} 月 |")
    lines += ["", "无近邻入口比例把开局已有习俗和有条件的俄国茶赠礼也算作入口；不删去不利分母。"
              "到达、峰值、父节点、约束记录都仅为离线诊断，不增加游戏中的地点状态。新增地点游戏状态仍只有 x 与排队期间的 q。", "",
              "表中的时间损失按 Σ(误差/容差)² 计算，未到达每项记 100；约束作为独立硬失败检查。"
              "这是城市代理的诊断损失，不冒充 09 的完整区域损失、参数正则或正式历史分级。", "",
              "## 复现与地图回放", "", "```powershell", "$env:PYTHONUTF8='1'",
              "& C:\\Users\\Hades\\anaconda3\\envs\\eu5\\python.exe -m tools.obsession_sim.study `",
              "  --graph tmp/obsession_real/eu5_1337.json `",
              "  --out docs/design/obsession/experiments/first_batch_transport_results.json `",
              "  --html-dir tmp/obsession_real/first_batch --mc 30", "```", "",
              "[完整输入、逐月 U、对照和 MC 结果](experiments/first_batch_transport_results.json)。"
              "地图回放及可直接载入工作台的 scenario JSON 生成于 `tmp/obsession_real/first_batch/`。", "",
              "地图回放：[咖啡](../../../tmp/obsession_real/first_batch/coffee.html)、"
              "[茶](../../../tmp/obsession_real/first_batch/tea.html)、[烟草](../../../tmp/obsession_real/first_batch/tobacco.html)。", "",
              "在模拟器的「载入回放文件」中，选择 `coffee.playback.json`、`tea.playback.json`、`tobacco.playback.json`，"
              "也可选择上述内嵌回放的 HTML。`*.scenario.json` 和保留兼容的商品名 `.json` 是情景配置，使用「导入配置」后重算；"
              "研究结果 `first_batch_transport_results.json` 是统计报告，不是回放。", "",
              "历史依据范围：[NCA 咖啡历史](https://www.aboutcoffee.org/origins/history-of-coffee/)、"
              "[UKTIA 茶历史](https://www.tea.co.uk/history-of-tea)、"
              "[IARC 烟草传播综述](https://www.ncbi.nlm.nih.gov/books/NBK316400/)，"
             "具体目标年份沿用 09 草案，仍为 B 级待逐行补证；也门源区达到20的±15年是研究开始前约定的额外 C 级诊断"
             "（09 对发源行没有给数值容差），不参与正式历史判分。路线/商业时段与权重为 C 级近似，不能把它们解释为观测贸易量。", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mc", type=int, default=30)
    ap.add_argument("--rng-seed", type=int, default=20261019)
    ap.add_argument("--budgets", default="40000,50000,60000,70000,80000,120000,480000")
    ap.add_argument("--html-dir", type=Path)
    a = ap.parse_args(argv)
    if a.mc < 1:
        ap.error("--mc must be positive")
    graph = load_json(a.graph)
    budgets = sorted(set(int(v) for v in a.budgets.split(",")))
    reports = []
    for budget in budgets:
        result = run_case(graph, budget)
        reports.append(result)
        print("budget", budget, json.dumps(compact(result)), flush=True)
    eligible = [r for r in reports if r["point_target_acceptance"] and r["checked_constraints_pass"] and not r["shared_budget"]["overruns"]]
    if not eligible:
        raise RuntimeError("No budget in scan meets first-batch point targets; refusing to publish success")
    selected = eligible[0]
    budget = selected["shared_budget"]["budget"]
    ablations = {"trade+corridors": compact(selected)}
    for name, options in (("adjacency only", dict(transport=False, corridors=False)),
                          ("without transport", dict(transport=False)), ("without corridors", dict(corridors=False))):
        ablations[name] = compact(run_case(graph, budget, **options))
        print(name, json.dumps(ablations[name]), flush=True)
    rng = random.Random(a.rng_seed)
    mc_runs = []
    for i in range(a.mc):
        sims, specs, draws = perturbed(graph, rng)
        result = evaluate(sims, specs, run_batch(sims.values(), budget))
        row = dict(index=i, draws=draws, **compact(result))
        mc_runs.append(row)
        print("MC", i + 1, json.dumps(row), flush=True)
    mc = {"rng_seed": a.rng_seed, "perturbation": "uniform startup +/-120 months, intensity x uniform[.8,1.2]",
          "runs": mc_runs, "within_fraction_quantiles": {good: percentiles([r["goods"][good]["within"] / r["goods"][good]["total"] for r in mc_runs])
                                                            for good in selected["goods"]},
          "any_constraint_failures": sum(not r["constraints_pass"] for r in mc_runs),
          "any_budget_overruns": sum(r["overruns"] > 0 for r in mc_runs)}
    result = {"graph": str(a.graph), "graph_sha256": hashlib.sha256(a.graph.read_bytes()).hexdigest(),
              "graph_source": {k: graph.meta.get(k) for k in ("source", "source_date", "source_year", "snapshot_label", "owner_source", "topology")},
              "scenarios": {good: scenario(good, graph) for good in selected["goods"]},
              "target_sha256": hashlib.sha256(TARGET_PATH.read_bytes()).hexdigest(),
              "selected": selected, "budget_frontier": [compact(r) for r in reports],
              "ablations": ablations, "monte_carlo": mc}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    write_markdown(result, a.out.parent.parent / "16_First_Batch_Transport_Results.md")
    if a.html_dir:
        a.html_dir.mkdir(parents=True, exist_ok=True)
        sims, specs = prepare(graph, params={"frames_every": 12, "series_every": 12})
        run_batch(sims.values(), budget)
        for good, sim in sims.items():
            if sim.frames[-1][0] != sim.t - 1:
                sim.frames.append((sim.t - 1, sim.stage_string()))
            export_study_run(sim, specs[good], a.html_dir, good, selected["goods"][good]["milestones"])
    print("selected shared budget", budget, "report", a.out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

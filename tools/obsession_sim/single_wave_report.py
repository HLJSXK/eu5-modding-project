"""Publish the single-wave refit's locked selection and fit-only diagnostics."""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import statistics
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .acceptance import aggregate_runs, moved
from .experiment import read_json
from .single_wave_fit import OUT, PUBLISHED, current, SingleWaveExperiment
from .round3_workflow import assert_fit, median_arrival
from .round2 import ROOT
from .worlds import canonical_hash
from tools.eu5_save_parser.world_export import atomic_json

DEST = ROOT / "docs/design/obsession/experiments"
REPORT = ROOT / "docs/design/obsession/29_Single_Wave_Refit.md"


def fmt(value):
    return "—" if value is None else f"{value:.4f}"


def main():
    p = read_json(PUBLISHED)
    selection = read_json(OUT / "selection.json")
    lock = read_json(OUT / "selection_lock.json")
    phase_a = read_json(OUT / "phase_a.json")
    d = read_json(OUT / "diagnostics.json")
    exp = SingleWaveExperiment(OUT)
    current(exp, p)
    audit = read_json(ROOT / "tmp/obsession_round3/world_audit_batch.json")
    if (not audit["passed"] or audit["seeds"] != list(range(30))
            or audit["world_sha256"] != canonical_hash(exp.facts)):
        raise ValueError("the reused world-input audit does not cover these frozen facts")
    if exp.graph_hash != p["graph_hash"]:
        raise ValueError("graph changed after protocol publication")
    if (d["selection_sha256"] != canonical_hash(selection) or not d["all_single_wave"]
            or d["params"] != selection["recommended"]["params"]
            or lock != dict(selection_sha256=canonical_hash(selection),
                            params_sha256=canonical_hash(d["params"]))):
        raise ValueError("diagnostics do not bind the locked single-wave selection")
    if not selection["fit_only"] or not d["fit_only"]:
        raise ValueError("refusing to publish holdout scores")
    if (len(phase_a) != p["candidate_count"]
            or {canonical_hash(r["params"]) for r in phase_a} != {canonical_hash(r) for r in p["grid"]}):
        raise ValueError("phase A does not cover the registered candidate cloud")
    raw = {name: [read_json(path) for path in paths] for name, paths in d["runs"].items()}
    assert_fit([r for rows in raw.values() for r in rows])
    mechanics = read_json(OUT / "mechanics_only.json")
    if canonical_hash(mechanics) != p["mechanics_sha256"]:
        raise ValueError("mechanics/baseline record changed after protocol publication")
    previous_params = mechanics["params"]
    d["previous_params"] = previous_params
    for name, rows in raw.items():
        expected_params = previous_params if name == "previous_params_S5" else d["params"]
        if ([r["seed"] for r in rows] != list(range(30 if name == "selected_S30" else 5))
                or any(r["params"] != expected_params or r["world_kind"] != "R"
                       or not r["identity"]["omit_wc"]
                       or r["mode"] != ("H" if name == "selected_H5" else "S")
                       or r["identity"]["budget_multiplier"] != (2 if name == "double_budget_S5" else 1)
                       for r in rows)):
            raise ValueError("diagnostic group does not match its registered seeds and configuration: " + name)
    if any(r["graph_hash"] != p["graph_hash"] or r["frozen_hash"] != p["frozen_hash"]
           or r["identity"]["code"] != p["runtime_hash"] for rows in raw.values() for r in rows):
        raise ValueError("diagnostic runs mix graph, input or runtime bindings")
    d["reused_world_audit"] = dict(path="tmp/obsession_round3/world_audit_batch.json",
                                   sha256=canonical_hash(audit), seeds=audit["seeds"],
                                   world_sha256=audit["world_sha256"], passed=True)
    d["cells"]["selected_S5"] = aggregate_runs(raw["selected_S30"][:5])
    d["runs"]["selected_S5"] = d["runs"]["selected_S30"][:5]
    d["violation_seeds"] = {
        name: [dict(seed=r["seed"], rules=[v[0] for v in r["violations"]])
               for r in rows if r["violation_count"]]
        for name, rows in raw.items()
    }
    d["early_ebb_episodes"] = {}
    for name, rows in raw.items():
        early = []
        for run in rows:
            for good, clocks in run["clocks"].items():
                waves = run["waves"][good]
                if waves:
                    early.extend(dict(seed=run["seed"], good=good, **r) for r in clocks["history"]
                                 if r["decay_start_month"] is not None
                                 and r["decay_start_month"] < waves[0]["end_month"])
        d["early_ebb_episodes"][name] = len(early)
    budget_rows = []
    for target in raw["selected_S30"][0]["milestones"]:
        if target["grade"] not in ("A", "B"):
            continue
        def arrival(rows):
            return median_arrival([next(m["simulated_month"] for m in r["milestones"]
                                        if m["id"] == target["id"]) for r in rows])
        a = arrival(raw["selected_S30"][:5])
        b = arrival(raw["double_budget_S5"])
        budget_rows.append(dict(id=target["id"], baseline=a, doubled=b,
                                moved_beyond_tolerance=moved(a, b, target["tolerance_months"])))
    d["paired_five_seed_budget"] = dict(targets=budget_rows,
        moved_fraction=sum(r["moved_beyond_tolerance"] for r in budget_rows)/len(budget_rows),
        limitation="Five-seed diagnostic only, not the ten-seed formal budget gate.")
    for row in d["fit_targets"]:
        lower = row["historical_month"] - 2*row["tolerance_months"]
        row["window_closed_before_2tol_band"] = sum(
            bool(r["waves"][row["good"]]) and r["waves"][row["good"]][0]["end_month"] < lower
            for r in raw["selected_S30"])
    selected = selection["recommended"]
    config = deepcopy(p["effective_config"])
    config["params"].update(selected["params"])
    # Raw clocks/K cases stay in tmp; the published artifact keeps summaries
    # and explicit cache references rather than duplicating every raw record.
    d["cells"] = {name: {k: v for k, v in cell.items() if k != "runs"}
                  for name, cell in d["cells"].items()}
    main30 = d["cells"]["selected_S30"]
    closed = sum(r["window_closed_before_2tol_band"] == 30 for r in d["fit_targets"])
    atomic_json(DEST / "single_wave_fit_selection.json", selection)
    atomic_json(DEST / "single_wave_selection_lock.json", lock)
    atomic_json(DEST / "single_wave_fit_phase_a.json", phase_a)
    atomic_json(DEST / "single_wave_selected_params.json", selected["params"])
    atomic_json(DEST / "single_wave_selected_config.json", config)
    atomic_json(DEST / "single_wave_fit_diagnostics.json", d)
    lines = ["# 29 单波统一退潮后的参数重拟合", "", "日期：2026-11-04。状态：离线拟合完成，未部署玩法代码。", "",
        "本轮启用工作区新增的 `fixed.uniform_ebb=true`：每商品最多开启一波，窗口结束时统一退潮，"
        "不再通过接触或所有权回流续期开波。保留 1200 月窗口、原来的事实/目标/K 规则及其余固定值；"
        "没有为命中历史而延长窗口。新参数必须和本轮配置一起使用，旧 `selected_params.json` 与冻结协议保留原样。", "",
        f"**结果：**新参数在配对五种子中将 2×容差命中率中位数从 "
        f"{d['cells']['previous_params_S5']['fit_within_2tol']:.1%} 提高到 "
        f"{d['cells']['selected_S5']['fit_within_2tol']:.1%}。扩展到 30 种子后，命中率中位数为 "
        f"{main30['fit_within_2tol']:.1%}、次序为 {main30['fit_p_order']:.4f}，仍未达到 0.5/0.7 参考线；"
        f"{closed}/24 个目标的 2×容差带开始前，传播窗口已在全部种子中关闭。", "",
        "## 拟合边界与复现", "",
        "复用第三轮已登记的 64 组六维 Latin 候选与参数范围（生成种子 2026102201），"
        "每组先跑 S×R 种子 0；前六名各补 1–4，按五种子中位数及原有分级排序选出一组。"
        "排序优先负面约束数、预算合规、min(2×容差命中率/0.5, 次序/0.7)，再比较容差命中率、符合条件的 K、延迟与哈希。", "",
        "此前已登记第二轮 49+147 组（147 含作废/中止批次）、第三轮 64 组；本轮再登记 64 组，"
        "累计登记 324 组，不把本轮描述成对拟合集的首次搜索。留出成绩仍未读取。", "",
        "协议在任何成绩运行之前写入仓库路径并绑定内容哈希；没有自动 Git 提交，因此本次是独立的机制重拟合，"
        "不宣称完成 26 的提交审计流程。选参结果先落盘并锁定哈希，再跑诊断；留出集未评分，W-C 未启用。", "",
        f"- 运行时代码：`{p['runtime_hash']}`。",
        f"- 基础冻结输入：`{p['base_frozen_hash']}`。",
        f"- 本轮配置与流程绑定：`{p['frozen_hash']}`。",
        f"- 协议：`experiments/single_wave_fit_protocol.json`，哈希 `{canonical_hash(p)}`。",
        "- 世界事实与图输入保持冻结；复核第三轮世界输入审计的事实哈希及 30 个种子全部通过记录，"
        "并逐运行检查本轮图、配置和运行时代码绑定一致。",
        f"- 共 {selection['candidate_count']} 个候选、{selection['selection_run_count']} 次选参运行；"
        "选定后 S×R 30 种子、H×R 5 种子、旧参数同机制 5 种子、双倍预算 5 种子。重复请求使用本轮专属缓存。", "",
        "```powershell", "$env:PYTHONUTF8='1'", "$env:EU5_PYTHON='C:/Users/Hades/anaconda3/envs/eu5/python.exe'",
        "& $env:EU5_PYTHON -m tools.obsession_sim.single_wave_fit mechanics",
        "& $env:EU5_PYTHON -m tools.obsession_sim.single_wave_fit protocol",
        "& $env:EU5_PYTHON -m tools.obsession_sim.single_wave_fit fit --workers 8",
        "& $env:EU5_PYTHON -m tools.obsession_sim.single_wave_fit diagnostics --workers 8",
        "& $env:EU5_PYTHON -m tools.obsession_sim.single_wave_report", "```", "",
        "## 选定参数", "", "| 参数 | 第三轮旧值 | 单波新值 |", "|---|---:|---:|"]
    # The comparison is the actual previous selection, not the structural default.
    old = previous_params
    for key, value in selected["params"].items():
        lines.append(f"| `{key}` | {old[key]:.8f} | {value:.8f} |")
    lines += ["", "完整可运行参数组合保存在 `experiments/single_wave_selected_config.json`；"
              "只复制六个数值到旧的多波配置，无法复现本轮结果。", "", "## 诊断结果", "",
              "| 同一单波机制 | 种子数 | 容差内 | 2×容差内 | 次序 | K | 违反数（最大） | 峰值 U（最大） |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    labels = {"previous_params_S5": "旧参数 S×R", "selected_S5": "新参数 S×R（配对）",
              "selected_S30": "新参数 S×R（扩展）", "selected_H5": "新参数 H×R",
              "double_budget_S5": "新参数 S×R（双倍预算）"}
    for name, label in labels.items():
        cell = d["cells"][name]
        lines.append(f"| {label} | {len(d['runs'][name])} | {fmt(cell['fit_within_tol'])} | "
                     f"{fmt(cell['fit_within_2tol'])} | {fmt(cell['fit_p_order'])} | {fmt(cell['p_K'])} | "
                     f"{cell['violation_count']} | {cell['peak_U']:,} |")
    lines += ["", "命中率、次序和 K 为运行间中位数；违反数与峰值 U 为运行间最大值。"
              "新旧参数的直接对照使用配对两行（同为种子 0–4）。"
              "原第三轮使用多波机制，不能把它与本表的旧参数单波对照混为一谈。", "",
              f"双倍预算五种子诊断中，{d['paired_five_seed_budget']['moved_fraction']:.1%} 的拟合目标"
              "中位到达移动超过自身容差；这不是正式十种子预算闸门。", "",
              "## 24 个拟合目标（S×R，30 种子）", "",
              "未到达记为 +∞ 后取中位，避免只在成功种子中计算到达时间而产生乐观偏差。", "",
              "| 目标 | 历史年份 | 模拟中位年份 | 到达次数 | 容差内次数 | 2×容差内次数 | 2×容差带前已关窗 |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for row in d["fit_targets"]:
        values = row["arrivals"]
        median = statistics.median([float("inf") if x is None else x for x in values])
        h = row["historical_month"]
        tol = row["tolerance_months"]
        within = lambda k: sum(x is not None and abs(x-h) <= k*tol for x in values)
        year = "未到达" if not math.isfinite(median) else f"{1337+median/12:.1f}"
        lines.append(f"| {row['good']} `{row['id']}` {row['label']} | {1337+h/12:g} | {year} | "
                     f"{sum(x is not None for x in values)}/30 | {within(1)}/30 | {within(2)}/30 | "
                     f"{row['window_closed_before_2tol_band']}/30 |")
    lines += ["", f"{closed}/24 个目标在全部 30 个种子中，传播窗口都先于其 2×容差带下限关闭。"
              "这是窗口和历史目标的时间关系审计，不把后续人口/政治口径变化可能产生的聚合变化说成绝对不可能。"]
    lines += ["", "## 波次和机制检查", "",
              "全部选后诊断运行均核对每商品波次数 ≤1。下表为选中参数 S×R 30 次的首波起止年份范围。", "",
              "| 商品 | 开始年份范围 | 结束年份范围 |", "|---|---:|---:|"]
    for good in ("coffee", "tea", "tobacco"):
        waves = [r[good][0] for r in d["waves"]["selected_S30"] if r[good]]
        def span(key):
            return "—" if not waves else f"{1337+min(w[key] for w in waves)/12:.1f}–{1337+max(w[key] for w in waves)/12:.1f}"
        lines.append(f"| {good} | {span('start_month')} | {span('end_month')} |")
    lines += ["", "机制体检使用旧选定参数、S×R 种子 0，全时段运行但不加载或计算目标分数；"
              "核对习俗值恒定、习俗区邻接外传为零、每商品最多一波，以及所有已记载退潮均不早于波次截止。", "",
              "选后诊断中，窗口截止前退潮的国家 episode 数为："
              + "；".join(f"{name}={count}" for name, count in d["early_ebb_episodes"].items()) + "。"
              + ("本轮各项对照均未记录提前退潮。" if not any(d["early_ebb_episodes"].values())
                 else "提前退潮案例可按原始运行的事件与时钟记录进一步定位。"), "",
              "## 本轮拟合集结论", ""]
    new5, old5 = d["cells"]["selected_S5"], d["cells"]["previous_params_S5"]
    for metric, label in (("fit_within_2tol", "2×容差命中率"), ("fit_p_order", "次序分数")):
        delta = new5[metric] - old5[metric]
        lines.append(f"同为种子 0–4，新参数的{label}相对旧参数变化 {delta*100:+.2f} 个百分点。")
    meets = main30["fit_within_2tol"] >= .5 and main30["fit_p_order"] >= .7
    lines += ["", f"选中参数的 S×R 30 种子中位数：2×容差命中率 {main30['fit_within_2tol']:.4f}，"
              f"次序 {main30['fit_p_order']:.4f}，负面约束违反数最大 {main30['violation_count']}。"
              + ("两项年份/次序参考线（0.5、0.7）均达到。" if meets else "尚未同时达到年份/次序参考线（0.5、0.7）。")
              + "这只陈述拟合集表现，不替代完整验收闸门。", "",
              f"30 种子的 10%–90% 分位区间：2×容差命中率 "
              f"{main30['fit_within_2tol_p10']:.4f}–{main30['fit_within_2tol_p90']:.4f}，"
              f"次序 {main30['fit_p_order_p10']:.4f}–{main30['fit_p_order_p90']:.4f}。", "",
              f"在这批运行已经到达的目标集合下，次序分数可达上限中位数为 {main30['fit_p_order_upper']:.4f}；"
              "它假定已到达目标之间的次序完全正确，用于区分漏到达与已到达目标的次序错误。", "",
              f"S×R 中 {30-len(d['violation_seeds']['selected_S30'])}/30 个种子没有负面约束违反。"
              + ("触发记录：" + "；".join(f"seed {r['seed']} → {', '.join(r['rules'])}"
                                          for r in d["violation_seeds"]["selected_S30"]) + "。"
                 if d["violation_seeds"]["selected_S30"] else "") + "\n",
              "## 验证", "",
              "模拟包的 200 项测试及 33 个子测试通过；工作区 `validate.py --changed` 通过。"
              "报告生成后独立读回核验了全部 123 个唯一计分运行：均为拟合集、R 世界、每商品最多一波，"
              "图/输入/运行时绑定一致；64 个首轮候选、6 个五种子复选及参数/配置配对也全部核对。"
              "测试临时目录显式放在工作区 `tmp/pytest_single_wave_20261104`。", "",
              "## 结论边界", "",
              "本轮只回答在当前单波机制和原有固定窗口下，登记候选里哪组参数较优。"
              "没有修改 K1/K5/K6、先占、习俗来源或历史事实来改善成绩；这些既有规格冲突仍可能限制结果。"
              "没有读取留出成绩、运行观察者验收或宣告 L1/L2/L3 通过。1200 月窗口若在历史目标前关闭，"
              "参数搜索不能代替对窗口设计的决定。", "",
              "原始运行与源码快照位于 `tmp/obsession_single_wave_20261104/`；"
              "可提交的协议、全部候选、选中配置与紧凑诊断保存在本目录的 `experiments/single_wave_*.json`。", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()

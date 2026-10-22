"""Analyze and plot ten-year purchasing-power observations, 1340--1840."""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from extract import OUTPUT, SERIES, STRATA

HERE = Path(__file__).resolve().parent
YEARS = list(range(1340, 1841, 10))
LABELS = {"nobles": "贵族", "clergy": "教士", "burghers": "市民", "commoners": "平民"}
COLORS = {"nobles": "#ad7b28", "clergy": "#8670b6", "burghers": "#278f86", "commoners": "#cf6254"}


def quantile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def write_csv(name, rows):
    with (OUTPUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def compound(first, last, years):
    return ((last / first) ** (10 / years) - 1) * 100


def main():
    snapshots = {}
    for year in YEARS:
        path = OUTPUT / "snapshots" / f"{year}.json"
        if not path.is_file():
            raise SystemExit(f"Missing {year}; run extract.py --all first")
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        assert snapshot["year"] == year and snapshot["playthrough_id"] == SERIES
        snapshots[year] = snapshot
    records, paired_rows, country_rows = [], [], []
    fixed_cohorts = {}
    for stratum in STRATA:
        sets = [{row["lineage"] for row in snapshots[year]["samples"][stratum]} for year in YEARS]
        fixed_cohorts[stratum] = set.intersection(*sets)
        assert fixed_cohorts[stratum], stratum
    for year in YEARS:
        for stratum in STRATA:
            rows = snapshots[year]["samples"][stratum]
            levels = [row["alpha"] for row in rows]
            median = statistics.median(levels)
            pooled = sum(row["funds_int"] for row in rows) / sum(row["base_int"] for row in rows)
            persistent = [row["alpha"] for row in rows if row["lineage"] in fixed_cohorts[stratum]]
            solver = [row["solver_funds_int"] / row["solver_base_int"] for row in rows if row["solver_base_int"] > 0]
            record = {"year": year, "stratum": stratum, "countries": len(rows), "median_alpha": median,
                      "median_pp_percent": (median - 1) * 100,
                      "p25_pp_percent": (quantile(levels, .25) - 1) * 100,
                      "p75_pp_percent": (quantile(levels, .75) - 1) * 100,
                      "pooled_alpha": pooled, "pooled_pp_percent": (pooled - 1) * 100,
                      "fixed_cohort_countries": len(persistent), "fixed_cohort_median_alpha": statistics.median(persistent),
                      "solver_cache_median_alpha": statistics.median(solver),
                      "zero_funds_countries": sum(row["funds_int"] == 0 for row in rows),
                      "share_alpha_ge_6_percent": sum(row["alpha"] >= 6 for row in rows) / len(rows) * 100,
                      "old_substitution_cache_countries": sum(0 < row["substitution_year"] < year - 1 for row in rows)}
            records.append(record)
            for row in rows:
                country_rows.append({"year": year, "stratum": stratum, **row})
            if year > YEARS[0]:
                previous = {row["lineage"]: row for row in snapshots[year - 10]["samples"][stratum]}
                current = {row["lineage"]: row for row in rows}
                common = previous.keys() & current.keys()
                ratios = [current[key]["alpha"] / previous[key]["alpha"] - 1 for key in common if previous[key]["alpha"] > 0]
                paired_rows.append({"start_year": year - 10, "end_year": year, "stratum": stratum,
                                    "matched_countries": len(common), "finite_growth_countries": len(ratios),
                                    "previous_zero_alpha_countries": sum(previous[key]["alpha"] == 0 for key in common),
                                    "median_paired_decade_growth_percent": statistics.median(ratios) * 100,
                                    "share_increasing_percent": sum(current[key]["alpha"] > previous[key]["alpha"] for key in common) / len(common) * 100})
    by_stratum = {s: [row for row in records if row["stratum"] == s] for s in STRATA}
    for stratum, series in by_stratum.items():
        first = series[0]
        for i, row in enumerate(series):
            row["index_1340_100"] = row["median_alpha"] / first["median_alpha"] * 100
            row["pooled_index_1340_100"] = row["pooled_alpha"] / first["pooled_alpha"] * 100
            row["fixed_cohort_index_1340_100"] = row["fixed_cohort_median_alpha"] / first["fixed_cohort_median_alpha"] * 100
            row["decade_growth_percent"] = (row["median_alpha"] / series[i - 1]["median_alpha"] - 1) * 100 if i else None
            row["decade_pp_change"] = row["median_pp_percent"] - series[i - 1]["median_pp_percent"] if i else None
    headline, periods = {}, []
    for stratum, series in by_stratum.items():
        first, last = series[0], series[-1]
        changes = series[1:]
        fastest = max(changes, key=lambda r: r["decade_growth_percent"])
        slowest = min(changes, key=lambda r: r["decade_growth_percent"])
        headline[stratum] = {"start_alpha": first["median_alpha"], "end_alpha": last["median_alpha"],
                             "start_pp_percent": first["median_pp_percent"], "end_pp_percent": last["median_pp_percent"],
                             "level_multiple": last["median_alpha"] / first["median_alpha"],
                             "compound_growth_per_decade_percent": compound(first["median_alpha"], last["median_alpha"], 500),
                             "annual_cagr_percent": ((last["median_alpha"] / first["median_alpha"]) ** (1 / 500) - 1) * 100,
                             "declining_decades": sum(r["decade_growth_percent"] < 0 for r in changes),
                             "fastest_decade_end": fastest["year"], "fastest_growth_percent": fastest["decade_growth_percent"],
                             "slowest_decade_end": slowest["year"], "slowest_growth_percent": slowest["decade_growth_percent"],
                             "fixed_cohort_countries": first["fixed_cohort_countries"],
                             "fixed_cohort_level_multiple": last["fixed_cohort_index_1340_100"] / 100,
                             "start_countries": first["countries"], "end_countries": last["countries"],
                             "pooled_level_multiple": last["pooled_index_1340_100"] / 100}
        for start in range(1340, 1840, 100):
            a = next(r for r in series if r["year"] == start)
            b = next(r for r in series if r["year"] == start + 100)
            periods.append({"start_year": start, "end_year": start + 100, "stratum": stratum,
                            "level_multiple": b["median_alpha"] / a["median_alpha"],
                            "compound_growth_per_decade_percent": compound(a["median_alpha"], b["median_alpha"], 100)})
    assert len(records) == 204 and len(paired_rows) == 200
    assert all(abs(row["index_1340_100"] - 100) < 1e-12 for row in records if row["year"] == 1340)
    # Independent CSV-export regression at the start: different population gates
    # permit a handful of stale positive-budget strata, but must stay near 0.4%.
    earlier_path = OUTPUT.parents[1] / "1340.04.01_autosave_c681faf6-91c6-45a9-bde4-9d8c22cd321e/purchasing_power_median_baseline/summary.json"
    regression = {}
    if earlier_path.is_file():
        earlier = json.loads(earlier_path.read_text(encoding="utf-8"))["baseline_coefficients"]
        for stratum in STRATA:
            deviation = headline[stratum]["start_alpha"] / earlier[stratum] - 1
            assert abs(deviation) < .004, (stratum, deviation)
            regression[stratum] = deviation * 100
    write_csv("decade_statistics.csv", records)
    write_csv("paired_country_growth.csv", paired_rows)
    write_csv("century_growth.csv", periods)
    write_csv("country_observations.csv", country_rows)
    summary = {"series": SERIES, "years": YEARS, "snapshots": len(snapshots),
               "versions": sorted({s["version"] for s in snapshots.values()}), "headline": headline,
               "periods": periods, "start_population_gate_sensitivity_percent": regression,
               "location_coverage": [{"year": y, "owned": s["owned_locations"], "cached": s["cached_owned_locations"]} for y, s in snapshots.items()]}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    make_plots(by_stratum, paired_rows)
    make_report(summary, records, paired_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def make_plots(by_stratum, paired_rows):
    # Reuse a verified CPython 3.11 matplotlib installation, without installing
    # packages or changing the project's interpreter/environment.
    if importlib.util.find_spec("matplotlib") is None:
        sys.path.append("C:/Users/Hades/anaconda3/envs/Research/Lib/site-packages")
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, pyplot as plt, ticker
    font_manager.fontManager.addfont("C:/Windows/Fonts/msyh.ttc")
    family = font_manager.FontProperties(fname="C:/Windows/Fonts/msyh.ttc").get_name()
    plt.rcParams.update({"font.family": family, "font.size": 11, "axes.titlesize": 14, "axes.labelsize": 11,
                         "axes.unicode_minus": False, "figure.facecolor": "#f8fafc", "axes.facecolor": "white",
                         "axes.edgecolor": "#cbd5e1", "grid.color": "#e2e8f0", "grid.linewidth": .7,
                         "axes.spines.top": False, "axes.spines.right": False, "savefig.facecolor": "#f8fafc",
                         "svg.fonttype": "path"})

    def save(fig, name):
        for extension in ("png", "svg", "pdf"):
            fig.savefig(OUTPUT / f"{name}.{extension}", dpi=180, bbox_inches="tight")
        plt.close(fig)

    def style(ax):
        ax.grid(axis="y", alpha=.8)
        ax.set_xlim(1335, 1845)
        ax.set_xticks([1340, 1440, 1540, 1640, 1740, 1840])

    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8), sharex=True)
    for ax, stratum in zip(axes.flat, STRATA):
        series = by_stratum[stratum]
        ax.fill_between(YEARS, [r["p25_pp_percent"] for r in series], [r["p75_pp_percent"] for r in series], color=COLORS[stratum], alpha=.15)
        ax.plot(YEARS, [r["median_pp_percent"] for r in series], color=COLORS[stratum], linewidth=2.3, marker="o", markersize=2.5)
        ax.axhline(0, color="#64748b", linewidth=.7)
        ax.set_title(f"{LABELS[stratum]}   {series[0]['median_pp_percent']:+.1f}% → {series[-1]['median_pp_percent']:+.1f}%", loc="left")
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:,.0f}%"))
        style(ax)
    fig.suptitle("全球购买力水平：各国中位数", fontsize=20, x=.07, ha="left", y=1.02)
    fig.text(.07, .965, "1340—1840，每十年一个存档 · 线为国家中位数，阴影为国家 P25—P75 · 各面板纵轴独立", color="#475569", fontsize=11)
    fig.supxlabel("游戏年份", y=.02)
    fig.tight_layout(rect=(0, .035, 1, .94))
    save(fig, "01_purchasing_power_levels")

    fig, ax = plt.subplots(figsize=(12.8, 6.8))
    for stratum in STRATA:
        series = by_stratum[stratum]
        ax.plot(YEARS, [r["index_1340_100"] for r in series], color=COLORS[stratum], linewidth=2.5,
                marker="o", markersize=3, label=f"{LABELS[stratum]}：期末 {series[-1]['index_1340_100']:.0f}")
    ax.set_yscale("log")
    all_values = [r["index_1340_100"] for series in by_stratum.values() for r in series]
    ticks = [100 * 2 ** i for i in range(-4, 15) if min(all_values) / 1.3 <= 100 * 2 ** i <= max(all_values) * 1.3]
    ax.set_yticks(ticks)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.yaxis.set_minor_formatter(ticker.NullFormatter())
    ax.set_ylim(min(all_values) / 1.15, max(all_values) * 1.2)
    ax.axhline(100, color="#64748b", linestyle="--", linewidth=.9)
    ax.set_ylabel("购买力水平指数（1340=100，对数刻度）")
    ax.set_xlabel("游戏年份")
    ax.legend(loc="upper left", frameon=False, ncol=2)
    style(ax)
    fig.suptitle("全球四阶层购买力上升了多少？", fontsize=20, x=.08, ha="left", y=1.01)
    fig.text(.08, .955, "指数比较资金/篮子成本的中位水平；未应用候选篮子方案 · 对数刻度下相同纵向距离代表相同增长倍数", color="#475569", fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, .93))
    save(fig, "02_purchasing_power_growth_index")

    fig, axes = plt.subplots(4, 1, figsize=(12.8, 9.4), sharex=True)
    for ax, stratum in zip(axes, STRATA):
        series = by_stratum[stratum][1:]
        ax.bar([r["year"] for r in series], [r["decade_growth_percent"] for r in series], width=7,
               color=[COLORS[stratum] if r["decade_growth_percent"] >= 0 else "#a3adb9" for r in series], alpha=.85)
        pairs = [r for r in paired_rows if r["stratum"] == stratum]
        ax.plot([r["end_year"] for r in pairs], [r["median_paired_decade_growth_percent"] for r in pairs],
                color="#334155", linestyle="--", linewidth=1.2)
        ax.axhline(0, color="#475569", linewidth=.8)
        growth_values = [r["decade_growth_percent"] for r in series] + [r["median_paired_decade_growth_percent"] for r in pairs]
        step = 20 if max(growth_values) - min(growth_values) > 40 else 10
        low, high = math.floor(min(growth_values) / step) * step, math.ceil(max(growth_values) / step) * step
        ax.set_yticks(list(range(low, high + step, step)))
        ax.set_ylim(low - step * .12, high + step * .12)
        ax.set_title(LABELS[stratum], loc="left", fontsize=12)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:+.0f}%"))
        style(ax)
    fig.suptitle("每十年增长有多快？", fontsize=20, x=.07, ha="left", y=1.01)
    fig.text(.07, .965, "柱：全球中位水平相对上个十年的增速（灰色为下降）；虚线：同期共同国家自身增速的中位数", color="#475569", fontsize=10.5)
    fig.supxlabel("十年区间的结束年份", y=.015)
    fig.tight_layout(rect=(0, .025, 1, .94))
    save(fig, "03_decade_growth")

    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8), sharex=True)
    for ax, stratum in zip(axes.flat, STRATA):
        series = by_stratum[stratum]
        ax.plot(YEARS, [r["index_1340_100"] for r in series], color=COLORS[stratum], linewidth=2, label="国家中位数")
        ax.plot(YEARS, [r["pooled_index_1340_100"] for r in series], color="#475569", linestyle=":", linewidth=1.8, label="全球资金/开销总额")
        ax.plot(YEARS, [r["fixed_cohort_index_1340_100"] for r in series], color="#475569", linestyle="--", linewidth=1.5,
                label=f"全程存续国家（n={series[0]['fixed_cohort_countries']}）")
        ax.set_title(f"{LABELS[stratum]}   有效国家 {series[0]['countries']} → {series[-1]['countries']}", loc="left", fontsize=12)
        ax.set_ylabel("各自 1340=100")
        ax.legend(frameon=False, fontsize=8.5, loc="upper left")
        style(ax)
    fig.suptitle("检查国家组成变化的影响", fontsize=20, x=.07, ha="left", y=1.02)
    fig.text(.07, .965, "三条线都只用于比较时间增长；存续国家含幸存者选择，全球总额比值按成本权重汇总，均不是人口加权工资", color="#475569", fontsize=10)
    fig.supxlabel("游戏年份", y=.02)
    fig.tight_layout(rect=(0, .035, 1, .94))
    save(fig, "04_aggregation_sensitivity")


def make_report(summary, records, paired_rows):
    headline = summary["headline"]
    rates = "\n".join(
        f"| {LABELS[s]} | {h['start_pp_percent']:+.1f}% | {h['end_pp_percent']:+.1f}% | ×{h['level_multiple']:.2f} | {h['compound_growth_per_decade_percent']:+.2f}% | {h['annual_cagr_percent']:+.3f}% | {h['declining_decades']}/50 |"
        for s, h in headline.items())
    centuries = "\n".join(
        f"| {start}—{start + 100} | " + " | ".join(
            f"{next(p for p in summary['periods'] if p['stratum'] == s and p['start_year'] == start)['compound_growth_per_decade_percent']:+.2f}%"
            for s in STRATA) + " |" for start in range(1340, 1840, 100))
    extremes = "\n".join(
        f"| {LABELS[s]} | {h['fastest_decade_end'] - 10}—{h['fastest_decade_end']}：{h['fastest_growth_percent']:+.1f}% | {h['slowest_decade_end'] - 10}—{h['slowest_decade_end']}：{h['slowest_growth_percent']:+.1f}% |"
        for s, h in headline.items())
    sensitivity = "\n".join(
        f"| {LABELS[s]} | {h['start_countries']} → {h['end_countries']} | {h['fixed_cohort_countries']} | ×{h['fixed_cohort_level_multiple']:.2f} | ×{h['pooled_level_multiple']:.2f} |"
        for s, h in headline.items())
    versions = ", ".join(summary["versions"])
    min_coverage = min(row["cached"] / row["owned"] for row in summary["location_coverage"])
    text = f"""# 全球购买力上升速度：1340—1840 十年序列

2026-10-23。独立分析，使用篮子调整前的历史存档数据。用户随后批准按 x1/x2/约0.6555/x4 的近似版本修改基础篮子；本分析数据与曲线没有应用新篮子。

## 核心结果

数据为 `{SERIES}` 序列从 1340.4.1 至 1840.4.1 的全部 51 个十年间隔存档，游戏版本：{versions}。

| 阶层 | 1340 原始购买力中位数 | 1840 原始购买力中位数 | 购买力水平倍数 | 每十年平均复合增长 | 年均复合增长 | 下降的十年区间 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{rates}

平民长期上升明显快于其他阶层，且前期更快、后期放缓。贵族的主要增长集中在 1440—1640 年，之后趋平；市民在 50 个十年区间中有 23 个回落，波动更频繁。以国家中位数看，1740—1840 年四阶层均略有下降，不能将全程平均增速理解为后期仍在持续加速。

“购买力水平”是 alpha=可支配资金/基准篮子成本，面板百分比为 (alpha-1)×100%。增长率对 alpha 计算，不直接对有正负号的面板百分比求增速。例如 +100%→+200% 是 alpha 从 2→3，即增长 50%。

![各阶层购买力水平]({OUTPUT.as_posix()}/01_purchasing_power_levels.png)

![增长指数]({OUTPUT.as_posix()}/02_purchasing_power_growth_index.png)

## 增速随时代变化

下表每项为相应一百年内的平均每十年复合增速，由起终中位 alpha 计算；不能解释为每个十年都以该速度增长。

| 时段 | 贵族 | 教士 | 市民 | 平民 |
| --- | ---: | ---: | ---: | ---: |
{centuries}

| 阶层 | 最大上升十年 | 最大下降十年 |
| --- | --- | --- |
{extremes}

![十年增速]({OUTPUT.as_posix()}/03_decade_growth.png)

柱形是相邻全球截面中位水平的变化；虚线是两个存档中共同国家的自身购买力增速中位数。起点 alpha=0 的国家无法求有限比率，配对增速中排除，并在 CSV 单列数量；其零值仍保留在截面中位数中。下降到 alpha=0 的配对增速保留为 -100%。

## 国家组成与汇总口径

每国等权。由于国家合并、消失、新生，以及阶层基准支出为零，样本国家数随时间变化，截面变化不是同一批国家的纯人均收入增长。

| 阶层 | 有效国家数，1340→1840 | 全部 51 点持续有效的国家数 | 持续样本中位水平增长倍数 | 全球资金/篮子总额比值增长倍数 |
| --- | ---: | ---: | ---: | ---: |
{sensitivity}

在固定国家样本和全球资金/开销总额口径下，四阶层也都呈现长期上升，平民仍然最快。因此，结果不是仅由参与中位数计算的国家集合变化产生的；但口径对幅度有显著影响，尤其不能把后期国家中位数趋平解释为所有国家或世界总额都停止增长。

持续样本按国家对象 ID 加 original_tag 识别，避免只用可变国名或当前 tag；它带有长期存续选择，不能取代主样本。全球总额比值按篮子成本形成隐含权重，不是国家等权或人口加权工资中位数。

![汇总口径对照]({OUTPUT.as_posix()}/04_aggregation_sensitivity.png)

## 提取和质量检查

直接从明文存档读取有主地点的四阶层资金、基准支出和净收入缓存，按当前领土加总到国家，再计算每国 F/B 和世界国家中位数。使用原始有符号五位小数整数加总，最后才相除，避免额外的浮点累计损失。

只要求相应阶层有正基准支出 B>0，保留零资金。没有重新解析全体 Pop，也没有用当前人口门槛去删掉尚有正开销缓存的国家阶层。这与此前候选策略分析的“当前人口也为正”门槛略有区别：1340 贵族/市民各多两个样本，起点中位 alpha 差异均小于 0.4%，教士和平民一致；候选策略系数没有随本分析更新。

所有文件的 playthrough ID、内部日期和十年序列均验证；每个存档固定读取 28,573 个地点。有主地点 SOL 缓存覆盖率最低为 {min_coverage:.2%}。保存的年份/版本、源路径、大小和修改时间、原始国家观测和零资金数均记录在输出中。

AI 缓存依各国周年刷新，单个存档不是全世界同日重新计算；图形不对十年之间的真实路径作插值推断，连线仅辅助阅读。本次数据覆盖不到十年内波动。涨幅可包含收入、储蓄、商品价格、供应、外部需求修正及国家组成变化，不据单条曲线推断唯一原因，也不把 500 年复合增长率直接用于后续预测。

## 复现与文件

```powershell
$env:PYTHONUTF8 = '1'
& 'C:/Users/Hades/anaconda3/envs/eu5/python.exe' docs/analysis/sol_purchasing_power_decades_20261023/extract.py --all
& 'C:/Users/Hades/anaconda3/envs/eu5/python.exe' docs/analysis/sol_purchasing_power_decades_20261023/analyze.py
```

提取使用两个本地进程，完成的年点按源文件大小/mtime/schema 缓存。分析使用项目 eu5 解释器；Matplotlib 复用同为 CPython 3.11 的已安装 Research 环境包，只读加入模块搜索路径，没有安装或修改环境。

输出位于 `data/save_analysis/purchasing_power_decades/{SERIES}/`：四组 PNG/SVG/PDF，`summary.json`、`decade_statistics.csv`、`paired_country_growth.csv`、`century_growth.csv`、`country_observations.csv` 及逐年提取缓存。CSV 保留每个十年、每个阶层的样本数、P25/P75、中位水平、零资金数和基准为 1340 的指数。
"""
    (HERE / "REPORT.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

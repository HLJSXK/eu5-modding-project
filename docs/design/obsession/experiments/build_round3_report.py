"""Build the complete handoff 26 report from frozen fit-only artifacts."""
from collections import Counter
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.obsession_sim.acceptance import q
from tools.obsession_sim.experiment import HERE, code_hash, freeze_status, read_json
from tools.obsession_sim.fit_workflow import median_arrival
from tools.obsession_sim.round3_workflow import assert_fit
from tools.eu5_save_parser.world_export import atomic_json

OUT = ROOT / "tmp/obsession_round3"
TARGET = ROOT / "docs/design/obsession/27_Round3_Results.md"


def build_report():
    r = read_json(OUT / "fit_report.json")
    valid, frozen, _ = freeze_status()
    assert valid and frozen == r["frozen_hash"] and code_hash() == r["runtime_hash"]
    assert r["params"] == read_json(HERE / "selected_params.json")
    cells = {k:v for k,v in r["cells"].items() if k.endswith("×R")}
    cells.update(r["world_cells"])
    for key,cell in cells.items():
        assert sorted(x["seed"] for x in cell["runs"]) == list(range(30 if key.endswith("×R") else 10))
        assert_fit(cell["runs"])
        assert all(x["identity"]["code"] == r["runtime_hash"] and x["identity"]["frozen"] == frozen for x in cell["runs"])
    base = cells["S×R"]["runs"]
    mechanics = read_json(OUT / "mechanics_only.json")
    selection = read_json(OUT / "round3_fit_selection.json")
    protocol = read_json(ROOT / "docs/design/obsession/experiments/round3_fit_protocol.json")
    facts = read_json(HERE / "world_facts.json")
    additions = read_json(HERE / "world_facts_round3_additions.json")
    audit = read_json(OUT / "world_audit_batch.json")
    assert audit["passed"] and not audit["zero_impact_errors"]
    lines = ["# 27 第三轮离线实现与拟合集结果\n", "日期：2026-10-22。依据 [26 交接规格](26_Round3_Handoff.md)。所有成绩均为 `fit_only=True`、`omit_wc=True`。全集与留出判分待审计方；本轮未运行或读取留出结果。\n"]
    def text(s):lines.append(s + "\n")
    def table(headers, rows):
        lines.extend(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"])
        lines.extend("| " + " | ".join(str(v).replace("|", "/").replace("\n", " ") for v in row) + " |" for row in rows)
        lines.append("")
    def num(v):return "无法判定" if v is None else f"{v:.3f}"
    def pct(v):return "无法判定" if v is None else f"{100*v:.2f}%"
    def dist(vs):
        values = [v for v in vs if v is not None]
        return "无" if not values else f"n={len(values)}；p10/中位/p90={q(values,.1):.1f}/{q(values):.1f}/{q(values,.9):.1f}"
    text("## 实现选择与边界")
    text("习俗区与过滤后的入边表是载入时的静态配置；没有新增地点级持久变量。四个聚合分别维护国家/市场的全量与开放值，沿用 12 片轮转。酒通过静态地区与当月宗教组直接求值，没有酒模拟器或酒 U 项。D 是唯一国家接触时钟；首次接触、全国流行和波次历史仅进入诊断输出。禁令截止月采用 Python round 的最近整数月规则（正好半月取偶数）。人口相同按稳定国家索引排列。")
    text("六维 Latin 分层抽样一次，64 个候选，生成种子 2026102201；前 6 名各补种子 1–4。五种子排序逐项取中位数。p_K 仅在双方候选都有至少 3 条可判定 K 时比较；稀疏 K 比较先按规范参数哈希排好输入，以保证确定性。回退 R2 同时恢复首次接触+240及旧的未退潮国家开波重置规则。")
    text(f"运行时 `{r['runtime_hash']}`；冻结身份 `{frozen}`；6 个拟合参数，{protocol['fit_AB_targets']} 个拟合 A/B 目标，D4 上限 8。手设常数清单 {read_json(HERE/'structural_config.json')['manual_constant_count']} 项。")
    text("## 输入")
    raw_hash = hashlib.sha256((HERE / "world_facts.json").read_bytes()).hexdigest()
    text(f"事实总数 {len(facts['facts'])}；文件 SHA256 `{raw_hash}`。审计方新增 43 条 re_、4 条 ea_、1 条 ru_，逐字保留。30 种子世界输入审计通过，zero_impact_errors 为空。")
    table(["组", "事实数"], sorted(Counter(f["id"].split("_")[0] for f in facts["facts"]).items()))
    text("既有五处首都缺项保留：af_dendi_formation、eu_scotland_capital_edinburgh、sa_dec_form_berar、sa_mse_luangprabang_formation、sa_ins_mat_capital_kartasura。re_por_calicut、re_ned_masulipatnam、re_eng_surat 在样本月份因同市场有领土被排除，符合商人资格规则。")
    text("编纂局限（冻结 additions 文件）：" + json.dumps(additions.get("known_gaps", facts.get("known_gaps")), ensure_ascii=False))
    text("存档可用范围核查：两份正式 timeline.json 均为 52 档，1338.4.1–1840.4.1。磁盘另有 SOL 局 1930 年导出，但原版局对应导出和原始归档均未找到；没有将孤立文件或推断年份拼成另一份清单。本轮按可验证的两份完整清单运行 O 诊断，保持 23 的真实终点规则。R 商人先验仍只使用冻结的 1338–1630 样本，不重算。")
    text("## 测试与期望值改动")
    text("全部 obsession_sim Python 测试、存档解析/关系/世界导出/归档四组依赖和两组 Node 工作台检查通过。core 的四组合成参考实验与修改前完整结果 JSON 哈希逐位相同，证据在 tmp/obsession_round3/core_equivalence.json。")
    table(["测试/夹具", "旧值或语义", "新值或语义", "依据"], [
        ["KFixture（影响 K1/K5 既有区间测试）", "等人口；不设大国条件", "国家1人口2，其余1，保持区间测试对象为大国", "J15"],
        ["test_j6_observer_nonoccurrence_window_is_shortened[K2]", "对手0也通过", "对手至少1后检验90年窗口", "J14"],
        ["test_no_roads_or_straits_have_additional_weight_and_wine_is_constant", "wine.x=[30,0,0]与无时钟对象", "同样背景值；无酒对象", "C1"],
        ["test_wine_removal_uses_an_empty_seed_collection_and_removes_preemption", "空种子酒对象", "所有背景0；先占0", "C1"],
        ["test_each_historical_negative_constraint_can_detect_a_violation[wine]", "改酒对象x=60", "合成回调60，继续测试不变量检测器", "C1"],
        ["test_actual_cross_boundary_land_contact_is_not_a_spontaneous_european_tea_seed", "以开局习俗为邻接源", "以普通非习俗源测试跨洲邻接", "C2"],
        ["test_positive_habit_rebase_preserves_the_entire_future_curve", "join=0", "D=240；完整未来曲线断言原样保留", "C3"],
        ["test_p3_creates_a_ban_shortens_hold_and_does_not_stack", "join:0→−110", "D:240→130；退潮月仍130", "C3"],
        ["test_entry_clock_starts_before_queue_service_and_survives_wave_renewal", "join=20", "D=1460；未退潮开波不改D", "C3"],
        ["test_j12_budget_rejected_event_is_counted / test_effect_activation_rejects_stale_aggregate_and_respects_budget", "含酒对象的月账本", "三商品账本；预算拒绝计数断言不变", "C1"],
        ["test_validation.experiment", "R份额夹具0.5", "R份额夹具0.9；数值0.003不变", "C4"],
        ["test_validation.seed_cache", "旧缓存身份", "补rollbacks=[]、mechanics_only=False", "C1–C4 新诊断隔离"],
        ["test_acceptance_endpoint_labels_partial_report_when_matrix_is_absent", "round2目录", "round3目录；内容与状态码不变", "可视化轮次切换"],
    ])
    text("structural.py 对 join 的全文检索仅余兼容接口名 clock_joined、历史计费字典键 join_write，以及字符串 join 方法；无 self.join、sim.join 或加入月计算。对应检索输出保存于 tmp/obsession_round3/join_search.txt。")
    text("## 机制体检（第二轮冻结参数，无目标表或判分器）")
    text(f"正式机制体检次数 {protocol['mechanics_run_count']}。参数：`{json.dumps(mechanics['params'],ensure_ascii=False)}`。")
    table(["商品", "习俗地点", "值恒定", "习俗邻接到达", "拒收输入", "曾为成员地点", "波次数"],
          [[g,mechanics['zone_sizes'][g],mechanics['zone_values_constant'][g],mechanics['zone_adjacency_arrivals'][g],mechanics['zone_rejected_inputs'][g],mechanics['ever_member'][g],len(mechanics['waves'][g])] for g in ('coffee','tea','tobacco')])
    for g,c in mechanics['clocks'].items():
        history=c['history']
        text(f"{g}：全国流行国家 {len({h['country'] for h in history if h['national_month'] is not None})}；上限退潮且未全国流行国家 {len({h['country'] for h in history if h['national_month'] is None and h['decay_start_month'] is not None})}。首次接触到退潮间隔/月：{dist([h['decay_start_month']-h['first_touch_month'] for h in history if h['decay_start_month'] is not None])}。开波原因：{dict(Counter(w['reason'] for w in mechanics['waves'][g]))}。")
    text(f"峰值 U={mechanics['peak_U']}；最大轮次延迟={mechanics['peak_round_delay_months']}月；因预算放弃事件={mechanics['events_abandoned_budget']}。维护工作可超过服务预算，超预算如实报告，不改固定值。")
    text("## 预注册扫描与选参")
    text("第二轮已登记49+147组；本轮只扫描一次。协议先提交，选参文件/日志先于诊断提交。未扩大范围，未增加参数，未读取留出或全集成绩。")
    text("冻结参数：`" + json.dumps(r['params'],ensure_ascii=False) + "`。")
    phase = read_json(OUT / "round3_fit_phase_a.json")
    table(["候选", "p", "rho", "λ商人", "λ领地", "先占", "同市场", "违反", "峰U", "2tol", "次序", "tol", "K", "可判K"],
        [[i, *[row['params'][k] for k in protocol['parameter_names']], row['metrics']['violation_count'],row['metrics']['peak_U'],pct(row['metrics']['fit_within_2tol']),pct(row['metrics']['fit_p_order']),pct(row['metrics']['fit_within_tol']),pct(row['metrics']['p_K']),row['metrics']['triggered_K']] for i,row in enumerate(phase)])
    text("### 前六名的逐种子结果与五种子中位排序")
    rows=[]
    for rank,rec in enumerate(selection['finalists'],1):
        i=protocol['grid'].index(rec['params'])
        for path in rec['runs']:
            run=read_json(path);assert_fit([run])
            rows.append([rank,i,run['seed'],run['violation_count'],run['peak_U'],pct(run['fit_within_2tol']),pct(run['fit_p_order']),pct(run['fit_within_tol']),pct(run['p_K']),run['triggered_K'],run['peak_round_delay_months'],run['events_abandoned_budget']])
        m=rec['metrics'];rows.append([rank,i,'中位',m['violation_count'],m['peak_U'],pct(m['fit_within_2tol']),pct(m['fit_p_order']),pct(m['fit_within_tol']),pct(m['p_K']),m['triggered_K'],m['peak_round_delay_months'],m['events_abandoned_budget']])
    table(['排名','候选','种子','违反','峰U','2tol','次序','tol','K','可判K','延迟/月','放弃事件'],rows)
    text("## 冻结参数诊断")
    table(['配置/世界','次数','tol','2tol','次序','次序上限','K','可判K','违反最大','unseeded','conn','健全率','峰U','延迟/月','放弃总数','拒收输入中位'],
        [[key,c['run_count'],pct(c['fit_within_tol']),pct(c['fit_within_2tol']),pct(c['fit_p_order']),pct(c['fit_p_order_upper']),pct(c['p_K']),num(c['triggered_K_median']),c['violation_count'],pct(c['p_unseeded']),pct(c['p_conn']),pct(c['healthy_rate']),c['peak_U'],c['peak_round_delay_months'],c['events_abandoned_budget'],{g:q([x['zone_rejected_inputs'][g] for x in c['runs']]) for g in ('coffee','tea','tobacco')}] for key,c in cells.items()])
    text("O 两局各配置10种子，仅作诊断，不作 L2 判断。计分未到达仍在分母，以下目标中位数把未到达记作 +∞。")
    text("### 拟合集 A/B 地区结果")
    rows=[]
    for key in ('S×R','H×R'):
        runs=cells[key]['runs']
        for m in runs[0]['milestones']:
            if m['grade'] not in ('A','B'):continue
            samples=[next(a for a in run['milestones'] if a['id']==m['id']) for run in runs]
            got=median_arrival([a['simulated_year'] for a in samples])
            rows.append([key,m['id'],m['name'],m['target_year'],m['tolerance_months']/12,'未到达' if got is None else f'{got:.1f}',sum(a['simulated_month'] is not None for a in samples),pct(sum(a['within_tolerance'] for a in samples)/30),pct(sum(a['within_2tol'] for a in samples)/30)])
    table(['配置','目标','地区','目标年','容差/年','含未到达中位年','到达/30','tol','2tol'],rows)
    text("## 新事实接触次数（S×R 30次）")
    text("触发次数取实际成功注入，另列月风险抽样成功的尝试次数（可因习俗区/退潮拒收）。两列按当前有效常驻事实逐条计数，零次照常报告。")
    new_facts=[f for f in additions['facts'] if f['id'].startswith('re_')]
    assert len(new_facts)==43
    table(['常驻事实','成功注入次数中位','最小','最大','抽样触发尝试中位','咖啡/茶/烟草成功注入中位'],[[f['id'],q([x.get('fact_contact_inputs',{}).get(f['id'],0) for x in base]),min(x.get('fact_contact_inputs',{}).get(f['id'],0) for x in base),max(x.get('fact_contact_inputs',{}).get(f['id'],0) for x in base),q([x['fact_contacts'].get(f['id'],0) for x in base]),[q([x.get('fact_contact_by_good',{}).get(g,{}).get(f['id'],0) for x in base]) for g in ('coffee','tea','tobacco')]] for f in new_facts])
    text("## K 规则与案例")
    rows=[];cases=[]
    for key,c in cells.items():
        for kid in ('K1','K2','K3','K4','K5','K6','K7'):
            rules=[next(a for a in run['K'] if a['id']==kid) for run in c['runs']]
            counts=Counter(a['status'] for a in rules)
            rows.append([key,kid,counts['pass'],counts['fail'],counts['untriggered']])
            samples=[a for k in rules for a in k['cases']];counts=Counter(a['status'] for a in samples)
            cases.append([key,kid,counts['pass'],counts['fail'],counts['untriggered'],sum(a.get('reason')=='rival never present' for a in samples),dict(Counter(a.get('reason','interval result') for a in samples))])
    table(['配置/世界','规则','通过次数','失败次数','未触发次数'],rows)
    table(['配置/世界','规则','通过案例','失败案例','未触发案例','K2对手从未出现','原因计数'],cases)
    text("## 国家时钟与波次")
    rows=[]
    for key in ('S×R','H×R'):
        for g in ('coffee','tea','tobacco'):
            history=[h for run in cells[key]['runs'] for h in run['clocks'][g]['history']]
            rows.append([key,g,*[dist([h[k] for h in history]) for k in ('first_touch_month','national_month','decay_start_month')],dict(Counter(w['reason'] for run in cells[key]['runs'] for w in run['waves'][g]))])
    table(['配置','商品','首次接触月分布','全国流行月分布','退潮开始月分布','开波原因计数'],rows)
    rows=[]
    for tag,g in [('TUR','coffee'),('MAM','coffee'),('F_SAFAVID','coffee'),('CAS','tobacco'),('POR','tobacco'),('ENG','tobacco'),('FRA','tobacco')]:
        samples=[]
        for run in base:
            countries={i for i,label in enumerate(run['country_labels']) if label==tag}
            h=[h for h in run['clocks'][g]['history'] if h['country'] in countries]
            samples.append({k:min((a[k] for a in h if a[k] is not None),default=None) for k in ('first_touch_month','national_month','decay_start_month')})
        rows.append([tag,g,*[num(median_arrival([a[k] for a in samples])) for k in ('first_touch_month','national_month','decay_start_month')],*[sum(a[k] is not None for a in samples) for k in ('first_touch_month','national_month','decay_start_month')]])
    table(['国家','商品','首次接触中位月','全国流行中位月','退潮中位月','接触次数/30','流行次数/30','退潮次数/30'],rows)
    text("月份均自1337年1月起算。上述逐国表对每次运行取首次对应事件，再含未发生的 +∞ 求30次中位；完整跨波次历史保存在 JSON。")
    text("## 消融、回退与双倍预算")
    variants=[('基线',r['baseline_10']),*r['ablations'].items(),*r['rollbacks'].items(),('双倍预算',r['budget_sensitivity']['double_budget'])]
    table(['对照','tol','2tol','次序','上限','K','可判K','违反中位','峰U中位','延迟中位/月','放弃中位'],[[name,pct(v['metrics']['fit_within_tol']),pct(v['metrics']['fit_within_2tol']),pct(v['metrics']['fit_p_order']),pct(v['metrics']['fit_p_order_upper']),pct(v['metrics']['p_K']),v['metrics']['triggered_K'],v['metrics']['violation_count'],v['metrics']['peak_U'],v['metrics']['peak_round_delay_months'],v['metrics']['events_abandoned_budget']] for name,v in variants])
    b=r['budget_sensitivity'];text(f"双倍预算 {sum(a['moved_beyond_tolerance'] for a in b['milestones'])}/{b['eligible_milestones']} 条拟合 A/B 目标中位位移超容差，比例 {pct(b['moved_fraction'])}；{'否决' if b['blocks_L2'] else '不单独否决'} L2/L3。回退只用于解释，不据此重选设计或参数。")
    text("## 闸门")
    s=cells['S×R']
    l1=[]
    if s['fit_p_order']<.6:l1.append(f"S×R 拟合次序 {pct(s['fit_p_order'])} < 60%")
    if s['violation_count']:l1.append(f"负面约束最大违反数 {s['violation_count']} > 0")
    text("未达 L1，差在"+'；'.join(l1)+'。' if l1 else '拟合集满足 S×R L1 的必要条件，全集与留出待审计方。')
    for level in ('L2','L3'):
        gaps=[]
        for metric,limit in read_json(HERE/'acceptance_spec.json')['thresholds'][level]['S×R'].items():
            actual={'p_order':s['fit_p_order'],'within_2tol':s['fit_within_2tol'],'violations_max':s['violation_count'],'D_event_max':cells['H×R'].get('D_event')}.get(metric)
            if actual is not None and (actual>limit if metric.endswith('_max') else actual<limit):gaps.append(f'{metric}={actual:.4g}（要求{limit}）')
        if b['blocks_L2']:gaps.append('双倍预算否决')
        text(f"未达 {level}，差在"+'；'.join(gaps if gaps else ['全集与留出待审计方；本轮 O 仅10次诊断，不作L2判断'])+'。')
        r['gates'][level]['failures']=gaps
    text("## 计划冲突处理与待决问题")
    text("扫描前体检重复原因：首次时钟计数把波次当国家，修正后复核；随后将新事实接触分成成功注入与抽样尝试，增加按商品分列，并使诊断路径和回放颜色遵守习俗区不外溢、不退潮，再用相同参数复核。全部体检均不读取成绩，次数如实预登记。新增事实副本没有 known_gaps 字段，编纂局限实际位于 world_facts.json，按原文引用，未改输入。没有改变四项机制、判分口径、参数范围、固定值、世界事实或目标定义。可用观察者档案与用户所述1930年存在范围差异，采用可验证的两份52档清单（见输入节），没有延长世界终点。协议交叉引用 §6.2 实际排序位于 §6.3，按后者的完整列表执行；tea_0 在既有文件中已删除，tea_1 保留定义并 scored=false。上述为执行细节，未据成绩调整规则。")
    text("待决问题：观察者原版局1840年之后的原始归档/完整导出在当前工作区不可用；不阻塞本轮按真实终点执行的10种子诊断。模型与事实的进一步修改由审计方决定。")
    text("## 交付物与复现")
    text("`tools/obsession_sim/round3_workflow.py` 依次提供 mechanics、protocol、fit、select、diagnostics。输入审计用 round2 audit-batch。报告构建器校验完整种子和冻结身份。所有大文件留 tmp/obsession_round3，不进 Git；fit_report.html 可离线双击打开，工作台支持习俗区、截止时钟、K2未触发、四项回退与双局切换。通知审计方的可审阅交付为本报告及已提交的选参日志；未自动向其他聊天发送消息。")
    TARGET.write_text("\n".join(lines),encoding='utf-8')
    atomic_json(OUT/'fit_report.json',r)
    packed=base64.b64encode(gzip.compress(json.dumps(r,ensure_ascii=False,separators=(',',':')).encode('utf-8'))).decode('ascii')
    template=(ROOT/'docs/design/obsession/experiments/structural_workbench.html').read_text(encoding='utf-8')
    (OUT/'fit_report.html').write_text(template.replace('</body>','<script type="application/octet-stream" id="obsession-acceptance-gzip">'+packed+'</script></body>'),encoding='utf-8')
    print(f'Wrote {TARGET}; complete frozen fit-only report, {len(phase)} candidates.')
    return r


if __name__=='__main__':build_report()

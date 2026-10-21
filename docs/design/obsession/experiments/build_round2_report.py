"""Render only the committed reference's final fit/K diagnostics as tables."""
from collections import Counter
from pathlib import Path
import json
import sys
import base64
import gzip

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root))

from tools.obsession_sim.experiment import read_json, code_hash, freeze_status
from tools.obsession_sim.acceptance import q
from tools.obsession_sim.fit_workflow import median_arrival
from tools.obsession_sim.graph import load_json
from tools.eu5_save_parser.world_export import atomic_json

def fit_failures(spec,s,h,budget_blocks):
    """L1 needs full A/B outcomes; only L2/L3 use these fit-only metrics."""
    known={'L1':[]}
    for level in ('L2','L3'):
        failures=[]
        for name,limit in spec['thresholds'][level]['S×R'].items():
            actual={'p_order':s['fit_p_order'],'within_2tol':s['fit_within_2tol'],
                    'violations_max':s['violation_count'],'D_event_max':h.get('D_event')}.get(name)
            if actual is None:continue
            maximum=name.endswith('_max')
            if (maximum and actual>limit) or (not maximum and actual<limit):
                failures.append(f'已知拟合集必要条件未达：S×R {name}={actual:.4g}，要求 {"≤" if maximum else "≥"}{limit}')
        if budget_blocks:
            failures.append('双倍预算下超过三分之一拟合 A/B 里程碑移动超容差，按 M4 不得宣称 L2')
        known[level]=failures
    return known


def build_report():
    report=read_json(root/'tmp/obsession_round2/fit_report.json')
    assert report['format']=='obsession.fit-diagnostics/1' and report['fit_only']
    valid,frozen,_=freeze_status()
    assert valid and frozen==report['frozen_hash'] and code_hash()==report['runtime_hash']
    assert report['params']==read_json(root/'tools/obsession_sim/selected_params.json')
    all_cells={**report['cells'],**report['world_cells']}
    for cell in all_cells.values():
        assert sorted(r['seed'] for r in cell['runs'])==list(range(30))
        for r in cell['runs']:
            assert r['identity']['fit_only'] and all(t['split']=='fit' for t in r['milestones'])
            assert r['identity']['code']==report['runtime_hash'] and r['identity']['params']==report['params']
            assert r['identity']['frozen']==report['frozen_hash']

    known=fit_failures(read_json(root/'tools/obsession_sim/acceptance_spec.json'),
        report['cells']['S×R'],report['cells']['H×R'],report['budget_sensitivity']['blocks_L2'])
    for level,failures in known.items():report['gates'][level]['failures']=failures
    report.update(frozen_valid=True,diagnostics_complete=True,known_fit_failures=known)
    g=load_json(root/'tmp/obsession_real/eu5_1337.json')
    lines=[]
    def table(headers,rows):
        lines.append('| '+' | '.join(headers)+' |')
        lines.append('| '+' | '.join('---' for _ in headers)+' |')
        lines.extend('| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in rows)
        lines.append('')
    def pct(v):return '无法判定' if v is None else f'{100*v:.2f}%'
    def num(v):return '无法判定' if v is None else f'{v:.2f}'
    lines.append('## 30 次拟合集与条件诊断\n')
    rows=[]
    for key,c in all_cells.items():
        if key in ('S×O','G×O'):continue
        is_r=key.endswith('×R')
        rows.append([key,c['run_count'],pct(c['fit_within_2tol']) if is_r else '不比较历史年份',
            pct(c['fit_p_order']) if is_r else '—',pct(c['p_K']),pct(c['healthy_rate']),
            c['violation_count'] if is_r else '—',c['peak_U'],c['peak_round_delay_months'],c['events_abandoned_budget']])
    table(['配置/世界','次数','拟合 2×容差内','拟合次序','K 中位','健全率','负面约束最大数','峰值 U','轮次延迟/月','预算放弃事件总数'],rows)
    lines.append('所有格均为 fit_only；O 只解释条件规律。完整 L1/留出与正式闸门仍由审计方执行。\n')
    rows=[]
    for key,c in all_cells.items():
        if key in ('S×O','G×O'):continue
        def bad(r,kind):
            for a in r['sanity'].values():
                if kind=='V_land' and a['V_land'] is not None and a['V_land']>1.5:return True
                if kind=='C50' and a['C50'] is not None and a['C50']>.5:return True
                if kind=='T_alive' and (a['T_alive_failed'] or (a['T_alive'] is not None and a['T_alive']>100)):return True
            return False
        rows.append([key,*[sum(bad(r,k) for r in c['runs']) for k in ('V_land','C50','T_alive')],
                     sum(r['healthy'] is None for r in c['runs'])])
    table(['配置/世界','陆路速度超限次数','50 年覆盖超限次数','百年外传失败/超时次数','健全性未知次数'],rows)
    lines.append('每一列按运行计数；同一次运行可能同时触发多个问题，不能把各列相加当作失败运行数。\n')
    lines.append('### K 条及事件质量\n')
    rows=[]
    for key,c in all_cells.items():
        if key in ('S×O','G×O'):continue
        detail=[]
        for kid in ('K1','K2','K4','K5','K6','K7'):
            counts=Counter(next(k['status'] for k in r['K'] if k['id']==kid) for r in c['runs'])
            detail.append(f"{counts['pass']}/{counts['fail']}/{counts['untriggered']}")
        rows.append([key,*detail,num(c['triggered_K_median']),c['B_max'],c['M_mis'],
            ' / '.join(num(c['E_gap_by_good'][good]) for good in ('coffee','tea','tobacco'))])
    table(['配置/世界','K1 通过/失败/未触发','K2','K4','K5','K6','K7','可判定 K 中位','封顶前 B_max','M_mis','咖啡/茶/烟草 E_gap 年'],rows)
    lines.append('未触发包含左/右删失、首都改变或其他取消条件，不等于通过。K3 按冻结规格未设计。E_gap 没有合格月时为无法判定。\n')
    lines.append('当前判分规则中，只要一条 K 的任一已判定案例失败，该次运行的整条 K 就失败。下表另列案例级结果，避免把规则通过率理解成国家案例通过率；左边界已满足的机会不建案例，右删失和取消的案例不进入案例通过率分母。\n')
    lines.append('K6 的“通过”表示禁令期间强度仍保留至少初值一半，即模型表现出禁令未能充分压制；它不是政策成功率。固定的自然退潮同样可能使强度低于一半，因此此指标不单独识别禁令的因果作用。\n')
    rows=[]
    for key,c in all_cells.items():
        if key in ('S×O','G×O'):continue
        for kid in ('K1','K5','K6'):
            cases=[a for r in c['runs'] for k in r['K'] if k['id']==kid for a in k['cases']]
            counts=Counter(a['status'] for a in cases)
            reasons=Counter()
            for a in cases:
                if a['status']!='fail':continue
                reason={'outcome absent after upper bound':'超过上界仍未到达',
                        'ban-period minimum fell below half':'观察期最低强度低于初值一半'}.get(a.get('reason'),a.get('reason'))
                if not reason and a.get('t1') is not None:
                    lower=(50 if kid=='K1' else 5)-(10 if '×O' in key else 0)
                    reason='到达过早' if (a['t1']-a['t0'])/12<max(0,lower) else '到达过晚'
                reasons[reason or '未说明']+=1
            decided=counts['pass']+counts['fail']
            rows.append([key,kid,counts['pass'],counts['fail'],counts['untriggered'],
                         pct(counts['pass']/decided if decided else None),dict(reasons)])
    table(['配置/世界','规则','通过案例','失败案例','删失/取消案例','案例通过率','失败原因计数'],rows)
    lines.append('## 逐通道对照与预算\n')
    rows=[]
    names=dict(contact='关闭商人常驻',ownership='关闭领地回流',market='关闭同市场带动',preemption='关闭先占',wine='移除酒背景')
    contrasts=[('S×R 基线（种子 0–9）',report['baseline_10']),
               *[(names[k],v) for k,v in report['ablations'].items()],
               ('双倍预算',report['budget_sensitivity']['double_budget'])]
    for key,rec in contrasts:
        m=rec['metrics']
        members=[read_json(path) for path in rec['runs']]
        assert sorted(r['seed'] for r in members)==list(range(10))
        assert all(r['identity']['fit_only'] and all(t['split']=='fit' for t in r['milestones']) for r in members)
        assert all(r['identity']['code']==report['runtime_hash'] and r['identity']['params']==report['params']
                   and r['identity']['frozen']==report['frozen_hash'] for r in members)
        rows.append([key,pct(m['fit_within_tol']),pct(m['fit_within_2tol']),pct(m['fit_p_order']),pct(m['p_K']),m['violation_count'],
            num(q([r['triggered_K'] for r in members])),m['peak_U'],m['peak_round_delay_months'],m['events_abandoned_budget']])
    table(['对照','拟合容差内','拟合 2×容差内','拟合次序','K','负面约束最大数','可判定 K 中位','峰值 U','轮次延迟/月','预算放弃事件'],rows)
    lines.append('关闭通道也会改变 K 的合格案例构成。对照同时报告可判定规则数；不能仅以 K 比例上升认定机制表现改善。\n')
    b=report['budget_sensitivity']
    lines.append(f"双倍预算：{sum(m['moved_beyond_tolerance'] for m in b['milestones'])}/{b['eligible_milestones']} 条拟合 A/B 里程碑中位位移超容差（{pct(b['moved_fraction'])}）；预算检查{'阻止' if b['blocks_L2'] else '不单独阻止'} L2 宣称。双未到达不记移动，单侧未到达记超容差。该检查通过也不能抵消其他门槛失败。\n")
    lines.append('### 基线实际输入量\n')
    share=read_json(root/'tools/obsession_sim/world_priors.json')['foreign_share_quantiles']['0.5']
    hazard=report['params']['lambda_contact']*share
    lines.append(f"R 每个有记录常驻社区采用共同份额 {share:.8g}，故未乘亲和/先占时的基础年风险率约 {hazard:.4g}；领地通道则为 {report['params']['lambda_ownership']:.6g}×A_C。两个 λ 乘的尺度不同，数值接近不表示实际输入强度接近。\n")
    base=report['cells']['S×R']['runs']
    rows=[]
    for good in ('coffee','tea','tobacco'):
        for channel in ('contact','ownership'):
            a=[r['channel_audit'][good][channel] for r in base]
            rows.append([good,channel,num(q([r['inputs'] for r in a])),num(q([r['receiving_countries'] for r in a])),
                num(q([r['ownership_population_share_median'] for r in a])) if channel=='ownership' else '—'])
    table(['商品','通道','入口次数中位','接收国家数中位','回流人口份额中位'],rows)
    lines.append('### 史料案例对照（只报告，不拟合）\n')
    rows=[]
    for tag,context in [('ENG',60),('FRA',160),('VEN',170)]:
        cases=[]
        for r in base:
            labels=r['country_labels']
            cases += [c for k in r['K'] if k['id']=='K1' for c in k['cases'] if c.get('country') is not None and labels[c['country']]==tag]
        lags=[(c['t1']-c['t0'])/12 if c['t1'] is not None else None for c in cases]
        statuses=Counter(c['status'] for c in cases)
        rows.append([tag,len(cases),sum(v is not None for v in lags),num(median_arrival(lags)),dict(statuses),context])
    table(['K1 国家','有案例次数','记录到首都阶段2','包含未到达的中位年差','判定状态','史料背景约/年'],rows)
    rows=[]
    for tag,context in [('TUR',17),('CAS','40–50')]:
        cases=[c for r in base for c in r['ownership_case_studies'] if c['country']==tag]
        points=Counter(g.names[c['capital_stage2']['node']] for c in cases if c['capital_stage2'])
        rows.append([tag,len(cases),sum(c['lag_years'] is not None for c in cases),num(median_arrival([c['lag_years'] for c in cases])),dict(points),context])
    table(['领地案例','运行数','首都达到阶段2','包含未到达的中位年差','实际首都地点','史料背景约/年'],rows)
    lines.append('奥斯曼案例以 1539 年也门事实起算；开罗、叙利亚等领地与邻接路线可同时作用，因此不是也门回流的单独因果估计。西班牙以各种子 1493–1496 的 Hispaniola 生效月起算。冻结目标 coffee_4 虽名为 Constantinople，实际筛选 balkan_region；tobacco_0 筛选 iberia_region，均要求区域至少半数人口所在地点 x≥20。因此首都节点达到阶段2不等于相应地区目标到达。常驻案例也可能同时受其他通道影响；未触发/删失不能补成成功。\n')
    lines.append('## 拟合集 A/B 地区结果\n')
    rows=[]
    for m in base[0]['milestones']:
        if m['grade'] not in ('A','B'):continue
        values=[next(x['simulated_month'] for x in r['milestones'] if x['id']==m['id']) for r in base]
        median=median_arrival(values)
        threshold='x>0' if m['threshold']=='positive' else 'x≥'+str(m['threshold'])
        rows.append([m['good'],m['name'],json.dumps(m['where'],ensure_ascii=False,separators=(',',':')),threshold,m['target_year'],m['tolerance_months']/12,
            '未到达' if median is None else f'{1337+median/12:.1f}',sum(v is not None for v in values)])
    table(['商品','拟合地区','冻结地域筛选','强度门槛','目标年','容差/年','30 次中位年（未到达按∞）','到达次数/30'],rows)
    (root/'tmp/round2_results_sections.md').write_text('\n'.join(lines),encoding='utf-8')
    out=root/'tmp/obsession_round2'
    atomic_json(out/'fit_report.json',report)
    template=(root/'docs/design/obsession/experiments/structural_workbench.html').read_text(encoding='utf-8')
    assert template.count('</body>')==1,'missing standalone-report injection point'
    data=json.dumps(report,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    packed=base64.b64encode(gzip.compress(data,mtime=0)).decode('ascii')
    (out/'fit_report.html').write_text(template.replace('</body>',
        '<script type="application/octet-stream" id="obsession-acceptance-gzip">'+packed+'</script></body>'),encoding='utf-8')
    print('Wrote fit-only tables:',len(lines),'lines; no holdout outcomes read.')


if __name__=="__main__":
    build_report()

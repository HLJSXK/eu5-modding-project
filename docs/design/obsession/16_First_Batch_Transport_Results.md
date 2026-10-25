# 首批痴迷传播：贸易、走廊与 U 峰值验证

日期：2026-10-19。实现范围：离线模拟器；没有部署 EU5 玩法脚本。

**城市代理目标 36/36 通过；已实现的六项负面约束零违反。** 三商品合计峰值 **49,995 U/月**，比同一模型宽预算运行的 198,275 U 下降 **74.8%**。

同额度纯邻接对照峰值 49,931 U；加入贸易与走廊后只增加 **64 U（0.13%）**。

这是允许的静态贸易近似：1337 年所有权，有限历史港口/商队骨架，年份和路线权重中的设计假设明确标 C。城市到达不等于地区人口加权采纳；未核对每行史料、未跑真实跨洋占有/出口条件、联合咖啡/酒与烟草禁令试验，也没有独立历史快照。因此**不宣称达到 15 文档的完整 L1/L2/L3**。开发中已查看全部城市目标，所谓 holdout 只作诊断分组，不能当盲测。

## 预算与性能

| 共享预算 U/月 | 实测峰值 | 总 U | 城市通过数 | 超额月数 |
|---:|---:|---:|---:|---:|
| 40,000 | 39,995 | 92,390,083 | 35/36 | 0 |
| 50,000 | 49,995 | 109,312,654 | 36/36 | 0 |
| 60,000 | 59,995 | 130,095,267 | 36/36 | 0 |
| 70,000 | 69,997 | 137,962,647 | 36/36 | 0 |
| 80,000 | 79,986 | 144,574,889 | 36/36 | 0 |
| 120,000 | 119,979 | 147,928,770 | 36/36 | 0 |
| 480,000 | 198,275 | 151,326,898 | 36/36 | 0 |

选择扫描中最小且全目标通过、负面约束通过、零超额的预算；不是数学上的全局最优证明。先计入所有商品的时钟、输入、清理与重标定，再轮转分配节点服务额度。预算过低的未到达、时效损失与维护超额全部保留。

U 包括原 PRICE_CLOCK、每次服务额外 10+d 的系数求值审计、路线变更/源输入/系数写入/唤醒/清队列/时钟续波。图生成、最短路预编译、回放与统计是离线工作；U 仍是抽象原语，不是引擎耗时，SOL 经济聚合及实际脚本展开待实机补验。

## 组件对照

| 情景 | 通过数 | 峰值 U/月 |
|---|---:|---:|
| trade+corridors | 36/36 | 49,995 |
| adjacency only | 3/36 | 49,931 |
| without transport | 4/36 | 49,941 |
| without corridors | 12/36 | 49,939 |

所有对照使用同一初值、原目标/容差、共享参数、窗口和预算；没有把目标城市直接设为成员或风尚。

## 逐项时间目标

| 商品 | 城市/指标 | 目标年 | 模拟年 | 容差 年 |
|---|---|---:|---:|---:|
| coffee | Yemen | 1450.0 | 1455.1 | 15 |
| coffee | Mecca | 1505.0 | 1505.7 | 15 |
| coffee | Cairo | 1520.0 | 1519.0 | 15 |
| coffee | Syria | 1535.0 | 1527.2 | 15 |
| coffee | Constantinople | 1555.0 | 1542.0 | 20 |
| coffee | Iran | 1575.0 | 1559.0 | 25 |
| coffee | Venice contact | 1615.0 | 1610.0 | 25 |
| coffee | Venice fashion | 1645.0 | 1626.4 | 25 |
| coffee | England | 1655.0 | 1657.2 | 25 |
| coffee | Low Countries | 1665.0 | 1678.2 | 25 |
| coffee | France | 1680.0 | 1657.2 | 25 |
| coffee | Austria | 1686.0 | 1668.2 | 25 |
| coffee | North Germany | 1690.0 | 1696.6 | 25 |
| tea | Japan custom | 1337.0 | 1337.0 | 0 |
| tea | Japanese tea ceremony | 1580.0 | 1570.9 | 20 |
| tea | Central Asia | 1450.0 | 1417.8 | 40 |
| tea | Russia contact | 1638.0 | 1638.0 | 25 |
| tea | Russia fashion | 1710.0 | 1713.8 | 25 |
| tea | Iran | 1675.0 | 1647.5 | 30 |
| tea | Dutch contact | 1610.0 | 1616.8 | 20 |
| tea | Dutch fashion | 1650.0 | 1639.8 | 20 |
| tea | English contact | 1658.0 | 1658.1 | 20 |
| tea | English fashion | 1676.0 | 1664.6 | 20 |
| tea | English obsession | 1740.0 | 1725.0 | 20 |
| tea | Northern Europe | 1700.0 | 1680.2 | 25 |
| tobacco | Iberia | 1545.0 | 1534.4 | 20 |
| tobacco | France | 1570.0 | 1572.5 | 20 |
| tobacco | England | 1590.0 | 1581.3 | 20 |
| tobacco | Low Countries | 1600.0 | 1584.9 | 20 |
| tobacco | Ottomans | 1610.0 | 1594.9 | 20 |
| tobacco | Japan | 1600.0 | 1604.9 | 20 |
| tobacco | South China | 1600.0 | 1588.2 | 25 |
| tobacco | India | 1605.0 | 1607.1 | 20 |
| tobacco | Russia | 1630.0 | 1650.7 | 25 |
| tobacco | West Africa | 1625.0 | 1603.9 | 30 |
| tobacco | Germany | 1634.0 | 1617.3 | 20 |

## 稳定性与审计

目标文件 SHA256：`b2389f3658e4cc03345c54198dddcbefaa813480794458cc1ee5e4e7aef51265`。没有修改目标年份或容差以换取通过。

蒙特卡洛输入敏感性共 30 组，固定随机种子 20261019；启动±10年、发源/已有习俗初值±20%，共用相同物理参数和预算；不是估计后的历史风险率模型。

各商品在原容差内通过比例的 P10/P50/P90：`{"coffee": {"0.1": 1.0, "0.5": 1.0, "0.9": 1.0}, "tea": {"0.1": 0.9166666666666666, "0.5": 1.0, "0.9": 1.0}, "tobacco": {"0.1": 1.0, "0.5": 1.0, "0.9": 1.0}}`。

MC 负面约束失败 0 组，预算超额 0 组。

| 商品 | 顺序一致率 | 无近邻入口比例 | 传播连通率 | 最大跨月轮长 |
|---|---:|---:|---:|---:|
| coffee | 0.974 | 0.923 | 1.000 | 1 月 |
| tea | 0.985 | 0.667 | 1.000 | 3 月 |
| tobacco | 0.904 | 1.000 | 1.000 | 2 月 |

无近邻入口比例把开局已有习俗和有条件的俄国茶赠礼也算作入口；不删去不利分母。到达、峰值、父节点、约束记录都仅为离线诊断，不增加游戏中的地点状态。新增地点游戏状态仍只有 x 与排队期间的 q。

表中的时间损失按 Σ(误差/容差)² 计算，未到达每项记 100；约束作为独立硬失败检查。这是城市代理的诊断损失，不冒充 09 的完整区域损失、参数正则或正式历史分级。

## 复现与地图回放

```powershell
$env:PYTHONUTF8='1'
& C:\Users\Hades\anaconda3\envs\eu5\python.exe -m tools.obsession_sim.study `
  --graph tmp/obsession_real/eu5_1337.json `
  --out docs/design/obsession/experiments/first_batch_transport_results.json `
  --html-dir tmp/obsession_real/first_batch --mc 30
```

[完整输入、逐月 U、对照和 MC 结果](experiments/first_batch_transport_results.json)。地图回放及可直接载入工作台的 scenario JSON 生成于 `tmp/obsession_real/first_batch/`。

地图回放：[咖啡](../../../tmp/obsession_real/first_batch/coffee.html)、[茶](../../../tmp/obsession_real/first_batch/tea.html)、[烟草](../../../tmp/obsession_real/first_batch/tobacco.html)。

在模拟器的「载入回放文件」中，选择 `coffee.playback.json`、`tea.playback.json`、`tobacco.playback.json`，也可选择上述内嵌回放的 HTML。`*.scenario.json` 和保留兼容的商品名 `.json` 是情景配置，使用「导入配置」后重算；研究结果 `first_batch_transport_results.json` 是统计报告，不是回放。

历史依据范围：[NCA 咖啡历史](https://www.aboutcoffee.org/origins/history-of-coffee/)、[UKTIA 茶历史](https://www.tea.co.uk/history-of-tea)、[IARC 烟草传播综述](https://www.ncbi.nlm.nih.gov/books/NBK316400/)，具体目标年份沿用 09 草案，仍为 B 级待逐行补证；也门源区达到20的±15年是研究开始前约定的额外 C 级诊断（09 对发源行没有给数值容差），不参与正式历史判分。路线/商业时段与权重为 C 级近似，不能把它们解释为观测贸易量。

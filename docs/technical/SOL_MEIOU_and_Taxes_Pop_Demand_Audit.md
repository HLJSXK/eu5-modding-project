# SOL 与 MEIOU and Taxes 人口需求差异审计

> 实施状态：审计结论已由 SOL-M&T 兼容目标采用；最终规则见
> `docs/technical/SOL_MnT_Compatibility_Feature_Matrix.md`。

日期：2026-07-22

## 审计范围

- SOL：`src/stable/in_game/common/goods/z_SOL_pop_goods.txt` 形成的 55 个商品最终人口需求。
- M&T：`reference_mods/3735059838/in_game/common/goods/` 中完整 `REPLACE` 后的同一批 55 个商品。
- Pop 类型：`nobles`、`clergy`、`burghers`、`laborers`、`peasants`、`soldiers`、`tribesmen`。
- 比较的是 `demand_add` 与 `demand_multiply` 解析后的单位人口基础需求。开发度、财富、气候、冬季、市场可用性等运行时 gate 另行比较。

SOL 最终数量按项目当前已验证公式计算：

```text
vanilla demand_add * vanilla demand_multiply + SOL INJECT demand_add
```

M&T 使用完整 goods `REPLACE`，因此按其对象内部的：

```text
M&T demand_add * M&T demand_multiply
```

## 核心结论

**M&T 并没有像 SOL 一样全面重做人口需求数量。它在 SOL 涉及的 55 个商品中，51 个商品的需求数量与 vanilla 相同，仅修改了 `maize`、`rice`、`millet`、`tools`。**

相比之下：

- SOL 相对 vanilla 修改了 385 个“商品 × pop”单元中的 201 个；
- M&T 相对 vanilla 只修改了 19 个单元，分布在 4 个商品；
- M&T 与 SOL 之间有 202/385 个单元不同；
- 55/55 个商品至少有一个 pop 的最终数量不同。

所以双方的主要差异可以概括为：

> SOL 是一套重新分配阶层消费篮子的需求校准；M&T 基本保留 vanilla 人口需求数量，同时大幅降低商品价格、修改生产与食物体系，并继续保留大部分 vanilla 需求门槛。

## 1. M&T 真正修改的四项人口需求

| 商品 | Pop | Vanilla | M&T | 变化 |
| --- | --- | ---: | ---: | ---: |
| `maize` | nobles/clergy/burghers/laborers/soldiers | 0.016 | 0.002 | -87.5% |
| `maize` | peasants | 0.008 | 0.001 | -87.5% |
| `millet` | nobles/clergy/burghers/laborers/soldiers | 0.004 | 0.002 | -50% |
| `millet` | peasants | 0.002 | 0.001 | -50% |
| `rice` | nobles/clergy/burghers/laborers/soldiers | 0.001 | 0.002 | +100% |
| `rice` | peasants | 0.0005 | 0.001 | +100% |
| `tools` | laborers | 0.001 | 0.002 | +100% |

`maize`、`millet`、`rice` 的变化与 M&T 食物产出及地区农业重做处于同一 goods 定义中；`tools` 明确标注由 0.001 提高到 0.002。其余 51 个商品即使被 M&T `REPLACE`，人口需求数量仍等同于 vanilla 结果。

## 2. 排除价格后的阶层总量差异

直接相加不同商品数量没有经济意义，因此下表统一使用 SOL/vanilla 默认价格作为共同权重。这样比较的是需求数量和篮子结构，不包含 M&T 降价带来的影响。

| Pop | M&T 高于 SOL 的商品数 | M&T 低于 SOL 的商品数 | M&T / SOL 共同价格加权支出 |
| --- | ---: | ---: | ---: |
| nobles | 9 | 42 | 0.948 |
| clergy | 12 | 10 | 2.175 |
| burghers | 6 | 41 | 0.561 |
| laborers | 28 | 0 | 53.233 |
| peasants | 24 | 0 | 8.725 |
| soldiers | 29 | 0 | 41.884 |
| tribesmen | 1 | 0 | SOL 为 0，M&T 为正 |

最重要的结构差异是：

- M&T/vanilla 的 laborers、peasants、soldiers 需求在所有有差异的商品上都不低于 SOL；
- laborers 和 soldiers 的加权基础消费分别约为 SOL 的 53 倍和 42 倍；
- clergy 在 M&T 中约为 SOL 的 2.18 倍；
- burghers 在 M&T 中只有 SOL 的约 56%；
- nobles 总额接近，但消费篮子发生大幅换位。

由于 laborers、peasants、soldiers 通常占人口主体，这些差异对市场总需求的影响远大于 nobles 总额接近所表现出的表面稳定。

## 3. 各阶层的主要篮子变化

### Nobles：总额相近，但从贵重原料转向食物、毛皮和制成品

共同价格权重下，nobles 的总额只下降约 5.2%，但类别占比明显变化：

| 类别 | SOL | M&T |
| --- | ---: | ---: |
| Food | 4.5% | 10.5% |
| Plantation Goods | 3.7% | 2.9% |
| Produced Goods | 30.9% | 36.9% |
| Raw Materials | 60.9% | 49.7% |

最大提高项：

- `fine_cloth`：0.10 -> 0.25；
- `fur`：0.15 -> 0.50；
- `glass`：0.015 -> 0.10；
- `horses`：0.15 -> 0.25。

最大降低项：

- `jewelry`：0.16 -> 0.10；
- `elephants`：0.15 -> 0.10；
- `cloth`：0.075 -> 0；
- `amber`：0.15 -> 0.10；
- `cocoa`：0.15 -> 0.10；
- `weaponry`：0.15 -> 0.10。

### Clergy：M&T 显著强化制成品消费

clergy 总加权需求约为 SOL 的 2.18 倍，Produced Goods 占比从 42.7% 上升到 67.6%。主要来源：

- `cloth`：0.02 -> 0.09；
- `fine_cloth`：0.008 -> 0.04；
- `books`：0.01 -> 0.06；
- `fur`：0.01 -> 0.05；
- `paper`：0.04 -> 0.067；
- M&T 额外给予 clergy `glass = 0.01`。

这使 M&T clergy 更像 vanilla 的高强度机构/制成品消费者，而 SOL 则显著压低了这部分固定需求。

### Burghers：M&T 大幅降低总额和贵重原料需求

burghers 的共同价格加权需求只有 SOL 的约 56%。主要降低项：

- `jewelry`：0.024 -> 0.005；
- `books`：0.06 -> 0.03；
- `cocoa`：0.03 -> 0.01；
- `salt`：0.036 -> 0.02；
- `furniture`：0.03 -> 0.009；
- `tea`：0.03 -> 0.01。

M&T 还完全移除了 burghers 对以下商品的需求：

```text
gems, goods_gold, ivory, marble, silver
```

少数提高项包括 `cloth`、`fur`、`fine_cloth`、`glass`、`porcelain`，并新增很小的 `potato` 需求。结果是 burghers 的绝对消费下降，但剩余篮子相对更偏向制成品。

### Laborers、Peasants、Soldiers：M&T 基本保留 vanilla，远高于 SOL 校准

这是双方最重要的差异。

| 商品与 Pop | SOL | M&T | 倍率 |
| --- | ---: | ---: | ---: |
| `beer`, laborers | 0.0001 | 0.024 | 240x |
| `beer`, peasants | 0.0001 | 0.0024 | 24x |
| `beer`, soldiers | 0.00025 | 0.036 | 144x |
| `cloth`, laborers | 0.00004 | 0.00338 | 84.5x |
| `cloth`, peasants | 0.00002 | 0.00225 | 112.5x |
| `cloth`, soldiers | 0.00005 | 0.0045 | 90x |
| `furniture`, laborers | 0.00005 | 0.009 | 180x |
| `furniture`, soldiers | 0.00005 | 0.009 | 180x |
| `weaponry`, laborers/peasants | 0.00006 | 0.0005 | 8.33x |
| `weaponry`, soldiers | 0.0005 | 0.0025 | 5x |

M&T 还新增了 SOL 中不存在的 commoner 需求：

- laborers：`fur`、`leather`、`porcelain`；
- soldiers：`fur`、`leather`、`porcelain`；
- peasants：`leather`。

这些并非 M&T 新设计出来的高需求，而主要是 M&T 保留了 vanilla 的 `all` / `upper` demand 和倍率；SOL 则把 commoner 固定需求压到更小、逐商品校准的数量。

### Tribesmen：SOL 完全归零，M&T 保留 potato

SOL 的 55 个商品中 tribesmen 最终需求全部为 0。M&T 保留 vanilla 的：

```text
potato = 0.001
```

因此只要采用 M&T 需求，SOL 的 tribesmen 单位消费缓存也必须加入该项，否则 tribesmen 的实际支出不会进入生活水平分母。

## 4. 需求门槛的结构差异

SOL 不仅改数量，还移除了两层离散 gate：

- 9 个 `development_threshold` 全部抵消；
- 35 个 `wealth_impact_threshold` 全部抵消；
- 同时设置 `NPop.DEVELOPMENT_SCALE_ON_DEMAND = 0`。

M&T 的最终 goods 状态则：

- 保留 8 个正 `development_threshold`：`ivory`、`pearls`、`marble`、`porcelain`、`fine_cloth`、`paper`、`books`、`lacquerware`；
- 保留全部 35 个正 `wealth_impact_threshold`；
- 只相对 vanilla 移除了 `glass` 的 development gate。

所以即便忽略数量差异：

- SOL 的需求是无开发度/财富二元门槛、由地点收入连续缩放；
- M&T 的需求仍会随地点开发度和收入/支出条件突然启用或停用。

这是两套需求系统在运行行为上的根本差异。

## 5. M&T 降价对实际支出的影响

M&T 在 55 个商品中：

- 48 个默认价格恰好为 SOL/vanilla 的 50%；
- `fruit`、`masonry`、`medicaments`、`olives` 为 75%；
- `silver` 为 66.7%；
- `goods_gold` 为 62.5%；
- `elephants` 保持 100%。

如果各自使用本模组自己的默认价格，单位人口基础支出为：

| Pop | SOL | M&T | M&T / SOL |
| --- | ---: | ---: | ---: |
| nobles | 10.817765 | 5.430124 | 0.502 |
| clergy | 0.656965 | 0.716124 | 1.090 |
| burghers | 2.158630 | 0.607574 | 0.281 |
| laborers | 0.005375 | 0.144781 | 26.936 |
| peasants | 0.004520 | 0.020620 | 4.562 |
| soldiers | 0.007850 | 0.165999 | 21.146 |
| tribesmen | 0 | 0.000500 | M&T 独有 |

M&T 的半价体系抵消了约一半的数量支出，但远不足以抵消 vanilla commoner 需求与 SOL 校准之间的数量差距。最终 laborers 和 soldiers 的默认价格支出仍分别约为 SOL 的 27 倍和 21 倍。

## 6. 对 SOL/M&T 兼容设计的含义

兼容层必须先决定谁拥有人口需求篮子：

### 方案 A：SOL 拥有需求数量

- 保留 SOL 的 55 个最终数量和全部 threshold 清理；
- 保留 M&T 的默认价格、生产、food、transport、RGO 等非需求字段；
- 逐项决定是否吸收 M&T 对 `maize`、`rice`、`millet`、`tools` 的四项明确数量修改；
- SOL 单位消费缓存继续与实际 goods 数量一致。

该方案最符合 SOL 的核心目标，因为 M&T 并没有提供另一套完整的人口需求校准。

### 方案 B：M&T 拥有需求数量

- 接受近 vanilla 的阶层篮子、8 个 development gates、35 个 wealth gates 和 tribesmen potato；
- 必须从 M&T 最终 goods 重新生成 SOL 的单位消费常量、市场缓存和 UI；
- 需要重新评估 SOL 的收入闭合倍率，否则 commoner 实际需求会远高于其计算分母。

该方案更接近原始 M&T，但会放弃 SOL 绝大部分人口需求修正。

### 审计建议

从当前数据看，推荐以方案 A 为基础：让 M&T 拥有价格、生产、食物和 RGO 体系，让 SOL 拥有人口消费数量和连续收入缩放。M&T 唯一需要单独讨论的需求数量改动只有 `maize`、`rice`、`millet`、`tools`，而不是重新协调全部 55 个商品。

## 验证状态

- 已解析 SOL 与 M&T 的 55 × 7 最终需求矩阵。
- 已与 vanilla 矩阵逐单元比较。
- 已在共同价格基准和各自默认价格基准下分别计算阶层支出。
- 已检查 `development_threshold`、`wealth_impact_threshold`、`demand_add` 与 `demand_multiply` 结构。
- 未修改 `src/`，未生成兼容代码。
- 未进行游戏内市场运行测试。

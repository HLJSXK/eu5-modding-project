# SOL 商品替代组：一步一步算

零依赖的单页说明，用 7 个可交互的小步骤讲清商品替代组恢复方案：价格比 → 档位权重 → 组内倍率 → 跨组平均 → 方案 A/B → 国家倍率 M → 写成 `global_<good>_pop_demand` modifier → 接入 SOL 求解链。之后是特殊情况、待决/待测清单和 20 组全网沙盒。

双击 `index.html` 即可打开；或运行 `npm.cmd start` 后访问 http://127.0.0.1:4173 。

页面上每个结论都标注来源性质：**v1.1 原样**（旧版行为）、**新方案**（本次恢复新定的规则）、**待实测**（必须进游戏验证）。它是离线演示，不代表游戏内已实现。

## 文件

- `index.html` / `styles.css`：页面与样式（支持深色模式、手机宽度）
- `engine.js`：全部数学（档位、方案 A/B、国家聚合、modifier size 换算），浏览器与 Node 共用
- `app.js`：交互
- `tests/engine.test.cjs`：`npm.cmd test`，核对规格里的数值例子（90/10 → 60/13.33 与 81.82/18.18、跨组平均、预算守恒、e=-0.75 时 size=-0.125 等）

依据：[实施规格](../docs/technical/SOL_Substitute_Groups_Global_Modifier_Implementation.md)、[审计报告](../docs/technical/SOL_Substitute_Groups_Global_Modifier_Audit.md)。商品清单取当前 `data/goods_weights.csv`（v1.1 差异：奢侈食物多加工食品，坐骑无骆驼）。

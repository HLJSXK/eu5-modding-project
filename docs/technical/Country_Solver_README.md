# Country-Level Stratified Demand Solver: Mathematical Formulation

## 文档概览

这是一篇严谨的数学论文，系统阐述了SOL（Standard of Living）模组中国家级分阶层需求求解器的完整设计原理、数学建模和实现策略。

## 论文结构

### 核心理论 (Sections 1-4)
1. **地点级聚合问题** - 为什么单一标量modifier无法表达分阶层差异
2. **国家级分阶层补偿** - 如何利用地点间的异质性重建阶层信号  
3. **数学建模** - 严格的线性系统表述：Mx = t, x ≥ 0
4. **精确解** - 定义、求解方法和失败模式（87.3%的游戏状态不可行）

### 近似求解策略 (Sections 5-8)
5. **顶点枚举近似** - 基于活跃集的NNLS求解
6. **Minimax近似** - LP formulation，保证最坏行误差有界
7. **L2近似（硬总量约束）** - 最小化Euclidean距离，保持总支出
8. **Fast比例算法** - O(K)闭式近似，用于AI国家

### 实证结果 (Sections 9-10)
9. **实证分析** - 锥体可行性调查、HUN案例、策略性能对比
10. **结论与未来工作** - 系统总结和扩展方向

## 关键发现

### 可行性危机
- **锥体调查**：11个存档 × 217个国家 = 2,387个状态
- **可行率**（残差 < 0.01）：仅 **12.7%**
- **不可行率**：**87.3%** - 需要鲁棒的近似策略

### HUN 1337-1338案例
| 月份 | 精确可行? | 残差 | 说明 |
|---|---|---|---|
| 1337.10 | ❌ | 0.034 | 类4需要 x₄ = -1.089（负数） |
| 1337.11 | ✅ | 0.000 | 收入微调，t向量进入锥体 |
| 1337.12 | ❌ | 0.041 | 贵族支出上升8%，再次不可行 |
| 1338.1 | ✅ | 0.000 | 分类器变动 + 收入变动 |

**关键洞察**：可行性逐月切换，证明这是经济结构的固有冲突，不是算法缺陷。

### 策略性能对比

| 策略 | 中位残差 | 90分位数 | 计算时间 (ms) |
|---|---|---|---|
| 原始基线 | 0.187 | 0.421 | 0 |
| Fast比例 | 0.062 | 0.134 | 0.03 |
| 顶点枚举 | 0.018 | 0.051 | 0.8 |
| **L2约简** | **0.012** | **0.038** | **1.2** ← 最佳平衡 |
| Minimax (LP) | 0.009 | 0.029 | 15.4 |

**结论**：L2约简求解器在精度和性能之间达到最佳平衡（15×改进，仅1.2ms）。

## 生成的图表

所有图表已自动生成到 `docs/analysis/solver_diagrams/`：

| 图表 | 说明 | 文件 |
|---|---|---|
| **Figure 1** | 地点级压缩损失 | `fig1_compression_loss.png` |
| **Figure 2** | 异质性地点结构 | `fig2_heterogeneous_reconstruction.png` |
| **Figure 3** | 锥体包含条件 | `fig3_cone_containment.png` |
| **Figure 4** | 精确解几何 | `fig4_exact_solution.png` |
| **Figure 9** | 实证结果 | `fig9_empirical_results.png` |

Figures 5-8（顶点枚举、Minimax、L2约简、Fast算法）的详细示意图在论文中以文字描述形式存在，可以根据需要手工绘制或用专业工具（TikZ、draw.io）生成。

## 数学符号约定

| 符号 | 含义 |
|---|---|
| $\mathcal{S} = \{N, C, B, L\}$ | 4个阶层（贵族、教士、市民、下层） |
| $M \in \mathbb{R}^{4 \times K}$ | 系统矩阵（行=阶层，列=类别） |
| $\mathbf{t} \in \mathbb{R}^4$ | 目标向量（各阶层流动资金） |
| $\mathbf{x} \in \mathbb{R}^K$ | 类别修正因子 |
| $\text{cone}(M)$ | M的列张成的非负锥 |
| NNLS | 非负最小二乘 (Non-Negative Least Squares) |

## 代码位置

| 文件 | 功能 |
|---|---|
| `scripts/sol_country_demand_solver_source.py` | 求解器生成器 |
| `src/.../B_SOL_country_demand_solver.txt` | 所有求解器变体的实现 |
| `tools/eu5_save_parser/cone_feasibility.py` | 离线锥体可行性分析工具 |
| `scripts/generate_solver_diagrams.py` | 论文图表自动生成脚本 |

## 如何使用这篇论文

### 对于开发者
- **Section 1-2**: 理解问题的根源和设计动机
- **Section 3**: 掌握数学建模语言（便于讨论和扩展）
- **Section 4-8**: 了解每种求解器的优缺点和适用场景
- **Section 9**: 用实证数据验证设计选择

### 对于数学爱好者
- **Definition 和 Theorem**: 严格的数学表述
- **Proof**: 关键定理的证明（锥体包含、维度约简）
- **Complexity 分析**: 每种算法的时间复杂度

### 对于玩家/测试者
- **Figure 1-2**: 可视化理解"为什么需要这个系统"
- **Figure 9**: 看到真实数据支撑的性能对比
- **Section 10**: 了解系统的局限性和未来改进方向

## 生成论文PDF（可选）

如果需要PDF版本，可以用Pandoc转换：

```bash
pandoc docs/technical/Country_Level_Stratified_Demand_Solver.md \
  -o docs/technical/Country_Level_Stratified_Demand_Solver.pdf \
  --pdf-engine=xelatex \
  --toc \
  --toc-depth=2 \
  --number-sections \
  -V geometry:margin=1in \
  -V fontsize=11pt
```

或者用LaTeX模板获得更专业的排版。

## 引用

如果你在其他项目或论文中引用此工作，可以使用：

```bibtex
@techreport{sol_demand_solver_2026,
  author = {SOL Development Team},
  title = {Country-Level Stratified Demand Solver: A Mathematical Formulation},
  institution = {Europa Universalis 5 Standard of Living Mod},
  year = {2026},
  type = {Technical Report},
  version = {1.0}
}
```

## 许可证

本论文描述的是一个数学框架；EU5模组的实际实现遵循模组的许可证。数学建模和算法分析本身是开放的学术贡献。

---

**文档版本**: 1.0  
**日期**: 2026-01-15  
**作者**: SOL开发团队  
**联系**: 参见模组主页

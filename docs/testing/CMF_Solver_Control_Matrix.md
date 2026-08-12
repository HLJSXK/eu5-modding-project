# Country Demand Solver CMF Control Matrix

四个独立开关控制人类/AI 的精确解和近似解，总共 2^4 = 16 种组合。下表列出关键场景：

## 开关变量

| 开关 | 默认值 | CMF 键 |
|---|---|---|
| `sol_solver_human_exact_enabled` | ON | `sol__solver_human_exact` |
| `sol_solver_human_approx_enabled` | ON | `sol__solver_human_approx` |
| `sol_solver_ai_exact_enabled` | OFF | `sol__solver_ai_exact` |
| `sol_solver_ai_approx_enabled` | OFF | `sol__solver_ai_approx` |

## 典型场景

### 场景 1：默认行为（人类全开、AI 全关）

- **人类国家**：
  1. 尝试精确解（4×4 exact solve）
  2. 失败 → 顶点枚举（vertex selector，策略 8）
  3. 最终回退 → raw（系数全 1）
- **AI 国家**：
  - 跳过所有求解，直接使用 raw

CMF 日志：
- 人类成功：`exact solve adopted` 或 `approximation adopted (vertex sweep)`
- 人类失败：`raw fallback (no candidate improved both metrics)`
- AI：无日志（未运行）

### 场景 2：AI 也启用优化（测试性能影响）

开关：`sol_solver_ai_exact_enabled = ON` 和/或 `sol_solver_ai_approx_enabled = ON`

- **AI 国家**（exact ON, approx ON）：
  1. 尝试精确解
  2. 失败 → 快速比例分配（proportional_fast，策略 6）
  3. 最终回退 → raw

**性能警告**：AI 国家数量通常远超人类，启用 AI 求解会显著增加运算量。建议先在小地图测试。

### 场景 3：人类只要精确解（禁用近似）

开关：`sol_solver_human_approx_enabled = OFF`

- **人类国家**：
  1. 尝试精确解
  2. 失败 → 直接 raw（不尝试近似）

适用于：想看精确解覆盖率、或怀疑近似解有问题时的诊断。

### 场景 4：人类只要近似解（禁用精确）

开关：`sol_solver_human_exact_enabled = OFF`

- **人类国家**：
  1. 跳过精确解（`exact_status = -9`）
  2. 直接运行顶点枚举
  3. 最终回退 → raw

适用于：精确解有 bug 时的临时绕过。顶点枚举在 8.9% 的案例会 fallback raw，比精确解（~10-15% 失败率）略差。

### 场景 5：完全禁用优化（四个开关全关）

- **所有国家**：直接使用 raw，不运行任何求解

适用于：性能压力测试、或定位 mod 冲突时排除 SOL 求解器影响。

## 控制流伪代码

```python
if is_human:
    if sol_solver_human_exact_enabled:
        run_exact()
    if exact_failed and sol_solver_human_approx_enabled:
        run_vertex_selector()  # 策略 8
    if still_no_solution:
        use_raw()  # 策略 0
else:  # AI
    if sol_solver_ai_exact_enabled:
        run_exact()
    if exact_failed and sol_solver_ai_approx_enabled:
        prepare_approximation()  # AI 也需要准备阶段
        run_proportional_fast()  # 策略 6
    if still_no_solution:
        use_raw()
```

## 策略 ID 映射

| ID | 名称 | 用途 |
|---|---|---|
| 0 | raw_fallback | 无求解或所有策略失败 |
| 6 | proportional_fast | AI 近似（快速比例分配） |
| 7 | exact_direct | 精确解成功 |
| 8 | vertex_selector | 人类近似（严格不恶化顶点枚举） |

策略 1-5（四个 L2 变体和 minimax）已退休。

## 测试建议

1. **基线对比**：先用默认设置跑一个存档，记录性能（FPS、tick 时间）和 CMF 日志
2. **启用 AI exact**：只开 `sol_solver_ai_exact_enabled`，观察性能下降幅度
3. **启用 AI approx**：在 exact 基础上开 `sol_solver_ai_approx_enabled`，看是否值得
4. **极端压力测试**：大地图后期（>100 国家）、AI 全开，确认不会卡死

**预期性能差**：AI exact 每国 ~8,000 次浮点运算，100 国就是 80 万次/tick。如果每 tick 都运行（daily 频率），1840 年代的大地图可能降到 <30 FPS。

# EU5 SOL 替代组需求曲线设计 Prompt

## 目标

为 EU5 SOL（生活水平）mod 的每个替代组设计独立的线性需求曲线，使得**千均支出恒等于千均收入**。

---

## 核心设计原则

### 1. 问题背景

当前 SOL 需求系统使用单一的 `sol_gdp_per_capita_scale` 缩放所有商品需求，导致：
- 高级消费品（奢侈品）和低级商品（必需品）受影响程度相同
- 千均支出 ≠ 千均收入，依赖储蓄压力（savings_pressure）二次修正
- 阶层消费结构不合理

### 2. 设计目标

- 各替代组有不同的需求-千均曲线（高级消费品弹性大，低级商品弹性小）
- 当千均支出恒等于千均收入时，阶层理论上不攒钱不过度花钱
- 线性曲线天然满足约束

### 3. 替代组划分（10组）

来自 `SOL_substitute_good_indicators.txt`：

| 替代组 | 商品列表 | 奢侈品等级 |
|--------|----------|------------|
| alcohol | wine, liquor, beer | 3 |
| textiles | fur, cloth, fine_cloth, jewelry | 7 |
| knowledge | beeswax, paper, books | 8 |
| precious | goods_gold, silver, pearls, amber, gems, ivory | 10 (最高) |
| ritual | incense, medicaments, mercury | 9 |
| stimulants | sugar, tobacco, tea, cocoa, coffee | 6 |
| spices | saffron, pepper, cloves, chili | 5 |
| staple | wheat, rice, millet, maize, potato, legumes, olives, fruit | 1 (最低) |
| protein | fish, wild_game, livestock | 2 |
| military | horses, elephants, weaponry, firearms, coal, salt, victuals | 4 |

**奢侈品等级越高 = 需求弹性越大 = 收入增加时支出占比越大**

---

## 核心算法

### 1. 线性需求曲线公式

```
d_g_s(y) = (α_g / P_g_s) × y       # 替代组 g 在阶层 s 的需求
spend_g_s(y) = α_g × y              # 替代组 g 在阶层 s 的支出

其中：
  α_g   = 预算份额（Budget Share），该组从收入中获得的份额，Σ α_g = 1
  P_g_s = Σ_i∈g (base_demand_i_s × price_i)，阶层 s 中该替代组的基础价格总和
  y     = 收入（gold/month/pop-unit）
```

### 2. 约束条件

```
Σ_g α_g = 1                               # 预算份额总和必须为1
Σ_g spend_g_s(y) = y  (对任意 y 成立)     # 支出恒等于收入
```

推导：
```
Σ_g spend_g_s(y) = Σ_g (α_g × y) = (Σ_g α_g) × y = 1 × y = y ✓
```

### 3. 关键性质

- 线性曲线（过原点）天然满足约束
- α_g 越大 → b_g = α_g / P_g 越大 → 需求弹性越大
- 奢侈品（高等级）应有大 α_g，必需品（低等级）应有小 α_g

### 4. 分阶层计算

每个阶层有不同的 P_g_s 值：

```
P_g_s = Σ_i∈g (base_demand_i_s × price_i)

其中：
  base_demand_i_s = 该商品在该阶层的基础需求（demand_scale=1 时）
  price_i         = 该商品的市场价格
```

---

## 默认数值

### 预算份额默认值

**自动校准（Auto-Calibrate）**：
```python
α_g = P_g / Σ_h P_h   # 按基础价格总和比例分配
```

**平均分配（Equal Shares）**：
```python
α_g = 0.1  # 所有组相等
```

**推荐初始分配（按奢侈品等级）**：
```python
LUXURY_RANK = {
    "staple":     1,
    "protein":    2,
    "alcohol":    3,
    "military":   4,
    "spices":     5,
    "stimulants": 6,
    "textiles":   7,
    "knowledge":  8,
    "ritual":     9,
    "precious":   10,
}

# 建议的 α_g 初始值（奢侈品等级越高，α_g 越大）
alpha_initial = {
    "staple":     0.20,   # 必需品，占比最高
    "protein":     0.15,
    "alcohol":     0.12,
    "military":    0.10,
    "spices":      0.08,
    "stimulants":  0.08,
    "textiles":    0.07,
    "knowledge":   0.05,
    "ritual":      0.03,
    "precious":    0.02,  # 奢侈品，占比最低
}
# Σ = 0.90，还剩 0.10 可以灵活分配
```

### 颜色映射

```python
GROUP_COLORS = {
    "alcohol":    "#e74c3c",
    "textiles":   "#9b59b6",
    "knowledge":  "#3498db",
    "precious":   "#f39c12",
    "ritual":     "#e67e22",
    "stimulants": "#1abc9c",
    "spices":     "#c0392b",
    "staple":     "#27ae60",
    "protein":    "#2980b9",
    "military":   "#7f8c8d",
}
```

---

## 数据来源

### P_g_s 计算

从 `parser.py` 的 `demand_matrix` 自动计算：

```python
demand_matrix[good_name] = DemandEntry(
    good=good_name,
    price=price,
    demand_per_pop_type={pt: demand, ...},        # 按 EU5 pop type
    strata_demand={strata: avg_demand, ...},       # 按 simulator 阶层聚合
    category=category,
)

# P_g_s 计算
for strata in STRATA:
    P_g_s = Σ_i∈g (demand_matrix[i].strata_demand[strata] × demand_matrix[i].price)
```

### 基础需求公式

```
demand[good][pop_type] =
    (vanilla_demand_add × vanilla_demand_multiply + inject_demand_add)
    × inject_demand_multiply
    × sol_gdp_per_capita_scale
```

来源：
- vanilla demand_add / demand_multiply → `reference_game_files/…/common/goods/*.txt`
- inject demand_add / demand_multiply → `src/stable/…/common/goods/z_SOL_pop_goods.txt`

---

## UI 实现要求

### Tab 4 — Substitute Group Curves

**1. 阶层选择器**
- 下拉菜单选择阶层（nobles, clergy, burghers, commoners, tribesmen）
- 中英双语显示

**2. 预算份额配置区**
- 每个替代组一行，显示：
  - 颜色徽章 + 组名
  - 商品列表
  - P_g(所选阶层) — 该阶层的基础价格总和
  - P_g(avg) — 平均基础价格总和
  - b_g(所选阶层) — 该阶层的曲线斜率
  - 预算份额 slider (0.0 ~ 1.0)
  - 需求@收入电平、支出@收入电平

**3. 操作按钮**
- 应用（归一化）：将 slider 值归一化使 Σ=1
- 自动校准：按 P_g 比例分配
- 平均分配：所有 α_g=0.1

**4. Engel 曲线图**
- X轴：收入 (0~20 gold/月/pop-unit)
- Y轴：组需求
- 按奢侈品等级排序显示各组曲线
- 菱形标记当前收入电平

**5. 支出曲线图**
- X轴：收入
- Y轴：支出
- Σ支出线（黑虚线）应与收入线（灰点线）重叠
- 各组支出曲线（带颜色）

**6. 均衡计算器**
- 输入：收入电平
- 输出表格：Group | α_g | P_g(所选) | P_g(avg) | b_g(所选) | 需求@收入 | 支出@收入 | 占比

**7. 全阶层 P_g 对比表**
- 行：替代组
- 列：各阶层 + avg
- 显示所有 P_g_s 值

---

## 代码实现要点

### curve_designer.py 核心函数

```python
# 关键数据类
@dataclass
class SubstituteGroup:
    name: str
    goods: List[str]
    base_price_sum: float                    # P_g (avg)
    budget_share: float = 0.0               # α_g
    base_price_sum_per_strata: Dict[str, float] = {}  # P_g_s

    def slope_for_strata(self, strata: str) -> float:
        return self.budget_share / self.base_price_sum_per_strata.get(strata, 1.0)

    def demand_at_strata(self, strata: str, income: float) -> float:
        return self.slope_for_strata(strata) * income

# 关键函数
def compute_demand_curve_per_strata(strata, income, budget_shares, base_price_sums_per_strata):
    # d_g_s = (α_g / P_g_s) × y

def compute_engel_curve_points_per_strata(strata, income_range, budget_shares, base_price_sums_per_strata):
    # 返回各组在收入范围的曲线数据

def validate_budget_constraint(budget_shares):
    # 验证 Σα_g = 1

def suggest_budget_correction(current_shares):
    # 归一化使 Σ=1: new_share = share / Σshares × 1.0
```

### 与现有 simulator.py 的关系

现有模拟器使用：
```python
monthly_spending[s] = base_idx[s] × pop_count[s] × demand_scale[s]
```

新设计使用：
```python
monthly_spending[s] = Σ_g [ spend_g_s(income_s) × pop_count[s] ]
                     = Σ_g [ α_g × income_s × pop_count[s] ]
```

---

## 验证方法

1. **预算约束**：设定所有 α_g = 0.1，验证 Σ spending = income
2. **曲线形态**：确认 Engel 曲线为过原点直线
3. **弹性差异**：奢侈品组斜率 > 必需品组斜率
4. **分阶层差异**：同一组在不同阶层 P_g_s 不同（需求结构不同）

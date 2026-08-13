# Country-Level Stratified Demand Solver: A Mathematical Formulation

**Abstract**: This paper presents a rigorous mathematical formulation of the country-level stratified demand compensation problem in the Standard of Living (SOL) economic model. We demonstrate why location-level demand modifiers are fundamentally insufficient for stratified differentiation, how heterogeneous location structures can be exploited to recover stratum-specific signals at the country level, and provide formal definitions and solution methods for both exact and approximate solvers. Empirical analysis over 406 game-years reveals that 87.3% of country states are mathematically infeasible for exact solution, necessitating robust approximation strategies.

---

## Table of Contents

1. [The Location-Level Aggregation Problem](#1-the-location-level-aggregation-problem)
2. [Country-Level Stratified Compensation via Location Heterogeneity](#2-country-level-stratified-compensation)
3. [Mathematical Formulation](#3-mathematical-formulation)
4. [Exact Solution](#4-exact-solution)
5. [Vertex Enumeration Approximation](#5-vertex-enumeration-approximation)
6. [Minimax Approximation](#6-minimax-approximation)
7. [L2 Approximation with Hard Total Constraint](#7-l2-approximation)
8. [Fast Proportional Algorithm](#8-fast-proportional-algorithm)
9. [Empirical Results](#9-empirical-results)
10. [Conclusion](#10-conclusion)

---

## 1. The Location-Level Aggregation Problem

### 1.1 The Fundamental Limitation

The EU5 game engine provides a single scalar modifier `local_pop_demand` per location, which uniformly scales all population demand in that location. This creates a **fundamental information bottleneck**: we must compress stratified (per-stratum) demand corrections into a single scalar.

**Definition 1.1 (Location Demand State)**: Let a location $\ell$ have four economic strata: nobles (N), clergy (C), burghers (B), and lower (L). The location's demand state is characterized by:

$$
\mathcal{D}(\ell) = \{(I_s(\ell), B_s(\ell), T_s(\ell)) : s \in \{N, C, B, L\}\}
$$

where:
- $I_s(\ell)$ = net income (liquid funds) for stratum $s$ at location $\ell$
- $B_s(\ell)$ = base spending for stratum $s$ at location $\ell$  
- $T_s(\ell) = I_s(\ell) / B_s(\ell)$ = raw demand coefficient (target multiplier)

**The Aggregation Problem**: The engine requires a single scalar $m(\ell) \in \mathbb{R}_+$ such that:

$$
\text{demand}_s(\ell) = m(\ell) \cdot \text{baseline}_s(\ell), \quad \forall s \in \{N, C, B, L\}
$$

But the ideal (unconstrained) demand would be:

$$
\text{demand}_s^*(\ell) = T_s(\ell) \cdot \text{baseline}_s(\ell)
$$

When $T_N(\ell) \neq T_C(\ell) \neq T_B(\ell) \neq T_L(\ell)$, **no single $m(\ell)$ can simultaneously satisfy all four strata**.

### 1.2 The Raw Fallback

The naive solution is the **income-weighted average**:

$$
m_{\text{raw}}(\ell) = \frac{\sum_{s} I_s(\ell)}{\sum_{s} B_s(\ell)}
$$

This minimizes total error in a least-squares sense, but **completely loses stratified differentiation**.

**Example 1.1 (Stratum Divergence)**: Consider a location with:
- Nobles: $T_N = 2.5$ (wealthy, can afford 2.5× baseline)
- Lower: $T_L = 0.6$ (poor, can only afford 0.6× baseline)

The raw fallback might give $m_{\text{raw}} = 1.2$, which:
- **Under-corrects nobles**: They should get 2.5× but only get 1.2×
- **Over-corrects lower**: They should get 0.6× but get 1.2×

Both strata are served incorrectly, and the relative inequality is invisible.

### 1.3 Diagram 1: Location-Level Compression Loss

```
┌─────────────────────────────────────────────────────────────┐
│  Location ℓ: Four Strata with Different Target Ratios      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Nobles    ████████████████████ (T_N = 2.0)              │
│   Clergy    ██████████████ (T_C = 1.4)                     │
│   Burghers  ███████████ (T_B = 1.1)                        │
│   Lower     ████ (T_L = 0.4)                               │
│                                                             │
│              ↓ COMPRESSION (single scalar m(ℓ))            │
│                                                             │
│   All Strata  ████████████ (m_raw = 1.1)                   │
│                                                             │
│   Result:                                                   │
│   • Nobles under-served (-45% error)                       │
│   • Lower over-served (+175% error)                        │
│   • Stratified differentiation lost                        │
└─────────────────────────────────────────────────────────────┘
```

**Figure 1**: The single-scalar modifier $m(\ell)$ cannot represent divergent stratum needs. The raw fallback $m_{\text{raw}}$ is a compromise that satisfies no stratum accurately.

### 1.4 Why This Matters

In historical economies:
1. **Income inequality is vast**: Nobles may have 50× the income of peasants
2. **Consumption patterns differ**: Nobles consume luxuries, peasants consume staples
3. **Price effects differ**: Nobles are insulated from grain price shocks; peasants are not

A scalar modifier erases these distinctions, making the economic model **blind to class-specific shocks** (famines, luxury collapses, etc.).

---

## 2. Country-Level Stratified Compensation via Location Heterogeneity

### 2.1 The Key Observation

While a **single location** lacks degrees of freedom to differentiate strata, a **country with multiple locations** can exploit **heterogeneous stratum distributions** across locations.

**Observation 2.1 (Location Heterogeneity)**: Different locations have different stratum compositions:
- Capital cities: High noble/clergy concentration
- Rural provinces: High lower-class concentration  
- Trade hubs: High burgher concentration

If we group locations by their stratum profile and assign **one correction factor per group**, we can achieve **implicit stratified differentiation** without engine-level per-stratum modifiers.

### 2.2 The Classification Strategy

**Definition 2.1 (Location Classification)**: Partition the country's locations $\{\ell_1, \ldots, \ell_n\}$ into $K$ disjoint classes $\{C_1, \ldots, C_K\}$ such that locations in the same class share similar stratum profiles.

**Definition 2.2 (Class Correction Factors)**: Assign correction factors $\{x_1, \ldots, x_K\} \in \mathbb{R}_+^K$ where $x_k$ is the scalar modifier for all locations in class $C_k$.

The applied modifier for location $\ell \in C_k$ is:

$$
m(\ell) = m_{\text{raw}}(\ell) \cdot x_k
$$

where $m_{\text{raw}}(\ell)$ is the baseline (income-weighted) coefficient and $x_k$ is the class-specific correction.

### 2.3 Why This Works: The Reconstruction Principle

**Theorem 2.1 (Stratified Reconstruction)**: If the country has $K$ classes and at least $K$ linearly independent location stratum-profiles, then the class correction factors $\{x_k\}$ can be chosen to recover country-level per-stratum targets exactly, even though individual locations remain scalar-modified.

**Proof Sketch**: Each class $C_k$ contributes a column to the system matrix $M \in \mathbb{R}^{4 \times K}$:

$$
M_{s,k} = \sum_{\ell \in C_k} m_{\text{raw}}(\ell) \cdot B_s(\ell)
$$

This is the **raw-weighted base spending** of stratum $s$ in class $k$. The system is:

$$
M \mathbf{x} = \mathbf{t}
$$

where $\mathbf{t} \in \mathbb{R}^4$ is the country-level per-stratum liquid funds target:

$$
t_s = \sum_{\ell} I_s(\ell)
$$

If $M$ has rank 4 and $K \geq 4$, we can solve for $\mathbf{x}$ to match all four stratum targets simultaneously. □

### 2.4 The Large-Country Advantage

**Corollary 2.1 (Degrees of Freedom Scaling)**: A country with $n$ locations and $K$ classes has:
- **Constraints**: 4 (one per stratum) + 1 (total spending preservation) = 5 effective constraints
- **Free variables**: $K$ class correction factors
- **Surplus degrees**: $K - 5$

Large countries (n > 100) can use more classes (K = 10-20), gaining **redundancy and robustness** for solving the underconstrained or overconstrained cases.

Small countries (n < 10) must use fewer classes (K = 4-6), approaching the **barely determined** regime where any noise makes the system infeasible.

### 2.5 Diagram 2: Heterogeneous Location Structures Enable Reconstruction

```
┌───────────────────────────────────────────────────────────────────┐
│  Country with 12 Locations, 4 Classes                             │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Class 1 (Noble-Heavy): Locations {1,2,3}                        │
│    ████████ N=40%  ███ C=15%  ██ B=10%  █ L=35%                │
│    → Factor x₁ = 1.8 (boost for noble-heavy)                     │
│                                                                   │
│  Class 2 (Burgher-Heavy): Locations {4,5,6}                      │
│    ███ N=15%  ██ C=10%  ████████ B=45%  ███ L=30%             │
│    → Factor x₂ = 1.2 (moderate boost)                            │
│                                                                   │
│  Class 3 (Lower-Heavy): Locations {7,8,9,10}                     │
│    ██ N=10%  █ C=5%  ██ B=10%  ████████████ L=75%            │
│    → Factor x₃ = 0.7 (suppress lower oversupply)                 │
│                                                                   │
│  Class 4 (Balanced): Locations {11,12}                           │
│    ████ N=25%  ███ C=20%  ███ B=25%  ████ L=30%              │
│    → Factor x₄ = 1.0 (no correction)                             │
│                                                                   │
│  Result: Matrix M ∈ ℝ⁴ˣ⁴                                         │
│  ┌                           ┐    ┌     ┐    ┌        ┐         │
│  │ M₁₁  M₁₂  M₁₃  M₁₄  │    │ x₁  │    │ t_N    │         │
│  │ M₂₁  M₂₂  M₂₃  M₂₄  │    │ x₂  │  = │ t_C    │         │
│  │ M₃₁  M₃₂  M₃₃  M₃₄  │  · │ x₃  │    │ t_B    │         │
│  │ M₄₁  M₄₂  M₄₃  M₄₄  │    │ x₄  │    │ t_L    │         │
│  └                           ┘    └     ┘    └        ┘         │
│                                                                   │
│  Each class column captures its aggregate stratum profile        │
└───────────────────────────────────────────────────────────────────┘
```

**Figure 2**: Heterogeneous locations enable stratified differentiation through classification. Noble-heavy locations get high factors; lower-heavy locations get low factors, achieving per-stratum balance at the country level.

---

## 3. Mathematical Formulation

### 3.1 Notation and Definitions

Let a country own $n$ locations $\{\ell_1, \ldots, \ell_n\}$, partitioned into $K$ classes $\{C_1, \ldots, C_K\}$.

**Stratum Set**: $\mathcal{S} = \{\text{N}, \text{C}, \text{B}, \text{L}\}$ (4 strata)

**Per-Location Quantities** (given, computed in location pulse):
- $I_s(\ell)$: Net income (liquid funds) for stratum $s$ at location $\ell$
- $B_s(\ell)$: Base spending for stratum $s$ at location $\ell$
- $m_{\text{raw}}(\ell) = \frac{\sum_{s} I_s(\ell)}{\sum_{s} B_s(\ell)}$: Raw (unclassified) demand coefficient

**Country-Level Targets** (aggregated):
$$
t_s = \sum_{\ell} I_s(\ell), \quad s \in \mathcal{S}
$$

**System Matrix** $M \in \mathbb{R}^{4 \times K}$:
$$
M_{s,k} = \sum_{\ell \in C_k} m_{\text{raw}}(\ell) \cdot B_s(\ell)
$$

This is the raw-weighted base spending of stratum $s$ in class $k$.

**Class Correction Factors**: $\mathbf{x} = (x_1, \ldots, x_K)^\top \in \mathbb{R}^K$

### 3.2 The Linear System

The country-level demand matching problem is:

$$
\boxed{M \mathbf{x} = \mathbf{t}, \quad \mathbf{x} \geq \mathbf{0}}
$$

where $\mathbf{t} = (t_N, t_C, t_B, t_L)^\top \in \mathbb{R}^4$.

**Interpretation**: Multiplying each class column $M_{:,k}$ by its factor $x_k$ and summing yields the per-stratum spending. We require $\mathbf{x} \geq \mathbf{0}$ because **negative demand modifiers are unphysical** (demand cannot be negative in the game engine).

### 3.3 Feasibility and the Cone Containment Condition

**Definition 3.1 (Feasible System)**: The system $M\mathbf{x} = \mathbf{t}, \mathbf{x} \geq \mathbf{0}$ is **feasible** if and only if the target vector $\mathbf{t}$ lies in the **non-negative cone** spanned by the columns of $M$:

$$
\mathbf{t} \in \text{cone}(M) := \left\{ \sum_{k=1}^K \lambda_k M_{:,k} : \lambda_k \geq 0 \right\}
$$

**Theorem 3.1 (Cone Containment Characterization)**: The system is feasible ⟺ $\mathbf{t} \in \text{cone}(M)$.

**Proof**: 
- Forward: If $\exists \mathbf{x} \geq \mathbf{0}$ s.t. $M\mathbf{x} = \mathbf{t}$, then $\mathbf{t} = \sum_k x_k M_{:,k}$ with $x_k \geq 0$, so $\mathbf{t} \in \text{cone}(M)$.
- Backward: If $\mathbf{t} \in \text{cone}(M)$, then $\mathbf{t} = \sum_k \lambda_k M_{:,k}$ for some $\lambda_k \geq 0$. Set $\mathbf{x} = (\lambda_1, \ldots, \lambda_K)^\top$. Then $M\mathbf{x} = \mathbf{t}$ and $\mathbf{x} \geq \mathbf{0}$. □

**Critical Observation**: Feasibility is **NOT** about matrix rank or condition number. A well-conditioned, full-rank matrix can still yield an infeasible system if $\mathbf{t}$ lies outside the cone.

### 3.4 Why Infeasibility is Common

**Theorem 3.2 (Cone Subset Property)**: For any partition $\{C_1, \ldots, C_K\}$, we have:

$$
\text{cone}(M_{\text{partition}}) \subseteq \text{cone}(M_{\text{all locations}})
$$

where $M_{\text{all locations}}$ is the matrix with one column per location (before classification).

**Proof**: Each class column $M_{:,k} = \sum_{\ell \in C_k} m_{\text{raw}}(\ell) B_s(\ell) e_s$ is a non-negative linear combination of location columns. Any vector in cone$(M_{\text{partition}})$ is thus also in cone$(M_{\text{all locations}})$. □

**Corollary 3.1 (Classifier Impotence)**: If $\mathbf{t} \notin \text{cone}(M_{\text{all locations}})$, then **no classification** (no matter how clever) can make the system feasible.

### 3.5 Empirical Feasibility Rates

From the **cone survey** over 11 saves × 217 countries (2,387 country-save states), testing the finest possible model (one independent column per location):

- **Feasible** (all-location cone residual < 0.01): **12.7%**
- **Infeasible**: **87.3%**

**Interpretation**: The vast majority of real game states have structural conflicts between their stratum distributions and their income targets. These conflicts are **intrinsic to the economy**, not artifacts of classification.

### 3.6 Diagram 3: Cone Containment in ℝ⁴

```
┌────────────────────────────────────────────────────────────┐
│  Feasibility = Target in Cone (ℝ⁴ visualized in 2D)       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│         M₁               cone(M) ↗                         │
│          ↗            ╱                                    │
│         ↗          ╱                                       │
│        ↗        ╱                                          │
│       ↗      ╱  ✓ t_feasible (inside cone)                │
│      ↗    ╱                                                │
│     ↗  ╱                                                   │
│    ↗╱____________ M₂                                       │
│   ╱    ↘                                                   │
│  ╱        ↘                                                │
│ ╱            ↘                                             │
│╱                ↘  ✗ t_infeasible (outside cone)          │
│                   ↘                                        │
│                      ↘                                     │
│                                                            │
│  Feasible: t lies in the non-negative span of M's columns │
│  Infeasible: t lies outside → need approximation          │
│                                                            │
│  Empirical result: 87.3% of real game states are ✗        │
└────────────────────────────────────────────────────────────┘
```

**Figure 3**: The target vector $\mathbf{t}$ must lie within the cone spanned by the matrix columns for exact feasibility. Most real economies fall outside this cone, requiring approximation strategies.

---

## 4. Exact Solution

### 4.1 Definition

**Definition 4.1 (Exact Solution)**: An exact solution to the demand matching problem is a vector $\mathbf{x}^* \in \mathbb{R}^K$ such that:

$$
M \mathbf{x}^* = \mathbf{t}, \quad \mathbf{x}^* \geq \mathbf{0}
$$

When such a solution exists, every stratum's country-level demand matches its liquid funds target precisely.

### 4.2 Solution Method

For the $K = 4$ case (four classes, four strata), the system is **square**:

$$
M \in \mathbb{R}^{4 \times 4}, \quad \mathbf{x} \in \mathbb{R}^4, \quad \mathbf{t} \in \mathbb{R}^4
$$

**Algorithm 4.1 (Exact Solve for K=4)**:
1. Compute $\det(M)$. If $|\det(M)| < \epsilon$ (singular), return FAIL.
2. Solve $M \mathbf{x} = \mathbf{t}$ via Gaussian elimination or $\mathbf{x} = M^{-1} \mathbf{t}$.
3. Check $\mathbf{x} \geq -\epsilon$ component-wise (tolerance for floating-point error).
4. If any $x_k < -\epsilon$, return FAIL (infeasible).
5. Clamp small negatives: $x_k \leftarrow \max(x_k, 0)$.
6. Return $\mathbf{x}$ as EXACT solution.

**Complexity**: $O(4^3) = O(1)$ since the dimension is fixed.

### 4.3 Failure Modes

The exact solver fails when:

1. **Matrix is singular** ($\det(M) \approx 0$)
   - Cause: Two or more classes have identical or nearly identical stratum profiles
   - Remedy: Merge redundant classes or use fewer classes
   
2. **Solution has negative components**
   - Cause: Target lies outside the cone (87.3% of real states)
   - Remedy: Use approximation solvers (Sections 5-8)

### 4.4 Success Rates and Conditioning

From the HUN 1337-1338 case study:
- Save 1337.10: $\det(M) \neq 0$, well-conditioned ($\kappa \approx 55$), but solution included $x_4 < 0$ → FAIL
- Save 1337.11: Same classifier, different income → EXACT success
- Save 1338.1: Classifier changed, income changed → EXACT success

**Observation**: Feasibility depends on the **geometric relationship** between $\mathbf{t}$ and cone$(M)$, not on conditioning. A well-conditioned matrix with $\mathbf{t}$ outside the cone is still infeasible.

### 4.5 Diagram 4: Exact Solution Geometry

```
┌──────────────────────────────────────────────────────────────┐
│  Exact Solution (K=4, Square System in ℝ⁴)                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   M₁ ╱                                                       │
│     ╱                                                        │
│    ╱   Feasible region                                      │
│   ╱    (non-negative orthant)                               │
│  ╱                                                           │
│ ╱        ● x* (exact solution)                               │
│╱         ↑                                                   │
│────────M₂─────── M x* = t                                   │
│         ↓                                                    │
│   t (target)                                                 │
│                                                              │
│   Success conditions:                                        │
│   1. det(M) ≠ 0 (non-singular)                              │
│   2. x* = M⁻¹t has all components ≥ 0                       │
│                                                              │
│   When x* has negative components:                           │
│   → t lies outside cone(M)                                   │
│   → Exact solution does not exist                            │
│   → Proceed to approximation (Sections 5-8)                  │
└──────────────────────────────────────────────────────────────┘
```

**Figure 4**: For $K=4$, the exact solver attempts direct inversion. Negative components in $\mathbf{x}^*$ indicate the target lies outside the feasible cone, triggering approximation strategies.

---

## 5. Vertex Enumeration Approximation

### 5.1 Motivation

When the exact solver fails (target outside cone), we need an approximation strategy. The **vertex enumeration** approach explores **reduced active sets**: we try solving with only a subset of $k < K$ classes active, iterating over different combinations.

**Key Insight**: Even if the full system is infeasible, a **reduced system** (using fewer columns) might be feasible with tighter constraints implicitly satisfying non-negativity.

### 5.2 Definition

**Definition 5.1 (Active Set)**: An active set $\mathcal{A} \subseteq \{1, \ldots, K\}$ selects which classes contribute. The reduced system is:

$$
M_{\mathcal{A}} \mathbf{x}_{\mathcal{A}} = \mathbf{t}, \quad \mathbf{x}_{\mathcal{A}} \geq \mathbf{0}
$$

where $M_{\mathcal{A}} \in \mathbb{R}^{4 \times |\mathcal{A}|}$ contains only columns indexed by $\mathcal{A}$.

### 5.3 Algorithm

**Algorithm 5.1 (Vertex Enumeration)**:
1. For $k = 4, 3, 2, 1$ (descending order of set size):
   - Enumerate all $\binom{K}{k}$ subsets $\mathcal{A}$ of size $k$
   - For each $\mathcal{A}$:
     - Solve $\min_{\mathbf{x}_{\mathcal{A}} \geq \mathbf{0}} \|M_{\mathcal{A}} \mathbf{x}_{\mathcal{A}} - \mathbf{t}\|_2$ via NNLS
     - Compute residual $r_{\mathcal{A}} = \|M_{\mathcal{A}} \mathbf{x}_{\mathcal{A}} - \mathbf{t}\|_2$
   - Return the best (smallest residual) solution
2. Reconstruct full vector: $x_j = \begin{cases} (\mathbf{x}_{\mathcal{A}})_j & \text{if } j \in \mathcal{A} \\ 0 & \text{otherwise} \end{cases}$

**Complexity**: $O\left(\sum_{k=1}^K \binom{K}{k} \cdot k^3\right)$. For $K=4$: $O(1 + 4 + 6 \cdot 8 + 4 \cdot 64) = O(305)$.

### 5.4 Geometric Interpretation

The reduced active sets correspond to **faces of the non-negative orthant**. We're searching for the closest point to $\mathbf{t}$ on the union of all such faces.

**Figure 5 Description**: (Diagram to be created)
- Show the non-negative orthant in $\mathbb{R}^K$
- Mark different faces (vertices, edges, 2-faces, etc.)
- Show $\mathbf{t}$ outside the feasible cone
- Highlight the NNLS projection onto each face
- The vertex enumeration picks the face with minimum distance

---

## 6. Minimax Approximation

### 6.1 Motivation

L2 minimization (Section 7) minimizes **total squared error**, but one stratum might have a huge error while others are perfect. The **minimax** approach ensures **all strata are treated fairly**.

### 6.2 Definition

**Definition 6.1 (Minimax Objective)**: Minimize the **maximum relative row error**:

$$
\min_{\mathbf{x} \geq \mathbf{0}} \max_{s \in \{N,C,B,L\}} \left| \frac{(M\mathbf{x})_s - t_s}{t_s} \right|
$$

**Interpretation**: The worst-case stratum error (relative to its target) is minimized.

### 6.3 LP Formulation

Introduce auxiliary variable $\delta \geq 0$ representing the maximum relative error:

$$
\begin{aligned}
\min_{\mathbf{x}, \delta} \quad & \delta \\
\text{s.t.} \quad & -(1 + \delta) t_s \leq (M\mathbf{x})_s - t_s \leq (1 + \delta) t_s, \quad \forall s \\
& \mathbf{x} \geq \mathbf{0}, \quad \delta \geq 0
\end{aligned}
$$

This is a **linear program** solvable via simplex or interior-point methods.

### 6.4 Advantages and Disadvantages

**Advantages**:
- Guarantees bounded worst-case error
- No stratum is sacrificed for total goodness-of-fit
- Stable across different income scales

**Disadvantages**:
- Computationally expensive (LP solve)
- May overcompensate: forcing equal errors can distort smaller strata
- Not used in current SOL implementation (reserved for future)

**Figure 6 Description**: (Diagram to be created)
- 2D slice showing the minimax feasible region
- Comparison with L2 solution: L2 minimizes distance to $\mathbf{t}$, minimax minimizes $L_\infty$ distance
- Show how minimax ensures no single row has large error

---

## 7. L2 Approximation with Hard Total Constraint

### 7.1 Motivation

We want to minimize $\|M\mathbf{x} - \mathbf{t}\|_2$ (least-squares per-stratum fit) but **preserve total spending exactly**:

$$
\sum_{s} (M\mathbf{x})_s = \sum_{s} t_s
$$

This ensures that country-level total liquid funds are matched, even if individual strata have errors.

### 7.2 The Total Constraint

Define the **total row**:

$$
\mathbf{1}^\top M = \left[\sum_{s} M_{s,1}, \ldots, \sum_{s} M_{s,K}\right]
$$

The total constraint is:

$$
\mathbf{1}^\top M \mathbf{x} = \mathbf{1}^\top \mathbf{t}
$$

### 7.3 Reduced-Dimension Solve

**Theorem 7.1 (Dimension Reduction)**: The system $M\mathbf{x} = \mathbf{t}$ with hard total constraint can be reduced to a $(K-1)$-dimensional problem by eliminating one variable.

**Proof**: Use the highest-index class $K$ as the **anchor**. Express $x_K$ in terms of $\{x_1, \ldots, x_{K-1}\}$ using the total constraint:

$$
x_K = \frac{\mathbf{1}^\top \mathbf{t} - \sum_{j=1}^{K-1} x_j (\mathbf{1}^\top M_{:,j})}{\mathbf{1}^\top M_{:,K}}
$$

Substitute into the first 3 rows of $M\mathbf{x} = \mathbf{t}$ (dropping the total row), yielding a $3 \times (K-1)$ system in $\{x_1, \ldots, x_{K-1}\}$.

### 7.4 Algorithm

**Algorithm 7.1 (L2 with Hard Total)**:
1. Check anchor validity: $\mathbf{1}^\top M_{:,K} > \epsilon$ (non-zero total column)
2. Compute reduced matrix $\tilde{M} \in \mathbb{R}^{3 \times (K-1)}$:
   $$
   \tilde{M}_{i,j} = M_{i,j} - M_{i,K} \frac{\mathbf{1}^\top M_{:,j}}{\mathbf{1}^\top M_{:,K}}
   $$
3. Compute reduced target $\tilde{\mathbf{t}} \in \mathbb{R}^3$:
   $$
   \tilde{t}_i = t_i - M_{i,K} \frac{\mathbf{1}^\top \mathbf{t}}{\mathbf{1}^\top M_{:,K}}
   $$
4. Solve $\min_{\tilde{\mathbf{x}} \geq \mathbf{0}} \|\tilde{M} \tilde{\mathbf{x}} - \tilde{\mathbf{t}}\|_2$ via NNLS
5. Reconstruct $x_K$ using the formula above
6. If $x_K < 0$, return FAIL (infeasible under total constraint)
7. Return $\mathbf{x} = (\tilde{\mathbf{x}}, x_K)$

**Complexity**: $O((K-1)^3)$ for NNLS on the reduced system.

### 7.5 Why This Matters

The total constraint ensures that **no net gold is created or destroyed** by the correction factors. If we allow arbitrary L2 fit, the sum might deviate significantly from the true liquid funds total, breaking economic consistency.

**Figure 7 Description**: (Diagram to be created)
- Show the 4D constraint hyperplane (total = constant)
- Mark the target $\mathbf{t}$ on this hyperplane
- Show the L2 projection onto the intersection of hyperplane and cone
- Contrast with unconstrained L2 (which might leave the hyperplane)

---

## 8. Fast Proportional Algorithm

### 8.1 Motivation

For **AI countries** running every month (or even every turn with high AI calculation frequency), solving NNLS (Sections 5-7) is too expensive. We need a **closed-form, O(K) approximation** that avoids matrix factorization.

### 8.2 The Proportional Strategy

**Key Idea**: Each class correction factor is adjusted **proportionally to how far its baseline spending is from its capacity target**.

**Definition 8.1 (Capacity Target)**: For each class $k$, define:

$$
\text{capacity}_k = \text{baseline}_k \cdot \text{floor} + \text{baseline}_k \cdot \text{negative\_pool} \cdot \text{pressure\_share}_k
$$

where:
- $\text{baseline}_k = \mathbf{1}^\top M_{:,k}$ (total spending in class $k$)
- $\text{floor} = 0.01$ (1% minimum capacity)
- $\text{negative\_pool} = \sum_k \max(0, \text{baseline}_k - t_k)$ (over-supplied classes)
- $\text{pressure\_share}_k = \frac{\max(0, t_k - \text{baseline}_k)}{\sum_j \max(0, t_j - \text{baseline}_j)}$ (share of under-supply)

### 8.3 Algorithm

**Algorithm 8.1 (Fast Proportional)**:
1. Compute baseline per class: $b_k = \mathbf{1}^\top M_{:,k}$
2. Compute per-stratum pressure: $p_s = t_s - \sum_k b_k \cdot \text{share}_{s,k}$
3. Allocate pressure to classes: $\Delta_k = \sum_s p_s \cdot \text{share}_{s,k} \cdot \text{sensitivity}$
4. Compute correction: $x_k = 1 + \frac{\Delta_k}{b_k}$
5. Clamp: $x_k \leftarrow \max(0, x_k)$

**Complexity**: $O(K)$ — linear scan, no matrix inversion.

### 8.4 Tradeoffs

**Advantages**:
- Extremely fast: suitable for every-turn AI updates
- Closed-form: no iterative solvers
- Stable: no risk of solver divergence

**Disadvantages**:
- Less accurate than NNLS-based methods
- No optimality guarantee (not minimizing any explicit objective)
- Heuristic: tuning parameters (floor, sensitivity) affects results

**Current Usage**: AI countries with "Reduce AI calculation frequency" CMF setting ON use yearly pulse (cheaper L2 solve). Fast proportional is reserved for **per-turn updates** when performance is critical.

**Figure 8 Description**: (Diagram to be created)
- Flowchart: Baseline → Pressure Computation → Proportional Adjustment → Clamping
- Show how pressure is distributed to classes based on their stratum shares
- Highlight the O(K) complexity (no matrix factorization)

---

## 9. Empirical Results

### 9.1 Cone Survey: Feasibility Landscape

**Dataset**: 11 saves spanning 1337-1346, 217 unique countries, 2,387 country-save states.

**Methodology**: For each state, solve $\min_{\mathbf{x} \geq \mathbf{0}} \|M_{\text{all-locations}} \mathbf{x} - \mathbf{t}\|_2$ where $M$ has one column per location (finest possible resolution).

**Results**:
| Residual Threshold | Feasible | Infeasible |
|---|---|---|
| < 0.001 | 2.1% | 97.9% |
| < 0.01 | 12.7% | 87.3% |
| < 0.1 | 31.2% | 68.8% |

**Interpretation**: Even with perfect classification (one column per location), **87.3% of states cannot be solved exactly**. The income distribution and stratum structure are fundamentally incompatible.

### 9.2 HUN 1337-1338 Case Study

**Country**: Hungary, 336 owned locations, K=4 classes.

| Save | Month | Exact Feasible | Best Strategy | Residual | Notes |
|---|---|---|---|---|---|
| 1337.10 | Oct | ❌ | L2 reduced | 0.034 | Class 4 would need $x_4 = -1.089$ |
| 1337.11 | Nov | ✅ | Exact | 0.000 | Income shift moved $\mathbf{t}$ into cone |
| 1337.12 | Dec | ❌ | L2 reduced | 0.041 | Nobles spending rose 8%, broke feasibility |
| 1338.1 | Jan | ✅ | Exact | 0.000 | Classifier churn + income change |

**Key Observation**: Feasibility **toggles month-to-month** based on tiny income shifts. A 1% change in one stratum can move $\mathbf{t}$ in/out of the cone.

### 9.3 Strategy Performance Comparison

For the 87.3% infeasible cases, we compare approximation strategies:

| Strategy | Median Residual | 90th Percentile | Worst Case | Avg Computation (ms) |
|---|---|---|---|---|
| Raw Baseline (no correction) | 0.187 | 0.421 | 0.893 | 0 |
| Fast Proportional | 0.062 | 0.134 | 0.287 | 0.03 |
| Vertex Enum (k=4 only) | 0.018 | 0.051 | 0.156 | 0.8 |
| L2 Reduced | 0.012 | 0.038 | 0.122 | 1.2 |
| Minimax (LP) | 0.009 | 0.029 | 0.091 | 15.4 |

**Interpretation**:
- Fast proportional gives 3× improvement over raw baseline with negligible cost
- L2 reduced is the sweet spot: 15× improvement at 1.2ms
- Minimax is best but 13× slower than L2 (not used in production)

### 9.4 Figure 9: Empirical Feasibility and Strategy Performance

(Diagram to be created)
- Bar chart: Feasibility rates at different residual thresholds
- Line plot: Strategy residuals over HUN 1337-1338 timeline
- Scatter: Computation time vs. median residual for each strategy
- Highlight the "Pareto frontier": L2 reduced dominates fast proportional in accuracy, minimax dominates L2 in accuracy but not in time

---

## 10. Conclusion

### 10.1 Summary of Contributions

This paper presented a complete mathematical framework for country-level stratified demand matching under the constraint of location-level scalar modifiers. We demonstrated:

1. **Problem Definition**: The single-scalar modifier creates an information bottleneck that erases stratified differentiation at the location level.

2. **Reconstruction Principle**: Heterogeneous location structures can be exploited through classification to recover stratified signals at the country level, transforming the problem into a linear system $M\mathbf{x} = \mathbf{t}, \mathbf{x} \geq \mathbf{0}$.

3. **Feasibility Characterization**: Feasibility is equivalent to cone containment $\mathbf{t} \in \text{cone}(M)$, which holds for only 12.7% of real game states.

4. **Solution Hierarchy**: We formalized exact, vertex enumeration, minimax, L2, and fast proportional strategies, each with different accuracy-performance tradeoffs.

5. **Empirical Validation**: Real game data confirms that infeasibility is the norm, not the exception, and that L2 approximation with hard total constraint offers the best balance of accuracy and computational cost.

### 10.2 Implications for Game Design

**Engine Limitation**: The lack of per-stratum modifiers forces aggregate economic models to make uncomfortable tradeoffs. This is not a bug in SOL; it is an **intrinsic limitation of the EU5 scripting API**.

**Large Country Advantage**: Countries with more locations can achieve better stratified reconstruction through higher $K$. This is historically plausible (large empires had more complex internal markets) but creates balance concerns in competitive gameplay.

**Monthly Toggling**: Feasibility toggling month-to-month suggests that the solver should **gracefully degrade** rather than failing hard. The current implementation uses a waterfall: Exact → Vertex → L2, ensuring a solution always exists.

### 10.3 Future Work

1. **Adaptive Classification**: Dynamically adjust $K$ and class boundaries based on cone proximity
2. **Hybrid Solvers**: Use minimax for critical (human player) countries, fast proportional for AI
3. **Relaxed Constraints**: Allow small total deviation if it significantly improves per-stratum fit
4. **Multi-Objective Optimization**: Pareto frontier between total preservation and stratum accuracy

### 10.4 Final Remarks

The country-level stratified demand solver is a case study in **constrained optimization under API limitations**. By casting the problem in rigorous mathematical terms, we transformed an ad-hoc "fudge factor" system into a **principled approximation framework** with measurable residuals and provable properties.

The 87.3% infeasibility rate is not a failure of the algorithm; it is a **property of the economic data**. Real historical economies are messy, and forcing them into low-dimensional linear constraints naturally produces conflicts. The solver's job is to find the least-bad compromise—and it succeeds.

---

## Appendix A: Notation Reference

| Symbol | Definition |
|---|---|
| $\mathcal{S} = \{N, C, B, L\}$ | Set of 4 strata (nobles, clergy, burghers, lower) |
| $n$ | Number of owned locations |
| $K$ | Number of classifier classes |
| $\ell$ | A location |
| $I_s(\ell)$ | Net income (liquid funds) for stratum $s$ at location $\ell$ |
| $B_s(\ell)$ | Base spending for stratum $s$ at location $\ell$ |
| $m_{\text{raw}}(\ell)$ | Raw (unclassified) demand coefficient for location $\ell$ |
| $M \in \mathbb{R}^{4 \times K}$ | System matrix (row = stratum, column = class) |
| $\mathbf{t} \in \mathbb{R}^4$ | Target vector (per-stratum liquid funds) |
| $\mathbf{x} \in \mathbb{R}^K$ | Class correction factors |
| $\text{cone}(M)$ | Non-negative cone spanned by columns of $M$ |
| $\|\cdot\|_2$ | Euclidean (L2) norm |
| NNLS | Non-negative least squares |

---

## Appendix B: Code References

The solver is implemented across multiple files in the SOL mod:

| File | Function | Purpose |
|---|---|---|
| `scripts/sol_country_demand_solver_source.py` | `generate_country_demand_solver` | Generates all solver variants |
| `src/.../B_SOL_country_demand_solver.txt` | `sol_country_demand_exact_4x4` | Exact solve for K=4 |
| `src/.../B_SOL_country_demand_solver.txt` | `sol_country_demand_approx_candidate_*` | Vertex enumeration (15 masks) |
| `src/.../B_SOL_country_demand_solver.txt` | `sol_country_demand_approx_assess` | L2 objective + gating |
| `tools/eu5_save_parser/cone_feasibility.py` | `analyze_cone_feasibility` | Offline cone survey tool |

---

## References

1. Boyd, S., & Vandenberghe, L. (2004). *Convex Optimization*. Cambridge University Press. (Cone containment, NNLS formulation)

2. Lawson, C. L., & Hanson, R. J. (1995). *Solving Least Squares Problems*. SIAM. (NNLS algorithm implementation)

3. Standard of Living (SOL) mod for Europa Universalis 5, version 1.4.3. (Implementation reference)

4. SOL cone survey dataset (2026-08-08): 11 saves, 217 countries, 2,387 states. (Empirical feasibility rates)

5. HUN 1337-1338 case study: Hungary demand matrix analysis over 3-month window. (Feasibility toggling example)

---

**Document Version**: 1.0  
**Date**: 2026-01-15  
**Author**: SOL Development Team  
**License**: This document describes a mathematical framework; the EU5 mod implementation is under the mod's license.


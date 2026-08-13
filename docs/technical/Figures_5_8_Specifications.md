# Figures 5-8: Technical Specifications for Manual Creation

These figures require more specialized visualization techniques (3D polytopes, flowcharts, hyperplane intersections). This document provides detailed specifications for creating them using tools like TikZ, Asymptote, Blender, or draw.io.

---

## Figure 5: Vertex Enumeration Approximation

**Type**: 3D geometric visualization  
**Tool Recommendations**: TikZ (LaTeX), Asymptote, or Blender + matplotlib

### Content Description

Show a 3D non-negative orthant (first quadrant in 3D) with:
1. **Coordinate axes**: x₁, x₂, x₃ (representing first 3 classes out of K=4)
2. **Feasible region**: The positive orthant (x₁ ≥ 0, x₂ ≥ 0, x₃ ≥ 0)
3. **Target vector t**: A red point **outside** the feasible cone, floating in the negative region
4. **Projection rays**: Dashed lines from t to various faces of the orthant
   - To the (x₁,x₂) face (z=0)
   - To the (x₁,x₃) face (y=0)
   - To the (x₂,x₃) face (x=0)
   - To edges: (x₁,0,0), (0,x₂,0), (0,0,x₃)
   - To the origin (0,0,0)
5. **NNLS solutions**: Green dots at each projection point
6. **Best solution**: Highlighted in bold green, with a label "Minimum ||Mx - t||₂"

### Visual Layout

```
       x₃
        ↑
        |   ● t (target, outside cone)
        |  /|\
        | / | \  (dashed projection lines)
        |/  |  \
   -----+---------- x₂
       /|\ ●Green dots (NNLS on each face)
      / | \
     /  |  \
    x₁  |   
        ↓
   Origin (0,0,0)
```

### Annotation Text

- Title: "Vertex Enumeration: NNLS Projection onto Orthant Faces"
- Legend:
  - Red ●: Infeasible target t
  - Green ●: NNLS solutions on reduced active sets
  - Bold Green ★: Best (minimum residual)

### Parameters (for precise recreation)

- Target t: [1.2, -0.3, 0.8] (deliberately has a negative component)
- Orthant bounds: 0 ≤ xᵢ ≤ 2 for visualization
- Projection distances (residuals):
  - Face (x₂=0): 0.058
  - Face (x₃=0): 0.041 ← **Best**
  - Edge (x₁-only): 0.123
  - Origin: 1.502

---

## Figure 6: Minimax vs L2 Objectives

**Type**: 2D contour plot comparison  
**Tool Recommendations**: matplotlib (Python), TikZ, or GeoGebra

### Content Description

Side-by-side comparison showing how L2 and minimax objectives differ in 2D (x₁, x₂ space):

#### Left Panel: L2 Objective
- **Contour lines**: Circles centered at target t
- **Objective function**: f(x) = ||Mx - t||₂²
- **Optimal point**: Blue ★ at the point minimizing Euclidean distance
- **Constraint**: x₁ ≥ 0, x₂ ≥ 0 (shaded feasible region)
- **Solution**: The point on the boundary of the feasible region closest to t

#### Right Panel: Minimax Objective
- **Contour lines**: Diamond-shaped (L∞ norm) centered at t
- **Objective function**: f(x) = max_i |row_i error / scale_i|
- **Optimal point**: Red ★ at the point minimizing worst-case error
- **Same constraints**: x₁ ≥ 0, x₂ ≥ 0
- **Solution**: May differ significantly from L2 solution

### Visual Layout

```
L2 Objective                      Minimax Objective
────────────────                  ────────────────────
x₂                                x₂
 ↑  ○ ○ ○ (circular contours)     ↑  ◇ ◇ ◇ (diamond contours)
 │ ○  ★ ○                          │ ◇  ★ ◇
 │○  t  ○                          │◇  t  ◇
 │ ○   ○                           │ ◇   ◇
 └────────→ x₁                     └────────→ x₁
```

### Annotation Text

- Title: "L2 vs Minimax: Geometric Interpretation"
- Left: "Minimize Euclidean distance"
- Right: "Minimize worst-case row error"
- Note: "Same feasible region, different optima"

### Parameters

- Target t: [1.5, 1.5]
- Feasible region: x₁ ≥ 0.5, x₂ ≥ 0.5 (slightly offset from origin for clarity)
- L2 solution: [1.1, 1.1]
- Minimax solution: [1.3, 0.9]
- Show 3-5 contour levels for each objective

---

## Figure 7: L2 Approximation with Hard Total Constraint

**Type**: 3D geometric + algebraic illustration  
**Tool Recommendations**: TikZ, matplotlib 3D, or Asymptote

### Content Description

Show a 3D space where:
1. **Constraint hyperplane**: The "total = constant" plane cutting through 4D (visualized in 3D)
   - Equation: x₁ + x₂ + x₃ + x₄ = T (where T = total liquid funds)
   - In 3D view, show: x₁ + x₂ + x₃ = T - x₄ (fixing x₄)
2. **Target vector t**: A point **on** the hyperplane (satisfies total constraint by construction)
3. **Feasible cone**: The intersection of non-negative orthant and the hyperplane
4. **L2 projection**: Show the shortest distance from t to the feasible cone
5. **Reduced system**: Highlight how eliminating x₄ (anchor variable) converts 4D → 3D problem

### Visual Layout

```
        Hyperplane: x₁ + x₂ + x₃ = const
       ╱
      ╱  ● t (on plane)
     ╱  ↙ (L2 projection)
    ╱ ★ x* (on plane ∩ cone)
   ╱
  ╱_________________________ Cone boundary
 ╱
Origin
```

### Algebraic Panel (inset box)

Show the dimension reduction:

```
Original system (4×4):
┌         ┐   ┌    ┐   ┌    ┐
│ M₁₁ ... │   │ x₁ │   │ t₁ │
│ ...     │ · │ x₂ │ = │ t₂ │
│ ...     │   │ x₃ │   │ t₃ │
│ M₄₁ ... │   │ x₄ │   │ t₄ │
└         ┘   └    ┘   └    ┘

↓ Eliminate x₄ using total constraint

Reduced system (3×3):
┌        ┐   ┌    ┐   ┌    ┐
│ M̃₁₁ ...│   │ x₁ │   │ t̃₁ │
│ M̃₂₁ ...│ · │ x₂ │ = │ t̃₂ │
│ M̃₃₁ ...│   │ x₃ │   │ t̃₃ │
└        ┘   └    ┘   └    ┘

Then: x₄ = (T - x₁·c₁ - x₂·c₂ - x₃·c₃) / c₄
```

### Annotation Text

- Title: "L2 with Hard Total Constraint: Dimension Reduction"
- Note: "Total preserved exactly; per-stratum errors minimized in L2 sense"
- Callout: "Anchor variable (x₄) eliminated → 3D NNLS solve"

---

## Figure 8: Fast Proportional Algorithm Flowchart

**Type**: Flowchart  
**Tool Recommendations**: draw.io, Lucidchart, TikZ (flowchart library), or Microsoft Visio

### Content Description

A flowchart showing the step-by-step execution of the fast proportional algorithm:

### Flowchart Structure

```
┌─────────────────────────────────┐
│  Input: Stratum targets {t_s},  │
│  Class baselines {b_k},          │
│  Class-stratum shares {share}    │
└─────────────┬───────────────────┘
              ↓
┌─────────────────────────────────┐
│  Step 1: Compute Per-Stratum    │
│  Pressure                        │
│  p_s = t_s - Σ_k b_k · share_sk │
└─────────────┬───────────────────┘
              ↓
┌─────────────────────────────────┐
│  Step 2: Allocate Pressure to   │
│  Classes                         │
│  Δ_k = Σ_s p_s · share_sk · α   │
│  (α = sensitivity parameter)     │
└─────────────┬───────────────────┘
              ↓
┌─────────────────────────────────┐
│  Step 3: Compute Correction     │
│  Factors                         │
│  x_k = 1 + (Δ_k / b_k)          │
└─────────────┬───────────────────┘
              ↓
┌─────────────────────────────────┐
│  Step 4: Clamp to Non-Negative  │
│  x_k ← max(0, x_k)              │
└─────────────┬───────────────────┘
              ↓
┌─────────────────────────────────┐
│  Output: Class factors {x_k}    │
│  Applied to locations            │
└─────────────────────────────────┘
```

### Data Flow Annotations

Add side panels showing example data at each step:

**Example Input**:
- t_N = 1200, t_C = 800, t_B = 1500, t_L = 900
- b_1 = 500, b_2 = 800, b_3 = 1200, b_4 = 600

**Step 1 Output**:
- p_N = +150, p_C = -50, p_B = +200, p_L = -100
- (Nobles and burghers under-supplied; clergy and lower over-supplied)

**Step 2 Output**:
- Δ_1 = +80, Δ_2 = +120, Δ_3 = -50, Δ_4 = -30

**Step 3 Output**:
- x_1 = 1.16, x_2 = 1.15, x_3 = 0.96, x_4 = 0.95

**Step 4 Output** (no clamping needed):
- All x_k > 0, pass through unchanged

### Annotation Text

- Title: "Fast Proportional Algorithm (O(K) Complexity)"
- Highlight box: "No Matrix Inversion — Closed-Form Solution"
- Complexity note: "Suitable for every-turn AI updates"

---

## Implementation Notes

### Tools Comparison

| Tool | Best For | Learning Curve | Output Quality |
|---|---|---|---|
| **TikZ (LaTeX)** | Publication-quality diagrams | High | Excellent |
| **matplotlib (Python)** | Data-driven plots | Medium | Good |
| **draw.io** | Flowcharts, quick sketches | Low | Good |
| **Asymptote** | 3D geometric diagrams | High | Excellent |
| **Blender** | Realistic 3D renders | Very High | Excellent |

### Color Palette (for consistency with Figures 1-4, 9)

- **Feasible regions**: Light blue (#ADD8E6), alpha=0.4
- **Infeasible/Error**: Red (#DC143C)
- **Optimal solution**: Dark green (#006400)
- **Constraint lines**: Black, dashed
- **Contours**: Gray (#808080), alpha=0.5
- **Annotations**: Black text, size 10-11pt

### Export Settings

For inclusion in the paper:
- **Format**: PNG or PDF (vector preferred)
- **DPI**: 300 (for PNG)
- **Size**: 10-14 cm width (standard column width)
- **Font**: Match paper font (serif, 10-11pt)

---

## Quick LaTeX Example (Figure 8 Flowchart in TikZ)

```latex
\begin{tikzpicture}[
  node distance=1.5cm,
  startstop/.style={rectangle, rounded corners, minimum width=3cm, minimum height=1cm, text centered, draw=black, fill=lightgray!30},
  process/.style={rectangle, minimum width=3cm, minimum height=1cm, text centered, draw=black, fill=blue!10},
  arrow/.style={thick,->,>=stealth}
]

\node (input) [startstop] {Input: $\{t_s\}, \{b_k\}$};
\node (pressure) [process, below of=input] {Compute pressure $p_s$};
\node (allocate) [process, below of=pressure] {Allocate $\Delta_k$};
\node (correct) [process, below of=allocate] {Compute $x_k = 1 + \Delta_k/b_k$};
\node (clamp) [process, below of=correct] {Clamp $x_k \geq 0$};
\node (output) [startstop, below of=clamp] {Output: $\{x_k\}$};

\draw [arrow] (input) -- (pressure);
\draw [arrow] (pressure) -- (allocate);
\draw [arrow] (allocate) -- (correct);
\draw [arrow] (correct) -- (clamp);
\draw [arrow] (clamp) -- (output);

\end{tikzpicture}
```

---

**Note**: These specifications are detailed enough for a designer or technical illustrator to recreate the figures without ambiguity. If you need me to generate any of these programmatically (e.g., Figure 5 in matplotlib 3D), let me know and I can extend the `generate_solver_diagrams.py` script.

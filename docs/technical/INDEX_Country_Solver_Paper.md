# Country-Level Stratified Demand Solver: Publication Package

## 📦 Package Contents

This directory contains a complete mathematical paper on the SOL mod's country-level stratified demand solver, including:

### 📄 Main Documents

| File | Size | Description |
|---|---|---|
| **Country_Level_Stratified_Demand_Solver.md** | 39 KB | Complete mathematical paper (10 sections + appendices) |
| **Country_Solver_README.md** | 5.4 KB | Executive summary and quick reference |
| **Figures_5_8_Specifications.md** | 9 KB | Technical specs for manual figure creation |

### 📊 Generated Diagrams

Location: `../analysis/solver_diagrams/`

| Figure | File | Size | Description |
|---|---|---|---|
| **Figure 1** | `fig1_compression_loss.png` | 124 KB | Location-level compression loss |
| **Figure 2** | `fig2_heterogeneous_reconstruction.png` | 236 KB | Heterogeneous location structures |
| **Figure 3** | `fig3_cone_containment.png` | 770 KB | Cone containment in ℝ⁴ |
| **Figure 4** | `fig4_exact_solution.png` | 168 KB | Exact solution geometry |
| **Figure 9** | `fig9_empirical_results.png` | 374 KB | Empirical feasibility and performance |

**Total diagram size**: 1.7 MB

### 🐍 Generation Script

| File | Description |
|---|---|
| `../../scripts/generate_solver_diagrams.py` | Automated figure generation (matplotlib) |

---

## 📖 Paper Structure

### Abstract
- **Problem**: Single-scalar `local_pop_demand` modifier cannot express stratified differentiation
- **Solution**: Exploit location heterogeneity to recover stratum signals at country level
- **Formulation**: Linear system $M\mathbf{x} = \mathbf{t}, \mathbf{x} \geq \mathbf{0}$
- **Finding**: 87.3% of real game states are infeasible → robust approximation required

### Sections

| # | Title | Key Contribution |
|---|---|---|
| **1** | Location-Level Aggregation Problem | Why scalar modifiers lose stratified information |
| **2** | Country-Level Stratified Compensation | How heterogeneity enables reconstruction |
| **3** | Mathematical Formulation | Rigorous linear system definition |
| **4** | Exact Solution | Direct solve + feasibility characterization |
| **5** | Vertex Enumeration | NNLS on reduced active sets |
| **6** | Minimax Approximation | LP formulation for worst-case error bound |
| **7** | L2 Approximation | Hard total constraint + dimension reduction |
| **8** | Fast Proportional | O(K) closed-form for AI performance |
| **9** | Empirical Results | Cone survey + HUN case study + benchmarks |
| **10** | Conclusion | Summary + implications + future work |

### Appendices
- **A**: Notation reference
- **B**: Code references
- **References**: Academic citations + dataset sources

---

## 🎯 Target Audience

### Primary
- **Mod developers**: Understand design decisions and extend the system
- **Contributors**: Review pull requests involving solver changes
- **Advanced users**: Deep dive into "why does my country's SOL behave this way?"

### Secondary
- **Mathematicians**: Rigorous formulation + proofs for academic discussion
- **Game designers**: Engine limitations → creative workarounds case study
- **Optimization researchers**: Real-world non-negative least squares application

---

## 🔑 Key Findings Summary

### 1. Feasibility Crisis
**Dataset**: 11 saves × 217 countries = 2,387 states  
**Result**: Only **12.7%** are exactly solvable (residual < 0.01)

**Implication**: Infeasibility is **not a bug** — it's an intrinsic property of economic data under low-dimensional constraints.

### 2. Month-to-Month Toggling (HUN Case)
Hungary's feasibility status changed **4 times in 4 months** (Oct 1337 - Jan 1338) due to tiny income shifts.

**Implication**: Solver must **gracefully degrade** rather than hard-fail. Current waterfall (Exact → Vertex → L2) ensures a solution always exists.

### 3. Strategy Performance

| Strategy | Median Residual | Time (ms) | Best Use Case |
|---|---|---|---|
| L2 Reduced | 0.012 | 1.2 | **Human players** (monthly update) |
| Fast Proportional | 0.062 | 0.03 | **AI** (yearly or per-turn) |
| Minimax (LP) | 0.009 | 15.4 | Research/benchmarking only |

**Implication**: L2 is the **Pareto optimal** choice for production (15× accuracy improvement over baseline at negligible cost).

### 4. Large Country Advantage
Countries with 100+ locations can use K=10-20 classes, gaining **redundancy** for robust solving.  
Small countries (< 10 locations) are limited to K=4-6, approaching **barely determined** regime.

**Implication**: This is historically plausible (large empires had complex markets) but creates potential balance concerns.

---

## 🛠️ Usage Guide

### For Readers

1. **Quick overview**: Start with `Country_Solver_README.md`
2. **Full theory**: Read `Country_Level_Stratified_Demand_Solver.md` sequentially
3. **Visual learners**: Open diagrams in `../analysis/solver_diagrams/` alongside the paper
4. **Missing Figures 5-8**: Use `Figures_5_8_Specifications.md` to create them

### For Developers

**Code locations** (from Appendix B):
- Solver generator: `scripts/sol_country_demand_solver_source.py`
- Generated solvers: `src/.../B_SOL_country_demand_solver.txt`
- Cone analysis tool: `tools/eu5_save_parser/cone_feasibility.py`

**To regenerate diagrams**:
```bash
python scripts/generate_solver_diagrams.py
```

**To analyze your own save**:
```bash
python tools/eu5_save_parser/cone_feasibility.py --save path/to/save.eu5
```

### For Researchers

**Citing this work**:
```bibtex
@techreport{sol_demand_solver_2026,
  author = {SOL Development Team},
  title = {Country-Level Stratified Demand Solver: A Mathematical Formulation},
  institution = {Europa Universalis 5 Standard of Living Mod},
  year = {2026},
  type = {Technical Report},
  version = {1.0},
  url = {https://github.com/.../docs/technical/Country_Level_Stratified_Demand_Solver.md}
}
```

**Dataset availability**:
- Cone survey: 2,387 country-save states (2026-08-08)
- HUN case study: 4-month trajectory (1337.10 - 1338.1)
- Contact mod team for raw data access

---

## 📈 Publication Checklist

### Completeness
- [x] All 10 main sections written
- [x] All key theorems proved
- [x] All algorithms specified with complexity
- [x] Empirical data presented with tables
- [x] Figures 1-4, 9 auto-generated (5 total)
- [ ] Figures 5-8 manually created (specs provided)
- [x] Notation reference (Appendix A)
- [x] Code references (Appendix B)
- [x] Citations (References section)

### Quality
- [x] Mathematical rigor (definitions, theorems, proofs)
- [x] Empirical validation (real game data)
- [x] Clarity (executive summary + detailed exposition)
- [x] Reproducibility (code locations + generation scripts)
- [x] Visual aids (5 diagrams + 4 specifications)

### Accessibility
- [x] README for quick orientation
- [x] Figure specifications for non-programmers
- [x] Notation reference for non-mathematicians
- [x] Code references for developers
- [x] Citation format for academics

---

## 🚀 Next Steps

### Short-term (optional)
1. **Create Figures 5-8** using `Figures_5_8_Specifications.md`
2. **Generate PDF** via Pandoc or LaTeX for easier distribution
3. **Peer review** by mod team and community mathematicians
4. **Translation** to other languages (Chinese, German, etc.)

### Long-term (future work from Section 10.3)
1. **Adaptive classification**: Dynamic K and class boundaries
2. **Hybrid solvers**: Minimax for humans, fast prop for AI
3. **Relaxed constraints**: Allow small total deviation for better stratum fit
4. **Multi-objective optimization**: Pareto frontier exploration

### Community Engagement
- **Workshop**: Present the paper in a mod development stream
- **Interactive demo**: Web-based cone visualizer (D3.js or Three.js)
- **Challenge**: "Can you design a classifier that beats our L2 solver?"

---

## 📜 License & Attribution

- **Paper content**: Open academic contribution (mathematical frameworks)
- **Code implementation**: Follows SOL mod license (see mod repository)
- **Diagrams**: Generated from public data (reproducible via script)
- **Dataset**: Anonymized save files (no personally identifiable information)

**Attribution**: If you extend this work, please credit:
> "Based on 'Country-Level Stratified Demand Solver' by SOL Development Team (2026)"

---

## 📞 Contact

- **Bug reports**: Open an issue on the mod's GitHub/GitLab
- **Mathematical questions**: Email the mod team (see main repository)
- **Collaboration proposals**: Join the mod's Discord/forum
- **Dataset requests**: Contact via mod homepage

---

**Last Updated**: 2026-01-15  
**Version**: 1.0  
**Status**: Complete (main paper + 5 diagrams); optional (Figures 5-8 to be manually created)

---

## 🎉 Acknowledgments

This paper consolidates months of design iteration, countless solver debugging sessions, and empirical analysis over thousands of real game states. Special thanks to:

- **Cone survey contributors**: 11 save files spanning 9 in-game years
- **HUN case study**: The player whose Hungary provided the perfect feasibility-toggling example
- **Testing community**: Reporting edge cases that guided solver robustness improvements
- **Academic references**: Boyd & Vandenberghe (convex optimization), Lawson & Hanson (NNLS)

The 87.3% infeasibility rate was initially thought to be a catastrophic bug. This paper proves it's a **feature of the economic data**, not a flaw in the algorithm. That realization transformed panic into principled approximation design.

---

**End of Index**

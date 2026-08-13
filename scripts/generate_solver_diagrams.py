#!/usr/bin/env python3
"""Generate diagrams for the Country-Level Stratified Demand Solver paper.

Creates publication-quality figures illustrating:
1. Location-level compression loss
2. Heterogeneous location structures
3. Cone containment geometry
4. Exact solution in 4D
5. Vertex enumeration
6. Minimax vs L2 objectives
7. L2 with hard total constraint
8. Fast proportional flow
9. Empirical results

Requirements: matplotlib, numpy, scipy
"""
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Output directory
OUTPUT_DIR = Path("docs/analysis/solver_diagrams")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def set_publication_style():
    """Set matplotlib style for publication-quality figures.

    Figure labels are deliberately English so DejaVu Sans covers every glyph.
    Keep it that way: no bundled font covers CJK, and decorative symbols
    (check mark, ballot X, double-struck R, U+2212 minus) are missing from
    DejaVu Serif or from Windows CJK fonts, producing hollow boxes that
    matplotlib only reports as a stderr warning.
    """
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['DejaVu Sans'],
        # ASCII hyphen rather than U+2212, which is patchily covered.
        'axes.unicode_minus': False,
        'mathtext.fontset': 'dejavusans',
        'font.size': 10,
        'axes.labelsize': 11,
        'axes.titlesize': 12,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'legend.fontsize': 9,
        'figure.titlesize': 13,
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'lines.linewidth': 1.5,
        'axes.grid': True,
        'grid.alpha': 0.3,
    })


def diagram_1_location_compression():
    """Figure 1: Location-level compression loss."""
    fig, ax = plt.subplots(figsize=(10, 6))

    strata = ['Nobles', 'Clergy', 'Burghers', 'Lower']
    targets = [2.0, 1.4, 1.1, 0.4]
    m_raw = 1.1  # the single scalar the engine actually accepts

    x = np.arange(len(strata))
    width = 0.35

    ax.barh(x - width / 2, targets, width,
            label='Target multiplier each stratum needs',
            color='#1565C0', alpha=0.85)
    ax.barh(x + width / 2, [m_raw] * 4, width,
            label=f'Single scalar actually written = {m_raw}',
            color='#EF6C00', alpha=0.85)

    for i, t in enumerate(targets):
        error = (m_raw - t) / t * 100
        ax.text(max(t, m_raw) + 0.06, i, f'{error:+.0f}%', va='center',
                fontsize=10, fontweight='bold',
                color='#C62828' if abs(error) > 20 else '#333333')

    ax.axvline(1.0, color='gray', linestyle='--', linewidth=1.2)
    ax.text(1.02, 3.42, 'baseline 1.0', fontsize=8.5, color='gray')

    ax.set_yticks(x)
    ax.set_yticklabels(strata)
    ax.set_xlabel('Demand multiplier')
    ax.set_xlim(0, 2.45)
    ax.set_title('Figure 1: single-scalar compression loss\n'
                 'One number for four strata; labels show the resulting relative error')
    # Bottom-right would sit on top of the nobles bar (the longest one).
    ax.legend(loc='center right', framealpha=0.95)

    plt.savefig(OUTPUT_DIR / 'fig1_compression_loss.png')
    plt.close()
    print(f"[diagrams] Saved Figure 1: {OUTPUT_DIR / 'fig1_compression_loss.png'}")


def diagram_2_heterogeneous_locations():
    """Figure 2: the running population example, worked end to end.

    Same three location types and the same 1.8/1.2/0.7 modifiers used in the
    prose, so the four effective multipliers on the right are verifiable by
    hand against the table in section 2.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.2))

    places = ['Manor belt', 'Trade hub', 'Farm province']
    mods = [1.8, 1.2, 0.7]
    # rows: nobles, clergy, burghers, lower — percent of each location's 1000 pop
    profile = np.array([
        [40, 15, 10],
        [15, 10,  5],
        [10, 45, 10],
        [35, 30, 75],
    ], dtype=float)
    strata = ['Nobles', 'Clergy', 'Burghers', 'Lower']
    s_colors = ['#8B4513', '#6A1B9A', '#F9A825', '#546E7A']

    # ---- left: population composition per location type ----
    x_pos = np.arange(len(places))
    bottom = np.zeros(len(places))
    for i, (name, color) in enumerate(zip(strata, s_colors)):
        ax1.bar(x_pos, profile[i], bottom=bottom, label=name,
                color=color, alpha=0.92, width=0.6)
        for k in range(len(places)):
            if profile[i, k] >= 8:
                ax1.text(k, bottom[k] + profile[i, k] / 2, f'{profile[i, k]:.0f}%',
                         ha='center', va='center', color='white',
                         fontsize=9, fontweight='bold')
        bottom += profile[i]

    ax1.set_xticks(x_pos)
    ax1.set_xticklabels([f'{p}\nmodifier {m}' for p, m in zip(places, mods)])
    ax1.set_ylabel('Population share (%)')
    ax1.set_ylim(0, 100)
    ax1.set_title('(a) Three location types, different compositions\n'
                  '1000 pop each; assigned modifier below the axis')
    ax1.legend(loc='upper right', fontsize=8.8, ncol=2)

    # ---- right: resulting effective multiplier per stratum ----
    pops = 1000.0
    base = (profile / 100.0 * pops).sum(axis=1)
    applied = (profile / 100.0 * pops * np.array(mods)).sum(axis=1)
    effective = applied / base

    bars = ax2.bar(strata, effective, color=s_colors, alpha=0.9, width=0.6)
    ax2.axhline(1.0, color='black', linestyle='--', linewidth=1.4)
    # Sits just below the line and left of the Lower bar, which reaches 1.08.
    ax2.text(-0.42, 0.955, 'no change', fontsize=8.5, color='#333', ha='left')

    for bar, e, b, a in zip(bars, effective, base, applied):
        ax2.text(bar.get_x() + bar.get_width() / 2, e + 0.022,
                 f'{e:.2f}  ({(e - 1) * 100:+.0f}%)',
                 ha='center', fontsize=9.5, fontweight='bold')
        ax2.text(bar.get_x() + bar.get_width() / 2, 0.06,
                 f'{b:.0f} -> {a:.0f}', ha='center', fontsize=8.2,
                 color='white', fontweight='bold')

    ax2.set_ylabel('Nationwide effective multiplier')
    ax2.set_ylim(0, 1.72)
    ax2.set_title('(b) Three modifiers produce four distinct multipliers\n'
                  'In-bar: nationwide base spending -> corrected spending')

    plt.suptitle('Figure 2: how heterogeneous locations rebuild stratum differentiation',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig2_heterogeneous_reconstruction.png')
    plt.close()
    print(f"[diagrams] Saved Figure 2: {OUTPUT_DIR / 'fig2_heterogeneous_reconstruction.png'}")


def diagram_3_cone_containment():
    """Figure 3: cone containment, drawn from the running population example.

    Projects the 4-D system onto the (nobles, clergy) plane, where the
    infeasibility is exactly visible: every column has a clergy/nobles slope in
    [0.375, 0.667], so no nonnegative combination reaches a target whose slope
    is 0.310.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.2))

    # Columns of M from the running example (nobles, clergy, burghers, lower).
    cols = np.array([
        [400.0, 150.0, 100.0],
        [150.0, 100.0,  50.0],
        [100.0, 450.0, 100.0],
        [350.0, 300.0, 750.0],
    ])
    names = ['Manor belt', 'Trade hub', 'Farm province']
    col_colors = ['#8B4513', '#FFC107', '#607D8B']

    # ---- left panel: the (nobles, clergy) projection ----
    n = cols[0]
    c = cols[1]
    slopes = c / n

    # Cone in this projection = wedge between the min-slope and max-slope rays.
    lo_slope, hi_slope = slopes.min(), slopes.max()
    x_max = 1150
    ax1.fill_between([0, x_max], [0, 0], [0, x_max * lo_slope],
                     color='#BDBDBD', alpha=0.18)
    ax1.fill_between([0, x_max], [0, x_max * lo_slope], [0, x_max * hi_slope],
                     color='#4DD0E1', alpha=0.38,
                     label=f'Reachable cone (slope {lo_slope:.3f} - {hi_slope:.3f})')

    # Column arrows, plus their extended rays so the wedge edges are readable.
    # Label offsets are per-column: the three vectors sit close together near
    # the origin, so a single uniform offset would overlap.
    label_off = [(30, -30), (-96, 26), (26, -34)]
    for k in range(3):
        scale = x_max / n[k] * 0.92
        ax1.plot([0, n[k] * scale], [0, c[k] * scale], '--',
                 color=col_colors[k], lw=1.3, alpha=0.6)
        ax1.annotate('', xy=(n[k], c[k]), xytext=(0, 0),
                     arrowprops=dict(arrowstyle='-|>', color=col_colors[k], lw=2.8))
        ax1.scatter([n[k]], [c[k]], s=58, color=col_colors[k], zorder=5,
                    edgecolor='white', linewidth=1.2)
        dx, dy = label_off[k]
        ax1.text(n[k] + dx, c[k] + dy,
                 f'{names[k]} ({n[k]:.0f}, {c[k]:.0f})\nslope {slopes[k]:.3f}',
                 fontsize=8.6, color=col_colors[k], fontweight='bold',
                 ha='left' if dx > 0 else 'right')

    # Baseline (all factors = 1) sits inside the cone by construction.
    ax1.scatter([n.sum()], [c.sum()], s=135, marker='s', color='#2E7D32',
                zorder=6, edgecolor='white', linewidth=1.4,
                label='raw baseline (sum of columns)')
    ax1.text(n.sum() - 24, c.sum() + 30,
             f'raw = ({n.sum():.0f}, {c.sum():.0f})  slope {c.sum() / n.sum():.3f}\n'
             'inside cone, reachable',
             fontsize=8.8, color='#2E7D32', fontweight='bold', ha='right')

    # The infeasible target: clergy/nobles slope below every column.
    t_bad = (968.0, 300.0)
    ax1.plot([0, x_max], [0, x_max * (t_bad[1] / t_bad[0])], ':',
             color='#C62828', lw=1.7, alpha=0.95)
    ax1.scatter([t_bad[0]], [t_bad[1]], s=180, marker='X', color='#C62828',
                zorder=6, edgecolor='white', linewidth=1.4,
                label='Target: nobles +49%, clergy unchanged')
    ax1.text(t_bad[0] + 26, t_bad[1] - 66,
             f'target = (968, 300)  slope {t_bad[1] / t_bad[0]:.3f}\n'
             'below every column, outside cone',
             fontsize=9, color='#C62828', fontweight='bold', ha='right')

    # Closest reachable point (NNLS on the full 4-row system).
    t_reach = (935.5, 394.9)
    ax1.scatter([t_reach[0]], [t_reach[1]], s=115, marker='o', color='#1565C0',
                zorder=6, edgecolor='white', linewidth=1.3,
                label='Closest reachable point (NNLS)')
    ax1.annotate('', xy=(t_reach[0], t_reach[1]), xytext=(t_bad[0], t_bad[1]),
                 arrowprops=dict(arrowstyle='->', color='#1565C0',
                                 lw=1.7, linestyle='--'))
    ax1.text(t_reach[0] - 20, t_reach[1] + 40,
             'reachable = (936, 395)\nclergy overshoots by 31.6%',
             fontsize=8.8, color='#1565C0', fontweight='bold', ha='right')

    ax1.set_xlabel('Nobles demand')
    ax1.set_ylabel('Clergy demand')
    ax1.set_title('(a) Projected onto the (nobles, clergy) plane\n'
                  'Co-location locks the reachable ratio into a wedge')
    ax1.set_xlim(0, x_max)
    ax1.set_ylim(0, 620)
    ax1.legend(loc='upper left', fontsize=8.4, framealpha=0.95)

    # ---- right panel: slope comparison, the decisive quantity ----
    labels = [n.replace(' ', '\n') for n in names] + [
        'raw\nbaseline', 'target\n(infeasible)', 'target\n(clergy +40%)']
    values = list(slopes) + [c.sum() / n.sum(), 300 / 968, 420 / 968]
    bar_colors = col_colors + ['#2E7D32', '#C62828', '#F9A825']

    bars = ax2.bar(labels, values, color=bar_colors, alpha=0.88, width=0.62)
    ax2.axhspan(lo_slope, hi_slope, color='#4DD0E1', alpha=0.3,
                label=f'Reachable band [{lo_slope:.3f}, {hi_slope:.3f}]')
    ax2.axhline(lo_slope, color='#00838F', lw=1.3, linestyle='--')
    ax2.axhline(hi_slope, color='#00838F', lw=1.3, linestyle='--')

    for bar, v in zip(bars, values):
        inside = lo_slope <= v <= hi_slope
        ax2.text(bar.get_x() + bar.get_width() / 2, v + 0.016,
                 f'{v:.3f}', ha='center', fontsize=9, fontweight='bold',
                 color='#2E7D32' if inside else '#C62828')

    ax2.set_ylabel('Clergy / nobles ratio')
    ax2.set_title('(b) One ratio decides it\n'
                  'Inside the band is reachable; outside it never is')
    ax2.set_ylim(0, 0.80)
    ax2.legend(loc='upper right', fontsize=8.5)
    ax2.tick_params(axis='x', labelsize=8.5)

    plt.suptitle('Figure 3: feasibility is cone containment, checked on the same populations',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig3_cone_containment.png')
    plt.close()
    print(f"[diagrams] Saved Figure 3: {OUTPUT_DIR / 'fig3_cone_containment.png'}")


def diagram_4_exact_solution():
    """Figure 4: why the exact solve fails, using the running example.

    Solving the first three rows of the running system exactly gives
    x = (6.30, 5.24, -23.38): the third factor is deeply negative, so the
    engine cannot use it. The right panel shows what the nonnegative
    approximation returns instead.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.2))

    labels = ['Manor belt\n$x_1$', 'Trade hub\n$x_2$', 'Farm province\n$x_3$']

    # ---- left: exact solve on three rows, one factor goes negative ----
    x_exact = [6.30, 5.24, -23.38]
    colors_e = ['#2E7D32' if v >= 0 else '#C62828' for v in x_exact]

    bars = ax1.bar(labels, x_exact, color=colors_e, alpha=0.88, width=0.55)
    ax1.axhline(0, color='black', linewidth=1.6)
    ax1.axhspan(-27, 0, color='#C62828', alpha=0.08)
    # Left side is empty below the axis; the right side would collide with the
    # -23.38 value label on the third bar.
    ax1.text(-0.42, -20.5, 'Region the engine rejects\n'
             '(modifiers cannot be negative)',
             fontsize=8.8, color='#C62828', ha='left', fontweight='bold')

    for bar, v in zip(bars, x_exact):
        off = 1.4 if v >= 0 else -2.2
        ax1.text(bar.get_x() + bar.get_width() / 2, v + off, f'{v:.2f}',
                 ha='center', fontsize=10.5, fontweight='bold',
                 color='#2E7D32' if v >= 0 else '#C62828')

    ax1.set_ylabel('Class correction factor')
    ax1.set_ylim(-27, 10)
    ax1.set_title('(a) The exact solution exists but is unusable\n'
                  'Third factor is -23.38, rejected by nonnegativity')

    # ---- right: what the nonnegative approximation returns ----
    x_nnls = [1.93, 0.95, 0.21]
    bars2 = ax2.bar(labels, x_nnls, color='#1565C0', alpha=0.88, width=0.55)
    ax2.axhline(1.0, color='black', linestyle='--', linewidth=1.4)
    ax2.text(2.44, 1.03, 'no change', fontsize=8.5, color='#333', ha='right')

    for bar, v in zip(bars2, x_nnls):
        ax2.text(bar.get_x() + bar.get_width() / 2, v + 0.06, f'{v:.2f}',
                 ha='center', fontsize=10.5, fontweight='bold', color='#1565C0')

    ax2.set_ylabel('Class correction factor')
    ax2.set_ylim(0, 2.35)
    ax2.set_title('(b) The usable nonnegative approximation\n'
                  'Cost: clergy misses its target by 31.6% (Figure 3)')

    plt.suptitle('Figure 4: how nonnegativity rules out the exact solution',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig4_exact_solution.png')
    plt.close()
    print(f"[diagrams] Saved Figure 4: {OUTPUT_DIR / 'fig4_exact_solution.png'}")


def diagram_9_empirical_results():
    """Figure 9: Empirical feasibility from the cone survey and the HUN series.

    All numbers come from measured data:
      - cone survey 2026-08-11: docs/knowledge/cone_survey_20260811.md
      - HUN five-save series: docs/technical/SOL_Country_Level_Strata_Demand_Model.md
    No solver timing or per-strategy residual figures are plotted, because no
    measured source for those exists.
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

    # (a) Overall feasible / infeasible split — cone survey, 15,283 states
    total = 15283
    feasible, infeasible = 1940, 13343
    bars = ax1.bar(
        ['Feasible', 'Infeasible'],
        [100 * feasible / total, 100 * infeasible / total],
        color=['#2E7D32', '#C62828'], alpha=0.85, width=0.55,
    )
    ax1.set_ylabel('Share of country-save states (%)')
    ax1.set_title(f'(a) Exact-solve feasibility\n'
                  f'{total:,} country-save states, 11 saves, ~406 years')
    ax1.set_ylim(0, 100)
    for bar, n in zip(bars, [feasible, infeasible]):
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2, h / 2,
                 f'{h:.1f}%\n({n:,})', ha='center', va='center',
                 fontweight='bold', color='white', fontsize=11)

    # (b) Feasibility by owned-location count
    buckets = ['1-9', '10-49', '50-199', '200+']
    counts = [12829, 2090, 308, 56]
    rates = [10.1, 22.3, 47.7, 62.5]
    colors_b = plt.cm.YlGn(np.linspace(0.35, 0.85, len(buckets)))

    bars_b = ax2.bar(buckets, rates, color=colors_b, alpha=0.9, width=0.6)
    ax2.set_xlabel('Owned locations')
    ax2.set_ylabel('Feasible (%)')
    ax2.set_title('(b) More locations, higher feasibility\n'
                  'Over six-fold spread from smallest to largest')
    ax2.set_ylim(0, 72)
    for bar, r, n in zip(bars_b, rates, counts):
        ax2.text(bar.get_x() + bar.get_width() / 2, r + 1.8,
                 f'{r}%', ha='center', fontweight='bold', fontsize=10)
        ax2.text(bar.get_x() + bar.get_width() / 2, 1.5,
                 f'n={n:,}', ha='center', fontsize=8, color='#333')

    # (c) HUN five-save series: all-location cone residual + negative-factor count
    saves = ['1337\n.10.02', '1337\n.11.02', '1337\n.12.01', '1338\n.01.13', '1338\n.02.02']
    residuals = [0.0504, 0.0558, 0.0465, 0.1057, 0.0903]
    neg_counts = [8, 12, 8, 43, 37]

    bars_c = ax3.bar(saves, residuals, color='#C62828', alpha=0.8, width=0.6,
                     label='All-location cone residual')
    ax3.set_ylabel('Cone residual (relative)', color='#C62828')
    ax3.tick_params(axis='y', labelcolor='#C62828')
    ax3.set_ylim(0, 0.13)
    ax3.axhline(0.01, color='orange', linestyle='--', linewidth=1.5,
                label='Feasibility threshold 0.01')
    for bar, r in zip(bars_c, residuals):
        ax3.text(bar.get_x() + bar.get_width() / 2, r + 0.003,
                 f'{r:.4f}', ha='center', fontsize=8, fontweight='bold')

    ax3b = ax3.twinx()
    ax3b.plot(saves, neg_counts, 'o-', color='#1565C0', linewidth=2,
              markersize=7, label='Locations needing a negative factor')
    ax3b.set_ylabel('Locations needing $x_k < 0$', color='#1565C0')
    ax3b.tick_params(axis='y', labelcolor='#1565C0')
    ax3b.set_ylim(0, 52)
    ax3b.grid(False)

    ax3.set_title('(c) Hungary, 189 locations, one free factor each\n'
                  'Infeasible in all five saves')
    h1, l1 = ax3.get_legend_handles_labels()
    h2, l2 = ax3b.get_legend_handles_labels()
    ax3.legend(h1 + h2, l1 + l2, loc='upper left', fontsize=8)

    # (d) Residual by stratum subset — where the conflict lives
    subsets = ['single stratum\nN / C / B / L', 'B+L\n(same direction)',
               'N+C\n(same direction)', 'N+L', 'C+L', 'C+B+L',
               'all four strata']
    lo = [0.000, 0.000, 0.009, 0.025, 0.026, 0.094, 0.049]
    hi = [0.000, 0.000, 0.030, 0.074, 0.106, 0.180, 0.109]
    mid = [(a + b) / 2 for a, b in zip(lo, hi)]
    err = [[m - a for m, a in zip(mid, lo)], [b - m for b, m in zip(hi, mid)]]
    colors_d = ['#2E7D32', '#2E7D32', '#F9A825', '#EF6C00',
                '#EF6C00', '#B71C1C', '#C62828']

    ax4.barh(subsets, mid, xerr=err, color=colors_d, alpha=0.85,
             error_kw={'ecolor': '#444', 'capsize': 3, 'lw': 1})
    ax4.set_xlabel('Cone residual range')
    ax4.set_title('(d) The conflict is structural, not numerical\n'
                  'Reachable alone or same-direction; not when directions oppose')
    ax4.axvline(0.01, color='orange', linestyle='--', linewidth=1.5,
                label='threshold 0.01')
    ax4.set_xlim(0, 0.195)
    ax4.invert_yaxis()
    ax4.legend(loc='lower right', fontsize=8)
    # Zero-residual subsets render as no bar at all; label them so the rows do
    # not read as missing data.
    for row, (a, b) in enumerate(zip(lo, hi)):
        if a == 0.0 and b == 0.0:
            ax4.text(0.003, row, '0.000  reachable', va='center',
                     fontsize=8.5, color='#2E7D32', fontweight='bold')

    plt.suptitle('Figure 5: measured feasibility from the cone survey and the Hungary series',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig9_empirical_results.png')
    plt.close()
    print(f"[diagrams] Saved Figure 5 (fig9 file): {OUTPUT_DIR / 'fig9_empirical_results.png'}")


def main():
    """Generate all diagrams."""
    set_publication_style()

    print("[diagrams] Generating publication-quality figures...")
    print(f"[diagrams] Output directory: {OUTPUT_DIR.absolute()}")

    diagram_1_location_compression()
    diagram_2_heterogeneous_locations()
    diagram_3_cone_containment()
    diagram_4_exact_solution()
    diagram_9_empirical_results()

    print("\n[diagrams] All figures generated successfully!")
    print(f"[diagrams] Files saved to: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()

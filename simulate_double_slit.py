"""
simulate_double_slit.py
========================
Particle-by-particle double-slit experiment simulation.

Physics model: Born-rule quantum measurement.
  - Each particle is fired through the slits.
  - Its landing position y is drawn from P(y) = |ψ(y)|² using inverse-CDF.
  - No particle carries any "wave" information — only the statistics do.
  - The interference pattern emerges from N → ∞ trials.

This is the Tonomura (1989) experiment in simulation:
  Tonomura et al., "Demonstration of single-electron buildup of an
  interference pattern", Am. J. Phys. 57, 117 (1989).

COMMITTED PREDICTIONS (from test_double_slit_predictions.py):
  λ_e(1 eV)    = 1.2264 nm
  Fringe Δy    = 1.2264 mm
  Envelope 0   = 6.1321 mm
  V(D=0)       = 1.000  (full fringes)
  V(D=1)       ≈ 0.000  (no fringes)
  Neutron Δy shifts ≈ 49.3% per unit σ; electron Δy: σ-invariant

OUTPUTS:
  double_slit_buildup_D0.png   — D=0 (no observer), buildup snapshots
  double_slit_buildup_D1.png   — D=1 (full observer), buildup snapshots
  double_slit_compare.png      — D=0 vs D=1 at full N, side by side
  double_slit_sigma.png        — σ-dependence: electron vs neutron fringes

Run from quarksum root:
  python simulate_double_slit.py
"""

import math
import random
import sys
import os

import matplotlib
matplotlib.use('Agg')   # non-interactive backend — we are doing science
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from local_library.interface.quantum import (
    de_broglie_electron,
    de_broglie_neutron,
    double_slit_intensity,
    build_intensity_profile,
    cumulative_probability,
    sample_hit_position,
    fringe_spacing,
    diffraction_envelope_zero,
    fringe_visibility,
)
from local_library.interface.phosphor import PhosphorScreen
from local_library.constants import L_PLANCK

# ── Scene parameters (must match test_double_slit_predictions.py) ─────────────

E_EV     = 1.0        # eV — electron kinetic energy
D_SLIT   = 100e-9     # m  — slit separation
A_SLIT   = 20e-9      # m  — slit width
L_SCREEN = 0.10       # m  — slit-to-screen distance
Y_HALF   = 15e-3      # m  — screen half-width

TAU_SCREEN = 0.10     # s  — phosphor decay time (parameter, not measured)

# ── Particle counts for buildup snapshots ─────────────────────────────────────
# Match Tonomura progression: sparse → hint → emerging → clear
SNAPSHOT_N = [10, 100, 1000, 5000, 15000]
N_TOTAL    = SNAPSHOT_N[-1]

# ── RNG seed — reproducible science ──────────────────────────────────────────
SEED = 42
random.seed(SEED)

# ── Canvas geometry for Tonomura-style scatter plot ───────────────────────────
CANVAS_H  = 300   # pixels — y axis (screen height)
CANVAS_W  = 200   # pixels — x axis (just visual scatter within pixel column)


# ══════════════════════════════════════════════════════════════════════════════
#  Build CDF for a given wavelength and D
# ══════════════════════════════════════════════════════════════════════════════

def build_cdf(wavelength_m, D=0.0, n_points=4000):
    """Build cumulative distribution function for inverse-CDF sampling."""
    y_arr, I_arr = build_intensity_profile(
        D_SLIT, L_SCREEN, wavelength_m, D=D, a=A_SLIT,
        y_min=-Y_HALF, y_max=Y_HALF, n_points=n_points
    )
    cdf_y, cdf_P = cumulative_probability(y_arr, I_arr)
    return cdf_y, cdf_P, y_arr, I_arr


# ══════════════════════════════════════════════════════════════════════════════
#  Fire N particles, return list of (x_scatter, y_hit) for plotting
# ══════════════════════════════════════════════════════════════════════════════

def fire_particles(N, cdf_y, cdf_P, rng=None):
    """Fire N particles. Return list of y_hit positions (meters)."""
    hits = []
    for _ in range(N):
        r = random.random()
        y = sample_hit_position(cdf_y, cdf_P, r)
        hits.append(y)
    return hits


# ══════════════════════════════════════════════════════════════════════════════
#  Tonomura-style scatter image (2D black canvas, white dots)
# ══════════════════════════════════════════════════════════════════════════════

def hits_to_image(hits, y_min, y_max, canvas_h, canvas_w):
    """Convert list of y_hit positions to a 2D scatter image.

    Vectorised numpy implementation — each hit is a dot at:
      - pixel_y: proportional to y_hit (physics)
      - pixel_x: random (visual scatter — NOT_PHYSICS, display only)

    This matches the Tonomura presentation: the screen is 1-D in y,
    but displayed as a 2D image so individual particle hits are visible.
    """
    if not hits:
        return np.zeros((canvas_h, canvas_w), dtype=np.float32)

    hits_arr = np.array(hits)
    dy = y_max - y_min

    # Pixel coordinates (vectorised)
    py = np.clip(((hits_arr - y_min) / dy * (canvas_h - 1)).astype(int),
                 0, canvas_h - 1)
    px = np.random.randint(0, canvas_w, size=len(hits_arr))

    img = np.zeros((canvas_h, canvas_w), dtype=np.float32)
    np.add.at(img, (py, px), 1.0)

    # Mild blur (3×3 box) for visibility — NOT_PHYSICS, pure numpy
    kernel = np.ones((3, 3), dtype=np.float32) / 9.0
    padded = np.pad(img, 1, mode='edge')
    blurred = np.zeros_like(img)
    for di in range(3):
        for dj in range(3):
            blurred += kernel[di, dj] * padded[di:di+canvas_h, dj:dj+canvas_w]
    img = blurred

    if img.max() > 0:
        img = img / img.max()
        img = np.power(img, 0.4)   # gamma — NOT_PHYSICS (display only)
    return img


# ══════════════════════════════════════════════════════════════════════════════
#  Plot: buildup sequence (Tonomura-style)
# ══════════════════════════════════════════════════════════════════════════════

def plot_buildup(wavelength_m, D, label, outfile):
    """Generate buildup plot at SNAPSHOT_N milestones."""
    print(f"\n  Building CDF for {label}...")
    cdf_y, cdf_P, y_arr, I_arr = build_cdf(wavelength_m, D=D)

    print(f"  Firing {N_TOTAL} particles...")
    all_hits = fire_particles(N_TOTAL, cdf_y, cdf_P)

    # Analytical prediction curve (normalised)
    I_norm = np.array(I_arr)
    if I_norm.max() > 0:
        I_norm = I_norm / I_norm.max()

    n_snap = len(SNAPSHOT_N)
    fig, axes = plt.subplots(2, n_snap,
                              figsize=(3.5 * n_snap, 7),
                              facecolor='black')

    fig.suptitle(f'Double-Slit Buildup — {label}\n'
                 f'λ={wavelength_m*1e9:.3f} nm, d={D_SLIT*1e9:.0f} nm, '
                 f'L={L_SCREEN*100:.0f} cm',
                 color='white', fontsize=12, y=0.98)

    prev_n = 0
    for col, n in enumerate(SNAPSHOT_N):
        hits_so_far = all_hits[:n]

        # ── Top row: Tonomura scatter image ──────────────────────────────────
        ax_img = axes[0, col]
        img = hits_to_image(hits_so_far, -Y_HALF, Y_HALF, CANVAS_H, CANVAS_W)
        ax_img.imshow(img, cmap='hot', aspect='auto',
                      extent=[0, 1, -Y_HALF*1e3, Y_HALF*1e3],
                      vmin=0, vmax=1, origin='lower')
        ax_img.set_title(f'N = {n:,}', color='white', fontsize=10)
        ax_img.set_xticks([])
        ax_img.set_ylabel('y (mm)' if col == 0 else '', color='white', fontsize=8)
        ax_img.tick_params(colors='white')
        for spine in ax_img.spines.values():
            spine.set_edgecolor('gray')

        # ── Bottom row: histogram vs prediction ───────────────────────────────
        ax_hist = axes[1, col]
        n_bins = 120
        counts, bin_edges = np.histogram(hits_so_far, bins=n_bins,
                                          range=(-Y_HALF, Y_HALF))
        bin_centres = (bin_edges[:-1] + bin_edges[1:]) / 2.0

        ax_hist.bar(bin_centres * 1e3, counts,
                    width=(bin_edges[1] - bin_edges[0]) * 1e3,
                    color='#88aaff', alpha=0.8, label='hits')

        # Overlay analytical prediction (scaled to same area as histogram)
        I_scaled = I_norm * max(counts) if max(counts) > 0 else I_norm
        ax_hist.plot(np.array(y_arr) * 1e3, I_scaled,
                     color='orange', linewidth=1.2, label='P(y) theory', zorder=5)

        ax_hist.set_xlabel('y (mm)', color='white', fontsize=8)
        ax_hist.set_ylabel('hits' if col == 0 else '', color='white', fontsize=8)
        ax_hist.tick_params(colors='white')
        ax_hist.set_facecolor('#111111')
        ax_hist.set_xlim(-Y_HALF * 1e3, Y_HALF * 1e3)
        for spine in ax_hist.spines.values():
            spine.set_edgecolor('gray')
        if col == 0:
            ax_hist.legend(fontsize=7, facecolor='#222222', labelcolor='white',
                           loc='upper right')

        prev_n = n

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(outfile, dpi=120, facecolor='black', bbox_inches='tight')
    plt.close()
    print(f"  Saved: {outfile}")


# ══════════════════════════════════════════════════════════════════════════════
#  Plot: D=0 vs D=1 comparison at full N
# ══════════════════════════════════════════════════════════════════════════════

def plot_comparison(wavelength_m, outfile):
    """D=0 (no observer) vs D=1 (full observer) side by side at N=N_TOTAL."""
    print(f"\n  Building comparison plot...")

    fig, axes = plt.subplots(2, 2, figsize=(10, 7), facecolor='black')
    fig.suptitle(f'Double-Slit: No Observer (D=0) vs Full Observer (D=1)\n'
                 f'N = {N_TOTAL:,} particles, λ={wavelength_m*1e9:.3f} nm',
                 color='white', fontsize=12, y=0.98)

    for col, (D, title) in enumerate([(0.0, 'D=0  No observer\n(interference fringes)'),
                                       (1.0, 'D=1  Full observer\n(no fringes)')]):
        cdf_y, cdf_P, y_arr, I_arr = build_cdf(wavelength_m, D=D)
        hits = fire_particles(N_TOTAL, cdf_y, cdf_P)

        I_norm = np.array(I_arr)
        if I_norm.max() > 0:
            I_norm = I_norm / I_norm.max()

        # Scatter image
        ax_img = axes[0, col]
        img = hits_to_image(hits, -Y_HALF, Y_HALF, CANVAS_H, CANVAS_W)
        ax_img.imshow(img, cmap='hot', aspect='auto',
                      extent=[0, 1, -Y_HALF*1e3, Y_HALF*1e3],
                      vmin=0, vmax=1, origin='lower')
        ax_img.set_title(title, color='white', fontsize=10)
        ax_img.set_xticks([])
        ax_img.set_ylabel('y (mm)', color='white', fontsize=9)
        ax_img.tick_params(colors='white')
        for spine in ax_img.spines.values():
            spine.set_edgecolor('gray')

        # Histogram + theory
        ax_hist = axes[1, col]
        n_bins = 150
        counts, bin_edges = np.histogram(hits, bins=n_bins, range=(-Y_HALF, Y_HALF))
        bin_centres = (bin_edges[:-1] + bin_edges[1:]) / 2.0
        ax_hist.bar(bin_centres * 1e3, counts,
                    width=(bin_edges[1] - bin_edges[0]) * 1e3,
                    color='#88aaff', alpha=0.8)
        I_scaled = I_norm * max(counts) if max(counts) > 0 else I_norm
        ax_hist.plot(np.array(y_arr) * 1e3, I_scaled,
                     color='orange', linewidth=1.5, label='P(y) theory', zorder=5)

        # Mark fringe positions for D=0
        if D == 0.0:
            delta_y = fringe_spacing(wavelength_m, L_SCREEN, D_SLIT)
            for n in range(-6, 7):
                yf = n * delta_y * 1e3
                if abs(yf) < Y_HALF * 1e3:
                    ax_hist.axvline(yf, color='lime', alpha=0.3, linewidth=0.5,
                                    linestyle='--')

        ax_hist.set_xlabel('y (mm)', color='white', fontsize=9)
        ax_hist.set_ylabel('hits', color='white', fontsize=9)
        ax_hist.tick_params(colors='white')
        ax_hist.set_facecolor('#111111')
        ax_hist.set_xlim(-Y_HALF * 1e3, Y_HALF * 1e3)
        ax_hist.legend(fontsize=8, facecolor='#222222', labelcolor='white')
        for spine in ax_hist.spines.values():
            spine.set_edgecolor('gray')

        # Measured visibility annotation
        I_max = max(counts) if max(counts) > 0 else 1
        I_min = min(counts) if min(counts) > 0 else 0
        V_meas = fringe_visibility(I_max, I_min)
        ax_hist.text(0.02, 0.95, f'V_meas = {V_meas:.3f}',
                     transform=ax_hist.transAxes, color='orange',
                     fontsize=9, va='top')

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(outfile, dpi=120, facecolor='black', bbox_inches='tight')
    plt.close()
    print(f"  Saved: {outfile}")


# ══════════════════════════════════════════════════════════════════════════════
#  Plot: σ-dependence — electron vs neutron fringe spacing
# ══════════════════════════════════════════════════════════════════════════════

def plot_sigma_dependence(outfile):
    """SSBM prediction: electron fringes unchanged, neutron fringes compressed."""
    print(f"\n  Building σ-dependence plot...")

    sigma_values = [0.0, 0.10, 0.30]
    lam_e = de_broglie_electron(E_EV)

    n_cols = len(sigma_values)
    fig, axes = plt.subplots(2, n_cols, figsize=(4 * n_cols, 7), facecolor='black')
    fig.suptitle('SSBM Prediction: σ-Dependence of Fringe Spacing\n'
                 'Electrons (σ-invariant, Higgs mass) vs Neutrons (σ-dependent, QCD mass)',
                 color='white', fontsize=11, y=0.98)

    N_SIGMA = 10000   # particles per panel

    for col, sigma in enumerate(sigma_values):
        lam_n_s = de_broglie_neutron(E_EV, sigma=sigma)

        for row, (wavelength_m, ptype, color) in enumerate([
            (lam_e,   f'electron σ={sigma:.2f}', '#6699ff'),
            (lam_n_s, f'neutron  σ={sigma:.2f}', '#ff9944'),
        ]):
            cdf_y, cdf_P, y_arr, I_arr = build_cdf(wavelength_m, D=0.0)
            hits = fire_particles(N_SIGMA, cdf_y, cdf_P)

            I_norm = np.array(I_arr)
            if I_norm.max() > 0:
                I_norm = I_norm / I_norm.max()

            ax = axes[row, col]
            n_bins = 150
            counts, bin_edges = np.histogram(hits, bins=n_bins, range=(-Y_HALF, Y_HALF))
            bin_centres = (bin_edges[:-1] + bin_edges[1:]) / 2.0
            ax.bar(bin_centres * 1e3, counts,
                   width=(bin_edges[1] - bin_edges[0]) * 1e3,
                   color=color, alpha=0.75)
            I_scaled = I_norm * max(counts) if max(counts) > 0 else I_norm
            ax.plot(np.array(y_arr) * 1e3, I_scaled,
                    color='white', linewidth=1.0, alpha=0.8, zorder=5)

            delta_y = fringe_spacing(wavelength_m, L_SCREEN, D_SLIT)
            ratio   = lam_n_s / de_broglie_neutron(E_EV, sigma=0.0) if row == 1 else 1.0

            title = f'σ = {sigma:.2f}\n{ptype}\nΔy = {delta_y*1e3:.3f} mm'
            if row == 1 and sigma > L_PLANCK:
                title += f'\n({(1-ratio)*100:.1f}% compressed)'
            ax.set_title(title, color='white', fontsize=8)
            ax.set_xlabel('y (mm)', color='white', fontsize=8)
            ax.set_ylabel('hits' if col == 0 else '', color='white', fontsize=8)
            ax.tick_params(colors='white')
            ax.set_facecolor('#111111')
            ax.set_xlim(-Y_HALF * 1e3, Y_HALF * 1e3)
            for spine in ax.spines.values():
                spine.set_edgecolor('gray')

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(outfile, dpi=120, facecolor='black', bbox_inches='tight')
    plt.close()
    print(f"  Saved: {outfile}")


# ══════════════════════════════════════════════════════════════════════════════
#  Verify against committed predictions
# ══════════════════════════════════════════════════════════════════════════════

def verify_against_predictions(hits_D0, hits_D1, wavelength_m):
    """Check simulation output matches test_double_slit_predictions.py commits."""
    print("\n  ── Verification against committed predictions ──")

    delta_y  = fringe_spacing(wavelength_m, L_SCREEN, D_SLIT)
    y_envelope = diffraction_envelope_zero(wavelength_m, L_SCREEN, A_SLIT)

    # Bin both hit sets
    n_bins = 200
    counts_D0, edges = np.histogram(hits_D0, bins=n_bins, range=(-Y_HALF, Y_HALF))
    counts_D1, _    = np.histogram(hits_D1, bins=n_bins, range=(-Y_HALF, Y_HALF))

    # Measure LOCAL fringe contrast at analytically known positions.
    # Peak at y=0; valley at y=Δy/2.  Global max/min would capture the
    # diffraction envelope shape for both D=0 and D=1, confounding the test.
    bin_centres = (edges[:-1] + edges[1:]) / 2.0

    def counts_near(bin_ctrs, hist, y_target, half_width):
        """Sum of histogram counts in [y_target ± half_width]."""
        mask = np.abs(bin_ctrs - y_target) < half_width
        return hist[mask].sum() if mask.any() else 0

    hw = delta_y * 0.2          # ±20% of fringe spacing — snug window

    # Central fringe peak: y=0
    peak_D0  = counts_near(bin_centres, counts_D0, 0.0,         hw)
    valley_D0 = counts_near(bin_centres, counts_D0, delta_y/2,  hw)
    peak_D1  = counts_near(bin_centres, counts_D1, 0.0,         hw)
    valley_D1 = counts_near(bin_centres, counts_D1, delta_y/2,  hw)

    V_D0 = fringe_visibility(peak_D0, valley_D0) if (peak_D0 + valley_D0) > 0 else 0.0
    V_D1 = fringe_visibility(peak_D1, valley_D1) if (peak_D1 + valley_D1) > 0 else 0.0

    results = [
        ('V(D=0) > 0.60  (fringes visible at N=%d)' % N_TOTAL, V_D0 > 0.60),
        ('V(D=1) < 0.20  (no fringes at N=%d)' % N_TOTAL, V_D1 < 0.20),
        ('V(D=0) > V(D=1)', V_D0 > V_D1),
    ]
    all_pass = True
    for label, ok in results:
        print(f"  {'✓' if ok else '✗'}  {label}")
        if not ok:
            all_pass = False

    print(f"\n  Measured V(D=0) = {V_D0:.3f}  (committed: ~1.000)")
    print(f"  Measured V(D=1) = {V_D1:.3f}  (committed: ~0.000)")

    return all_pass


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    lam_e = de_broglie_electron(E_EV)
    delta_y = fringe_spacing(lam_e, L_SCREEN, D_SLIT)

    print("=" * 65)
    print("  Double-Slit Simulation — quarksum / SSBM")
    print("=" * 65)
    print(f"\n  λ_e(1 eV)    = {lam_e*1e9:.4f} nm  [committed: 1.2264 nm]")
    print(f"  Fringe Δy    = {delta_y*1e3:.4f} mm  [committed: 1.2264 mm]")
    print(f"  N_total      = {N_TOTAL:,} particles")
    print(f"  RNG seed     = {SEED} (reproducible)")

    # ── 1. D=0 buildup ────────────────────────────────────────────────────────
    print("\n[1/4] Buildup: D=0 (no observer)")
    random.seed(SEED)
    plot_buildup(lam_e, D=0.0,
                 label='D=0  No observer (interference expected)',
                 outfile='double_slit_buildup_D0.png')

    # ── 2. D=1 buildup ────────────────────────────────────────────────────────
    print("\n[2/4] Buildup: D=1 (full observer)")
    random.seed(SEED)
    plot_buildup(lam_e, D=1.0,
                 label='D=1  Full observer (no interference expected)',
                 outfile='double_slit_buildup_D1.png')

    # ── 3. Comparison at full N ────────────────────────────────────────────────
    print("\n[3/4] Comparison: D=0 vs D=1 at full N")
    random.seed(SEED)
    plot_comparison(lam_e, outfile='double_slit_compare.png')

    # ── 4. σ-dependence ───────────────────────────────────────────────────────
    print("\n[4/4] SSBM σ-dependence: electron vs neutron")
    random.seed(SEED)
    plot_sigma_dependence(outfile='double_slit_sigma.png')

    # ── 5. Verify against committed predictions ───────────────────────────────
    print("\n[5/4] Verification")
    random.seed(SEED)
    cdf_y0, cdf_P0, _, _ = build_cdf(lam_e, D=0.0)
    cdf_y1, cdf_P1, _, _ = build_cdf(lam_e, D=1.0)
    hits_D0 = fire_particles(N_TOTAL, cdf_y0, cdf_P0)
    hits_D1 = fire_particles(N_TOTAL, cdf_y1, cdf_P1)
    ok = verify_against_predictions(hits_D0, hits_D1, lam_e)

    print("\n" + "=" * 65)
    print(f"  {'✓ ALL CHECKS PASSED' if ok else '✗ SOME CHECKS FAILED'}")
    print("  Output files:")
    for f in ['double_slit_buildup_D0.png', 'double_slit_buildup_D1.png',
              'double_slit_compare.png', 'double_slit_sigma.png']:
        print(f"    {f}")
    print("=" * 65)

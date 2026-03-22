"""
simulate_double_slit_3d.py
============================
3-D timelapse of the double-slit experiment.

Physics is identical to simulate_double_slit.py (same CDF, same Born-rule
sampling, same cascade constants).  This script adds a third axis: time,
measured in particle count N.

SCENE GEOMETRY
──────────────
  X  — screen position y (meters)
  Y  — particle count N (10 → 15 000) — the time axis
  Z  — hit density (normalised per slice)

At small N: only a few random dots — no structure visible.
As N grows: the interference fringes crystallise out of the noise.

For D=0 (no observer): fringes emerge — quantum interference.
For D=1 (full observer): smooth Gaussian envelope only — no fringes.

OUTPUTS
──────────────────────────────────────────
  double_slit_3d_D0.png       — 3-D waterfall: D=0, fringes emerge
  double_slit_3d_D1.png       — 3-D waterfall: D=1, smooth buildup
  double_slit_3d_compare.png  — side-by-side D=0 / D=1
  double_slit_3d_timelapse.gif — animated GIF: 36 frames rotating around
                                  the D=0 pattern as particles accumulate

Run from quarksum root:
  python simulate_double_slit_3d.py
"""

import math
import random
import sys
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401 (registers 3d proj)
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from local_library.interface.quantum import (
    de_broglie_electron,
    build_intensity_profile,
    cumulative_probability,
    sample_hit_position,
    fringe_spacing,
    diffraction_envelope_zero,
)

# ── Match scene parameters from simulate_double_slit.py ───────────────────────
E_EV     = 1.0
D_SLIT   = 100e-9
A_SLIT   = 20e-9
L_SCREEN = 0.10
Y_HALF   = 15e-3
SEED     = 42

SNAPSHOT_N = [10, 50, 100, 300, 1000, 3000, 5000, 10000, 15000]
N_TOTAL    = SNAPSHOT_N[-1]

N_BINS   = 120    # histogram bins across the screen
N_CDF    = 4000   # CDF resolution


# ── Helpers ───────────────────────────────────────────────────────────────────

def build_cdf(wavelength_m, D=0.0):
    y_arr, I_arr = build_intensity_profile(
        D_SLIT, L_SCREEN, wavelength_m, D=D, a=A_SLIT,
        y_min=-Y_HALF, y_max=Y_HALF, n_points=N_CDF
    )
    cdf_y, cdf_P = cumulative_probability(y_arr, I_arr)
    return cdf_y, cdf_P


def fire_particles(N_total, cdf_y, cdf_P):
    """Return list of y_hit positions (meters) for N_total particles."""
    hits = []
    for _ in range(N_total):
        r = random.random()
        hits.append(sample_hit_position(cdf_y, cdf_P, r))
    return hits


def hits_to_density(hits_subset, n_bins=N_BINS):
    """Normalised hit density as a numpy array, one entry per bin."""
    counts, edges = np.histogram(hits_subset, bins=n_bins,
                                 range=(-Y_HALF, Y_HALF))
    total = counts.sum()
    density = counts / max(total, 1)          # normalised so area ≈ 1
    bin_centres = (edges[:-1] + edges[1:]) / 2.0
    return bin_centres, density


# ── Colour mapping — NOT_PHYSICS, display only ────────────────────────────────

def density_to_rgba(density, cmap_name='inferno', alpha=0.85):
    """Map a 1-D density array → RGBA colours per bar."""
    cmap = plt.get_cmap(cmap_name)
    norm = density / max(density.max(), 1e-12)
    return cmap(norm), norm


# ══════════════════════════════════════════════════════════════════════════════
#  Core 3-D waterfall plotter
# ══════════════════════════════════════════════════════════════════════════════

def plot_waterfall_3d(ax, all_hits, wavelength_m, D, cmap_name='inferno',
                      alpha_face=0.82, title=''):
    """
    Draw a 3-D waterfall (ribbon) plot on ax.

    Each ribbon = one snapshot slice.  Ribbons are stacked along the Y axis
    (particle count, log scale for visual clarity).

    Args:
        ax         — Axes3D
        all_hits   — list of all N_TOTAL hit positions (pre-fired)
        wavelength_m — de Broglie wavelength (metres)
        D          — which-path distinguishability
        cmap_name  — matplotlib colourmap (NOT_PHYSICS)
        alpha_face — ribbon opacity
        title      — panel title
    """
    delta_y = fringe_spacing(wavelength_m, L_SCREEN, D_SLIT)
    env_zero = diffraction_envelope_zero(wavelength_m, L_SCREEN, A_SLIT)

    cmap = plt.get_cmap(cmap_name)

    # Log-spaced Y positions for the N axis (visual only, NOT_PHYSICS)
    n_snaps = len(SNAPSHOT_N)
    y_positions = np.log10(np.array(SNAPSHOT_N, dtype=float))   # log₁₀ scale

    verts = []      # list of polygon vertex arrays for Poly3DCollection
    facecolors = []

    for snap_i, N in enumerate(SNAPSHOT_N):
        hits_so_far = all_hits[:N]
        bin_centres, density = hits_to_density(hits_so_far)

        # Scale density to max-across-all-snaps for consistent Z range
        z_vals = density  # normalised per slice; full-N slice sets the scale

        # Build ribbon polygon: bottom edge at z=0, top edge at z=density
        xs = bin_centres
        y_pos = y_positions[snap_i]

        # Each bar → thin quad ribbon in 3D
        dx = (xs[1] - xs[0]) * 0.9    # slight gap between bars — NOT_PHYSICS
        for xi, zi in zip(xs, z_vals):
            # Four corners of the bar: (x, y, z) ordered for Poly3DCollection
            verts.append([
                (xi - dx/2, y_pos, 0),
                (xi - dx/2, y_pos, zi),
                (xi + dx/2, y_pos, zi),
                (xi + dx/2, y_pos, 0),
            ])
            # Colour by density value and snapshot index
            progress = snap_i / max(n_snaps - 1, 1)
            colour = cmap(0.2 + 0.8 * zi / max(density.max(), 1e-12))
            facecolors.append((*colour[:3], alpha_face))

    poly = Poly3DCollection(verts, facecolors=facecolors, linewidths=0.0)
    ax.add_collection3d(poly)

    # ── Axes ──────────────────────────────────────────────────────────────────
    x_mm = np.array([-Y_HALF, Y_HALF]) * 1e3
    ax.set_xlim(x_mm[0], x_mm[1])
    ax.set_ylim(y_positions[0] - 0.2, y_positions[-1] + 0.2)
    ax.set_zlim(0, None)

    # X ticks in mm
    ax.set_xticks(np.arange(-12, 13, 6))
    ax.set_xticklabels([f'{v}mm' for v in np.arange(-12, 13, 6)],
                       fontsize=6, color='#cccccc')

    # Y ticks: particle counts
    ax.set_yticks(y_positions)
    ax.set_yticklabels([f'N={N:,}' for N in SNAPSHOT_N],
                       fontsize=6, color='#cccccc')

    ax.set_zlabel('hit density', fontsize=7, color='#aaaaaa', labelpad=2)

    # Mark fringe spacing and envelope zero
    for k in range(-5, 6):
        yf = k * delta_y * 1e3
        if abs(yf) <= Y_HALF * 1e3:
            ax.plot([yf, yf],
                    [y_positions[0] - 0.15, y_positions[-1] + 0.15],
                    [0, 0],
                    color='#00aaff', lw=0.4, alpha=0.35, zorder=0)

    for sign in [-1, 1]:
        xe = sign * env_zero * 1e3
        if abs(xe) <= Y_HALF * 1e3:
            ax.plot([xe, xe],
                    [y_positions[0] - 0.15, y_positions[-1] + 0.15],
                    [0, 0],
                    color='#ff6600', lw=0.6, alpha=0.4, zorder=0)

    ax.set_title(title, fontsize=9, color='white', pad=4)
    ax.tick_params(axis='z', labelsize=6, colors='#aaaaaa')
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor('#333333')
    ax.yaxis.pane.set_edgecolor('#333333')
    ax.zaxis.pane.set_edgecolor('#333333')
    ax.grid(True, color='#333333', linewidth=0.3)

    return ax


# ── X-axis in mm (the screen must display in mm) ───────────────────────────────
def _mm_axis(ax):
    """Convert x-axis labels from metres to mm for the 3-D axes."""
    # Axis is already set in mm in plot_waterfall_3d (xs * 1e3)
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  Standalone waterfall panels
# ══════════════════════════════════════════════════════════════════════════════

DARK_BG = '#0d0d0d'

def single_panel(all_hits, wavelength_m, D, outfile, cmap_name,
                 elev=22, azim=-55):
    fig = plt.figure(figsize=(10, 7), facecolor=DARK_BG)
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor(DARK_BG)
    fig.patch.set_facecolor(DARK_BG)

    title = ('D=0 — No observer   (quantum interference emerges)' if D == 0.0
             else 'D=1 — Full observer   (no interference, smooth envelope)')

    # X in mm
    hits_mm = [h * 1e3 for h in all_hits]
    plot_waterfall_3d(ax, hits_mm, wavelength_m, D,
                      cmap_name=cmap_name, title=title)

    ax.view_init(elev=elev, azim=azim)

    # Legend annotations
    delta_y = fringe_spacing(wavelength_m, L_SCREEN, D_SLIT)
    env_zero = diffraction_envelope_zero(wavelength_m, L_SCREEN, A_SLIT)
    fig.text(0.02, 0.96,
             f'λ_e = {wavelength_m*1e9:.4f} nm  |  '
             f'Δy = {delta_y*1e3:.4f} mm  |  '
             f'Envelope zero = {env_zero*1e3:.4f} mm',
             color='#88aacc', fontsize=7.5, va='top')
    fig.text(0.02, 0.02,
             '▬  fringe peaks (blue)    |    ▬  envelope zeros (orange)',
             color='#888888', fontsize=6.5, va='bottom')

    plt.tight_layout()
    plt.savefig(outfile, dpi=150, bbox_inches='tight',
                facecolor=DARK_BG, edgecolor='none')
    plt.close()
    print(f'  Saved: {outfile}')


# ══════════════════════════════════════════════════════════════════════════════
#  Side-by-side comparison
# ══════════════════════════════════════════════════════════════════════════════

def comparison_panel(hits_D0, hits_D1, wavelength_m, outfile):
    fig = plt.figure(figsize=(18, 7), facecolor=DARK_BG)
    ax0 = fig.add_subplot(121, projection='3d')
    ax1 = fig.add_subplot(122, projection='3d')
    for ax in (ax0, ax1):
        ax.set_facecolor(DARK_BG)

    hits_D0_mm = [h * 1e3 for h in hits_D0]
    hits_D1_mm = [h * 1e3 for h in hits_D1]

    plot_waterfall_3d(ax0, hits_D0_mm, wavelength_m, D=0.0, cmap_name='inferno',
                      title='D=0  No observer\n(quantum interference)')
    plot_waterfall_3d(ax1, hits_D1_mm, wavelength_m, D=1.0, cmap_name='plasma',
                      title='D=1  Full observer\n(which-path known — no fringes)')

    for ax in (ax0, ax1):
        ax.view_init(elev=22, azim=-55)

    delta_y = fringe_spacing(wavelength_m, L_SCREEN, D_SLIT)
    env_zero = diffraction_envelope_zero(wavelength_m, L_SCREEN, A_SLIT)
    fig.suptitle(
        f'Double-Slit Experiment — SSBM quarksum\n'
        f'λ_e(1 eV) = {wavelength_m*1e9:.4f} nm   '
        f'Δy = {delta_y*1e3:.4f} mm   '
        f'Envelope zero = {env_zero*1e3:.4f} mm\n'
        f'N_total = {N_TOTAL:,}   seed = {SEED}',
        color='white', fontsize=9, y=0.99
    )
    fig.text(0.5, 0.01,
             'Englert duality: D² + V² ≤ 1  |  Born-rule inverse-CDF sampling',
             ha='center', color='#555555', fontsize=7)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(outfile, dpi=150, bbox_inches='tight',
                facecolor=DARK_BG, edgecolor='none')
    plt.close()
    print(f'  Saved: {outfile}')


# ══════════════════════════════════════════════════════════════════════════════
#  Animated GIF — rotating view of the D=0 buildup
# ══════════════════════════════════════════════════════════════════════════════

def animated_timelapse(all_hits, wavelength_m, outfile, n_frames=48):
    """
    Render an animated GIF.  Two phases:
      Phase 1 (first half): particles accumulate, azimuth fixed.
      Phase 2 (second half): N=15000, camera rotates 360°.
    """
    import tempfile, glob

    hits_mm = [h * 1e3 for h in all_hits]
    delta_y = fringe_spacing(wavelength_m, L_SCREEN, D_SLIT)
    env_zero = diffraction_envelope_zero(wavelength_m, L_SCREEN, A_SLIT)

    half = n_frames // 2
    frame_files = []

    # ── Phase 1: particle buildup ──────────────────────────────────────────────
    # Distribute snapshots logarithmically across Phase 1 frames
    N_range = np.logspace(1, np.log10(N_TOTAL), half).astype(int)
    N_range = np.unique(np.clip(N_range, 1, N_TOTAL))

    print(f'  Rendering {n_frames} frames...')

    for frame_i, N in enumerate(N_range):
        fig = plt.figure(figsize=(9, 6), facecolor=DARK_BG)
        ax = fig.add_subplot(111, projection='3d')
        ax.set_facecolor(DARK_BG)
        fig.patch.set_facecolor(DARK_BG)

        subset = hits_mm[:N]

        # Simple density bar chart in 3D for this single snapshot
        bin_centres_mm = np.linspace(-Y_HALF*1e3, Y_HALF*1e3, N_BINS)
        counts, edges = np.histogram(subset, bins=N_BINS,
                                     range=(-Y_HALF*1e3, Y_HALF*1e3))
        density = counts / max(counts.sum(), 1)
        bin_ctrs = (edges[:-1] + edges[1:]) / 2.0

        cmap = plt.get_cmap('inferno')
        max_d = density.max() if density.max() > 0 else 1e-12
        dx = (bin_ctrs[1] - bin_ctrs[0]) * 0.92

        verts = []
        fcs = []
        for xi, zi in zip(bin_ctrs, density):
            verts.append([
                (xi - dx/2, 0, 0),
                (xi - dx/2, 0, zi),
                (xi + dx/2, 0, zi),
                (xi + dx/2, 0, 0),
            ])
            fcs.append(cmap(0.15 + 0.85 * zi / max_d))

        poly = Poly3DCollection(verts, facecolors=fcs, linewidths=0.0)
        ax.add_collection3d(poly)

        # Overlay the theoretical prediction (NOT_PHYSICS display guide)
        from local_library.interface.quantum import build_intensity_profile
        y_th, I_th = build_intensity_profile(
            D_SLIT, L_SCREEN, wavelength_m, D=0.0, a=A_SLIT,
            y_min=-Y_HALF, y_max=Y_HALF, n_points=800
        )
        y_th_mm = np.array(y_th) * 1e3
        I_th_norm = np.array(I_th) / max(max(I_th), 1e-12) * max_d * 1.05
        ax.plot(y_th_mm, np.zeros_like(y_th_mm) - 0.02,
                I_th_norm, color='#00ccff', lw=0.8, alpha=0.55, zorder=10)

        # Fringe markers
        for k in range(-5, 6):
            yf = k * delta_y * 1e3
            if abs(yf) <= Y_HALF * 1e3:
                ax.plot([yf, yf], [-0.1, 0.1], [0, 0],
                        color='#0077cc', lw=0.5, alpha=0.5)

        ax.set_xlim(-Y_HALF*1e3, Y_HALF*1e3)
        ax.set_ylim(-0.5, 0.5)
        ax.set_zlim(0, 0.06)

        ax.set_xlabel('screen position (mm)', fontsize=7, color='#aaaaaa')
        ax.set_zlabel('hit density', fontsize=7, color='#aaaaaa', labelpad=1)
        ax.set_yticks([])
        ax.tick_params(axis='x', labelsize=6, colors='#999999')
        ax.tick_params(axis='z', labelsize=6, colors='#999999')
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor('#222222')
        ax.yaxis.pane.set_edgecolor('#222222')
        ax.zaxis.pane.set_edgecolor('#222222')
        ax.grid(True, color='#222222', linewidth=0.3)
        ax.view_init(elev=20, azim=-60)

        ax.set_title(f'D=0 — No observer\nN = {N:,} particles',
                     color='white', fontsize=9, pad=3)
        fig.text(0.02, 0.97,
                 f'λ_e = {wavelength_m*1e9:.4f} nm  |  Δy = {delta_y*1e3:.4f} mm',
                 color='#6699bb', fontsize=7, va='top')
        fig.text(0.02, 0.03,
                 '── theoretical |ψ(y)|²  (cyan)',
                 color='#555555', fontsize=6.5, va='bottom')

        fpath = f'/tmp/ds3d_frame_{frame_i:04d}.png'
        plt.savefig(fpath, dpi=110, bbox_inches='tight',
                    facecolor=DARK_BG, edgecolor='none')
        plt.close()
        frame_files.append(fpath)

    # ── Phase 2: full N, camera rotation ──────────────────────────────────────
    azim_range = np.linspace(-60, 300, n_frames - len(frame_files))

    for rot_i, azim in enumerate(azim_range):
        frame_i = len(frame_files)
        fig = plt.figure(figsize=(9, 6), facecolor=DARK_BG)
        ax = fig.add_subplot(111, projection='3d')
        ax.set_facecolor(DARK_BG)
        fig.patch.set_facecolor(DARK_BG)

        counts, edges = np.histogram(hits_mm, bins=N_BINS,
                                     range=(-Y_HALF*1e3, Y_HALF*1e3))
        density = counts / max(counts.sum(), 1)
        bin_ctrs = (edges[:-1] + edges[1:]) / 2.0

        cmap = plt.get_cmap('inferno')
        max_d = density.max() if density.max() > 0 else 1e-12
        dx = (bin_ctrs[1] - bin_ctrs[0]) * 0.92

        verts = []
        fcs = []
        for xi, zi in zip(bin_ctrs, density):
            verts.append([
                (xi - dx/2, 0, 0),
                (xi - dx/2, 0, zi),
                (xi + dx/2, 0, zi),
                (xi + dx/2, 0, 0),
            ])
            fcs.append(cmap(0.15 + 0.85 * zi / max_d))

        poly = Poly3DCollection(verts, facecolors=fcs, linewidths=0.0)
        ax.add_collection3d(poly)

        from local_library.interface.quantum import build_intensity_profile
        y_th, I_th = build_intensity_profile(
            D_SLIT, L_SCREEN, wavelength_m, D=0.0, a=A_SLIT,
            y_min=-Y_HALF, y_max=Y_HALF, n_points=800
        )
        y_th_mm = np.array(y_th) * 1e3
        I_th_norm = np.array(I_th) / max(max(I_th), 1e-12) * max_d * 1.05
        ax.plot(y_th_mm, np.zeros_like(y_th_mm) - 0.02,
                I_th_norm, color='#00ccff', lw=1.0, alpha=0.65, zorder=10)

        ax.set_xlim(-Y_HALF*1e3, Y_HALF*1e3)
        ax.set_ylim(-0.5, 0.5)
        ax.set_zlim(0, 0.06)
        ax.set_xlabel('screen position (mm)', fontsize=7, color='#aaaaaa')
        ax.set_zlabel('hit density', fontsize=7, color='#aaaaaa', labelpad=1)
        ax.set_yticks([])
        ax.tick_params(axis='x', labelsize=6, colors='#999999')
        ax.tick_params(axis='z', labelsize=6, colors='#999999')
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor('#222222')
        ax.yaxis.pane.set_edgecolor('#222222')
        ax.zaxis.pane.set_edgecolor('#222222')
        ax.grid(True, color='#222222', linewidth=0.3)
        ax.view_init(elev=22, azim=azim)

        ax.set_title(f'D=0 — No observer\nN = {N_TOTAL:,} — camera rotating',
                     color='white', fontsize=9, pad=3)

        fpath = f'/tmp/ds3d_frame_{frame_i:04d}.png'
        plt.savefig(fpath, dpi=110, bbox_inches='tight',
                    facecolor=DARK_BG, edgecolor='none')
        plt.close()
        frame_files.append(fpath)

    # ── Assemble GIF ──────────────────────────────────────────────────────────
    from PIL import Image
    frames_pil = []
    for fpath in frame_files:
        img = Image.open(fpath).convert('RGB')
        # Quantize for GIF (256 colours) — NOT_PHYSICS
        img_q = img.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
        frames_pil.append(img_q)

    # Buildup phase: 120ms/frame.  Rotation phase: 80ms/frame.
    n_buildup = n_frames // 2
    durations = ([120] * n_buildup) + ([80] * (len(frames_pil) - n_buildup))

    frames_pil[0].save(
        outfile,
        format='GIF',
        save_all=True,
        append_images=frames_pil[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )
    print(f'  Saved: {outfile}  ({len(frames_pil)} frames)')

    # Clean up temp PNGs
    for f in frame_files:
        try:
            os.remove(f)
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    lam_e   = de_broglie_electron(E_EV)
    delta_y = fringe_spacing(lam_e, L_SCREEN, D_SLIT)

    print('=' * 65)
    print('  Double-Slit 3-D Timelapse — quarksum / SSBM')
    print('=' * 65)
    print(f'\n  λ_e(1 eV)    = {lam_e*1e9:.4f} nm')
    print(f'  Fringe Δy    = {delta_y*1e3:.4f} mm')
    print(f'  N_total      = {N_TOTAL:,} particles')
    print(f'  RNG seed     = {SEED}')

    # Fire all particles once, reuse for all plots
    print('\n  Firing particles for D=0...')
    random.seed(SEED)
    cdf_y0, cdf_P0 = build_cdf(lam_e, D=0.0)
    all_hits_D0 = fire_particles(N_TOTAL, cdf_y0, cdf_P0)

    print('  Firing particles for D=1...')
    random.seed(SEED)
    cdf_y1, cdf_P1 = build_cdf(lam_e, D=1.0)
    all_hits_D1 = fire_particles(N_TOTAL, cdf_y1, cdf_P1)

    # ── 3-D waterfall panels ──────────────────────────────────────────────────
    print('\n[1/4] 3-D waterfall: D=0')
    single_panel(all_hits_D0, lam_e, D=0.0,
                 outfile='double_slit_3d_D0.png',
                 cmap_name='inferno')

    print('\n[2/4] 3-D waterfall: D=1')
    single_panel(all_hits_D1, lam_e, D=1.0,
                 outfile='double_slit_3d_D1.png',
                 cmap_name='plasma')

    print('\n[3/4] Side-by-side comparison')
    comparison_panel(all_hits_D0, all_hits_D1, lam_e,
                     outfile='double_slit_3d_compare.png')

    print('\n[4/4] Animated timelapse GIF (buildup + rotation)')
    animated_timelapse(all_hits_D0, lam_e,
                       outfile='double_slit_3d_timelapse.gif',
                       n_frames=48)

    print('\n' + '=' * 65)
    print('  Output files:')
    for f in ['double_slit_3d_D0.png',
              'double_slit_3d_D1.png',
              'double_slit_3d_compare.png',
              'double_slit_3d_timelapse.gif']:
        size = os.path.getsize(f) // 1024 if os.path.exists(f) else 0
        print(f'    {f}  ({size} KB)')
    print('=' * 65)

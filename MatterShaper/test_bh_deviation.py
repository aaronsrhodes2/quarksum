"""
Barnes-Hut θ deviation scan.

Purpose
-------
Measure the EXACT deviation between Barnes-Hut and brute-force N² gravity
as a function of θ, at three particle scales.

This answers two questions the Captain asked:
  1. Is there an optimal θ somewhere between 0 and 1?
  2. Does that optimal shift with scale (scale curve) or is it universal?

If the three scale lines sit on top of each other → θ is scale-independent
→ there MAY be a universal derivable constant.

If they separate → θ has a scale curve → the cascade must supply it
per scale.

Test structure
--------------
  θ scan  : 0.00, 0.05, 0.10, ..., 1.00  (21 values)
  scales  : N = 100, 500, 2000
  metric  : RMS relative force deviation per particle
              δ = |a_BH - a_brute| / |a_brute|   (per particle)
              RMS_δ = sqrt(mean(δ²))
            also: max δ, median δ

Output
------
  misc/bh_deviation.png  — deviation graph  (the one the Captain wants)
  misc/bh_timing.png     — wall time vs θ for each scale

Intentionally failing test
--------------------------
  test_theta_natural_is_derived()

  This test MUST FAIL until THETA_NATURAL is derived from the cascade.
  It is not a broken test.  It is a standing TODO with teeth.
  When it passes, something real has been discovered.

Reference
---------
  Barnes & Hut (1986) Nature 324:446-449.
  θ = 0.5 was chosen empirically, not derived.
"""

import sys, os, math, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

sys.path.insert(0, os.path.dirname(__file__))
from mattershaper.physics.gravity.barnes_hut import (
    QuadTree, brute_force_gravity, barnes_hut_gravity,
    THETA_BH, THETA_NATURAL, EPS_GRAVITY,
)

# ── Intentionally failing test ────────────────────────────────────────────────

def test_theta_natural_is_derived():
    """
    θ must come from the cascade, not from tuning.

    THIS TEST INTENTIONALLY FAILS until THETA_NATURAL is derived from
    the physics of information deresolution at the observer's scale.

    Golden Rule 2: No magic numbers.
    THETA_BH = 0.5 is a magic number.
    THETA_NATURAL = None is the honest statement of that debt.

    When this passes, mark it FIRST_PRINCIPLES with a derivation chain.
    """
    assert THETA_NATURAL is not None, (
        "THETA_NATURAL is not yet derived from the cascade.  "
        "θ = 0.5 (THETA_BH) is a Barnes & Hut (1986) convenience value, "
        "NOT a physics constant.  Derive it from the force noise floor "
        "at the observer's scale before marking this test green.  "
        "See barnes_hut.py — 'THETA_NATURAL' section."
    )


# ── Particle set generation ───────────────────────────────────────────────────

def make_particles(N, seed=42):
    """Generate N particles with unit mass in [0,1]².

    Uses a clustered distribution (not uniform) so the tree has
    interesting structure — uniform gives an unrepresentative easy case.
    FIRST_PRINCIPLES: gravitational clustering is the natural state of
    N-body systems; clusters stress the θ criterion more than uniform grids.
    """
    rng = np.random.default_rng(seed)
    # Three clusters + background scatter
    n_cluster = int(N * 0.6)
    n_back    = N - n_cluster
    centres   = rng.uniform(0.1, 0.9, (3, 2))
    n_each    = n_cluster // 3

    xs = []; ys = []
    for cx, cy in centres:
        xs.append(rng.normal(cx, 0.05, n_each))
        ys.append(rng.normal(cy, 0.05, n_each))
    # Background
    xs.append(rng.uniform(0, 1, n_back))
    ys.append(rng.uniform(0, 1, n_back))

    rx   = np.clip(np.concatenate(xs)[:N], 0.001, 0.999)
    ry   = np.clip(np.concatenate(ys)[:N], 0.001, 0.999)
    mass = np.ones(N)
    return rx, ry, mass


# ── Deviation measurement ─────────────────────────────────────────────────────

def deviation(ax_bh, ay_bh, ax_bf, ay_bf):
    """Per-particle relative force deviation.

    δᵢ = |a_BH - a_brute|ᵢ / (|a_brute|ᵢ + tiny)

    Returns (rms, max, median) of δ across all particles.
    """
    a_bh = np.sqrt(ax_bh**2 + ay_bh**2)
    a_bf = np.sqrt(ax_bf**2 + ay_bf**2)
    diff = np.sqrt((ax_bh - ax_bf)**2 + (ay_bh - ay_bf)**2)
    denom = a_bf + 1e-12 * a_bf.max()
    delta = diff / denom
    return float(np.sqrt(np.mean(delta**2))), float(delta.max()), float(np.median(delta))


# ── Main scan ─────────────────────────────────────────────────────────────────

def run_scan():
    THETAS  = np.linspace(0.0, 1.0, 21)
    SCALES  = [100, 500, 2000]
    G       = 1.0
    EPS     = EPS_GRAVITY
    COLORS  = ['#4fc3f7', '#aed581', '#ffb74d']   # cyan, green, orange
    SEED    = 42

    results = {}   # {N: {'rms': [...], 'max': [...], 'time_bh': [...], 'time_bf': float}}

    print("═" * 64)
    print("  Barnes-Hut θ deviation scan")
    print("═" * 64)

    for N in SCALES:
        rx, ry, mass = make_particles(N, seed=SEED)

        # Brute force ground truth (once per N)
        t0 = time.perf_counter()
        ax_bf, ay_bf = brute_force_gravity(rx, ry, mass, G=G, eps=EPS)
        t_bf = time.perf_counter() - t0

        rms_list = []; max_list = []; med_list = []; t_bh_list = []

        print(f"\n  N = {N:>5}  (brute-force: {t_bf*1000:.1f} ms)")
        print(f"  {'θ':>6}  {'RMS%':>8}  {'Max%':>8}  {'Med%':>8}  {'BH ms':>8}")
        print("  " + "-"*52)

        for theta in THETAS:
            t0 = time.perf_counter()
            ax_bh, ay_bh = barnes_hut_gravity(rx, ry, mass,
                                              theta=theta, G=G, eps=EPS)
            t_bh = time.perf_counter() - t0

            rms, mx, med = deviation(ax_bh, ay_bh, ax_bf, ay_bf)
            rms_list.append(rms * 100)
            max_list.append(mx  * 100)
            med_list.append(med * 100)
            t_bh_list.append(t_bh * 1000)

            marker = " ← BH standard" if abs(theta - 0.5) < 0.01 else ""
            print(f"  {theta:>6.2f}  {rms*100:>7.3f}%  {mx*100:>7.2f}%  "
                  f"{med*100:>7.3f}%  {t_bh*1000:>7.2f}ms{marker}")

        results[N] = {
            'rms':  rms_list,
            'max':  max_list,
            'med':  med_list,
            'tbh':  t_bh_list,
            't_bf': t_bf * 1000,
        }

    return THETAS, SCALES, results, COLORS


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_results(THETAS, SCALES, results, COLORS, out_dir):

    # ── Figure 1: deviation curves ────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 6),
                             facecolor='#0d0d0d')
    fig.suptitle("Barnes-Hut θ Deviation — BH vs Full N² Sum",
                 color='white', fontsize=14, y=0.98)

    ax_rms = axes[0];  ax_max = axes[1]

    for ax in axes:
        ax.set_facecolor('#111111')
        ax.tick_params(colors='#aaaaaa', labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor('#333333')
        ax.grid(True, color='#222222', linewidth=0.5)
        ax.set_xlabel('θ  (opening angle)', color='#aaaaaa', fontsize=10)
        ax.axvline(x=0.5, color='#ff6666', linewidth=1.2, linestyle='--', alpha=0.7)
        ax.text(0.51, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 1,
                '0.5\n(BH 1986)', color='#ff6666', fontsize=7, va='top')

    for i, N in enumerate(SCALES):
        r = results[N]
        ax_rms.semilogy(THETAS, r['rms'], color=COLORS[i], linewidth=2,
                        marker='o', markersize=3, label=f'N = {N}')
        ax_max.semilogy(THETAS, r['max'], color=COLORS[i], linewidth=2,
                        marker='o', markersize=3, label=f'N = {N}')

    # 1% and 0.1% reference lines
    for ax in axes:
        ax.axhline(y=1.0,  color='#ffffff', linewidth=0.6, linestyle=':',  alpha=0.4)
        ax.axhline(y=0.1,  color='#aaaaaa', linewidth=0.6, linestyle=':',  alpha=0.3)
        ax.text(0.02, 1.0,  '1%',   color='#888888', fontsize=7, va='bottom',
                transform=ax.get_yaxis_transform())
        ax.text(0.02, 0.1,  '0.1%', color='#666666', fontsize=7, va='bottom',
                transform=ax.get_yaxis_transform())

    ax_rms.set_title('RMS relative deviation', color='#cccccc', fontsize=11)
    ax_rms.set_ylabel('Force deviation (%)', color='#aaaaaa', fontsize=10)
    ax_max.set_title('Max relative deviation (worst particle)', color='#cccccc', fontsize=11)
    ax_max.set_ylabel('Force deviation (%)', color='#aaaaaa', fontsize=10)

    for ax in axes:
        leg = ax.legend(fontsize=9, facecolor='#1a1a1a', edgecolor='#333333',
                        labelcolor='white')

    # Annotation: THETA_NATURAL pending
    fig.text(0.5, 0.01,
             "THETA_NATURAL = None  |  test_theta_natural_is_derived() → INTENTIONAL FAIL"
             "  |  Golden Rule 2: No magic numbers.",
             ha='center', color='#ff6666', fontsize=8, style='italic')

    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    out1 = os.path.join(out_dir, 'bh_deviation.png')
    fig.savefig(out1, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"\n  Deviation graph → {out1}")

    # ── Figure 2: timing ──────────────────────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(9, 5), facecolor='#0d0d0d')
    ax2.set_facecolor('#111111')
    ax2.tick_params(colors='#aaaaaa', labelsize=9)
    for spine in ax2.spines.values():
        spine.set_edgecolor('#333333')
    ax2.grid(True, color='#222222', linewidth=0.5)
    ax2.set_xlabel('θ', color='#aaaaaa', fontsize=10)
    ax2.set_ylabel('Wall time (ms)', color='#aaaaaa', fontsize=10)
    ax2.set_title('Barnes-Hut step time vs θ', color='#cccccc', fontsize=12)

    for i, N in enumerate(SCALES):
        r = results[N]
        ax2.plot(THETAS, r['tbh'], color=COLORS[i], linewidth=2,
                 marker='o', markersize=3, label=f'N={N} BH')
        ax2.axhline(y=r['t_bf'], color=COLORS[i], linewidth=1,
                    linestyle='--', alpha=0.5, label=f'N={N} brute')

    ax2.axvline(x=0.5, color='#ff6666', linewidth=1.2, linestyle='--', alpha=0.7)
    leg2 = ax2.legend(fontsize=9, facecolor='#1a1a1a', edgecolor='#333333',
                      labelcolor='white', ncol=2)

    plt.tight_layout()
    out2 = os.path.join(out_dir, 'bh_timing.png')
    fig2.savefig(out2, dpi=150, facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"  Timing graph   → {out2}")

    return out1, out2


# ── Summary analysis ──────────────────────────────────────────────────────────

def analyse(THETAS, SCALES, results):
    print("\n── Analysis ─────────────────────────────────────────────────")

    # At θ=0.5 (the dumb number)
    idx_half = np.argmin(np.abs(THETAS - 0.5))
    print(f"\n  At θ = 0.50 (THETA_BH — NOT_PHYSICS):")
    for N in SCALES:
        rms = results[N]['rms'][idx_half]
        mx  = results[N]['max'][idx_half]
        print(f"    N={N:>5}: RMS={rms:.3f}%  Max={mx:.2f}%")

    # Find θ where RMS first exceeds 1% for each N
    print(f"\n  θ at which RMS deviation first exceeds 1%:")
    for N in SCALES:
        rms = results[N]['rms']
        cross = next((THETAS[j] for j, v in enumerate(rms) if v > 1.0), None)
        print(f"    N={N:>5}: θ ≈ {cross:.2f}" if cross else
              f"    N={N:>5}: never exceeds 1% in 0–1 range")

    # Scale curve check: do the RMS curves coincide?
    # Compare N=100 vs N=2000 at each θ
    if len(SCALES) >= 2:
        rms_small = np.array(results[SCALES[ 0]]['rms'])
        rms_large = np.array(results[SCALES[-1]]['rms'])
        # Avoid log(0)
        valid = (rms_small > 0) & (rms_large > 0)
        if valid.any():
            spread = np.max(np.abs(np.log10(rms_large[valid]+1e-6)
                                   - np.log10(rms_small[valid]+1e-6)))
            scale_dependent = spread > 0.3   # 1 order of magnitude = scale curve
            print(f"\n  Scale curve check (N={SCALES[0]} vs N={SCALES[-1]}):")
            print(f"    Max log10 spread: {spread:.2f}")
            print(f"    Conclusion: θ is {'SCALE-DEPENDENT' if scale_dependent else 'SCALE-INDEPENDENT'}")
            if scale_dependent:
                print("    → optimal θ shifts with N → cascade must supply θ(scale)")
            else:
                print("    → θ may be derivable as a universal constant")

    print(f"\n  THETA_NATURAL = {THETA_NATURAL}  (FAILING TEST — derivation pending)")
    print("═" * 64)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'misc')
    os.makedirs(out_dir, exist_ok=True)

    THETAS, SCALES, results, COLORS = run_scan()
    out1, out2 = plot_results(THETAS, SCALES, results, COLORS, out_dir)
    analyse(THETAS, SCALES, results)

    # Run the intentionally-failing test so it prints clearly
    print("\n── Intentional fail test ────────────────────────────────────")
    try:
        test_theta_natural_is_derived()
        print("  test_theta_natural_is_derived: ✓ PASS  ← THIS SHOULD NOT HAPPEN")
    except AssertionError as e:
        print(f"  test_theta_natural_is_derived: ✗ INTENTIONAL FAIL")
        print(f"  {str(e)[:120]}...")

    from mattershaper.physics.gravity.barnes_hut import THETA_NATURAL
    print(f"\n  THETA_NATURAL = {THETA_NATURAL}")
    print("  Mark this green only when the derivation chain is complete.")
    print("═" * 64)

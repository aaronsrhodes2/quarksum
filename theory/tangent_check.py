#!/usr/bin/env python3
"""Tangent Check: Do the σ curves meet smoothly at the junction?

We have two σ(T) curves:
  BH side:     σ_grav(T_virial) — gravitational σ as the collapse heats up
  Cosmic side: σ_cosmic(T) = ξ ln(T/Λ_QCD) — thermal σ as the universe cools

Both are functions of temperature. At the overlap point (~203 GeV),
the VALUES match (σ ≈ 1.085). But do the SLOPES match?

If dσ/dT is the same from both sides → C¹ continuity (tangent match).
If only σ matches but slopes differ → C⁰ only (curves cross or kink).

This is the difference between a smooth handoff and a coincidence.
"""

import sys
import math

sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/quarksum")
sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/Materia/qamss")

from materia.core.constants import CONSTANTS
from materia.core.cosmology import COSMOLOGY
from materia.core.scale_field import (
    XI_SSBM, LAMBDA_QCD_GEV,
    sigma_at_radius_combined, lambda_eff_gev,
)
from materia.models.black_hole import schwarzschild_radius_m, M_SUN_KG
from materia.models.bh_formation import run_formation
from materia.models.cosmic_evolution import sigma_cosmic

c = CONSTANTS.c
c2 = c ** 2
G = CONSTANTS.G
k_B = CONSTANTS.k_B
eV = CONSTANTS.eV
m_p = CONSTANTS.m_p

MASS_SOLAR = 10.0
M_KG = MASS_SOLAR * M_SUN_KG
R_S = schwarzschild_radius_m(M_KG)


def main():
    print("=" * 100)
    print("TANGENT CHECK: Are the σ curves smooth through the junction?")
    print("=" * 100)
    print()

    # ── 1. Get σ(T) from the BH formation ──────────────────────────────
    print("Extracting σ(T_virial) from BH formation snapshots...")
    snapshots = run_formation(
        mass_solar=MASS_SOLAR,
        n_points=2000,   # high resolution for derivative
        R_start_factor=100.0,
        R_end_factor=1e-14,
    )

    # Extract σ_center and virial temperature from each snapshot
    bh_sigma_T = []
    for s in snapshots:
        sigma = s.ssbm.sigma_center
        T_K = s.ssbm.temperature_K
        T_GeV = T_K * k_B / (eV * 1e9) if T_K > 0 else 0
        if T_GeV > 0 and sigma > 0:
            bh_sigma_T.append((T_GeV, sigma))

    # Sort by temperature
    bh_sigma_T.sort(key=lambda x: x[0])

    print(f"  {len(bh_sigma_T)} points with σ > 0 and T > 0")
    print(f"  T range: {bh_sigma_T[0][0]:.4e} — {bh_sigma_T[-1][0]:.4e} GeV")
    print(f"  σ range: {bh_sigma_T[0][1]:.6f} — {bh_sigma_T[-1][1]:.6f}")
    print()

    # ── 2. Get σ(T) from the cosmic formula ────────────────────────────
    print("Computing σ_cosmic(T) = ξ ln(T/Λ_QCD)...")
    print(f"  ξ = {XI_SSBM}, Λ_QCD = {LAMBDA_QCD_GEV} GeV")
    print()

    # Analytical derivative:
    # σ_cosmic(T) = ξ ln(T/Λ_QCD)
    # dσ_cosmic/dT = ξ / T
    print(f"  dσ_cosmic/dT = ξ/T = {XI_SSBM}/T")
    print()

    # ── 3. Find the overlap region ─────────────────────────────────────
    # The overlap is where σ_BH ≈ σ_cosmic
    target_sigma = None
    for T_bh, sigma_bh in bh_sigma_T:
        sigma_cos = sigma_cosmic(T_bh)
        if sigma_cos > 0 and abs(sigma_bh - sigma_cos) < 0.1:
            target_sigma = sigma_bh
            break

    # More carefully: find where |σ_BH(T) - σ_cosmic(T)| is minimized
    # But these curves are parameterized differently:
    # BH: as collapse proceeds, BOTH T and σ increase
    # Cosmic: as time proceeds, BOTH T decreases and σ decreases
    # So we compare σ_BH at T_BH vs σ_cosmic at T_cosmic where σ values match

    # Let's just tabulate both curves near σ ≈ 1.085
    print("=" * 100)
    print("σ(T) FROM BOTH SIDES — NEAR THE OVERLAP")
    print("=" * 100)
    print()

    # BH side: show σ and T around the overlap
    print("  BH FORMATION: σ_grav(T_virial)")
    print(f"  {'T (GeV)':>14s} {'σ_grav':>12s} {'σ_cosmic(T)':>14s} {'Δσ':>12s}")
    print(f"  {'─'*14} {'─'*12} {'─'*14} {'─'*12}")

    # Filter to show points near σ ≈ 1.085 ± 0.5
    near_overlap_bh = [(T, s) for T, s in bh_sigma_T if 0.5 < s < 1.6]
    step = max(1, len(near_overlap_bh) // 25)
    for i, (T, sigma) in enumerate(near_overlap_bh):
        if i % step == 0 or i == len(near_overlap_bh) - 1:
            sigma_cos = sigma_cosmic(T)
            delta = sigma - sigma_cos
            marker = " ← OVERLAP" if abs(delta) < 0.05 else ""
            print(f"  {T:>14.6e} {sigma:>12.6f} {sigma_cos:>14.6f} {delta:>12.6f}{marker}")

    print()

    # ── 4. Compute derivatives at the overlap ──────────────────────────
    print("=" * 100)
    print("DERIVATIVE ANALYSIS AT THE OVERLAP")
    print("=" * 100)
    print()

    # For the BH side, compute dσ/dT numerically from the snapshots
    # Find the point closest to σ = 1.085
    target = 1.085
    best_idx = min(range(len(bh_sigma_T)),
                   key=lambda i: abs(bh_sigma_T[i][1] - target))

    # Use central difference with neighbors
    if best_idx > 0 and best_idx < len(bh_sigma_T) - 1:
        T_lo, s_lo = bh_sigma_T[best_idx - 1]
        T_hi, s_hi = bh_sigma_T[best_idx + 1]
        T_mid, s_mid = bh_sigma_T[best_idx]

        dsdT_bh = (s_hi - s_lo) / (T_hi - T_lo)
        T_overlap_bh = T_mid
        sigma_overlap_bh = s_mid
    else:
        print("  Cannot compute BH derivative — overlap at boundary")
        return

    # For the cosmic side: dσ/dT = ξ / T (analytical)
    # At which T does σ_cosmic = target?
    # σ_cosmic = ξ ln(T/Λ_QCD) = target
    # T = Λ_QCD × exp(target / ξ)
    T_overlap_cos = LAMBDA_QCD_GEV * math.exp(target / XI_SSBM)
    dsdT_cos = XI_SSBM / T_overlap_cos

    print(f"  AT THE OVERLAP (σ ≈ {target}):")
    print()
    print(f"  BH SIDE (gravitational):")
    print(f"    T_virial at σ={target}:       {T_overlap_bh:.6e} GeV")
    print(f"    σ_grav:                        {sigma_overlap_bh:.6f}")
    print(f"    dσ_grav/dT (numerical):        {dsdT_bh:.6e} GeV⁻¹")
    print()
    print(f"  COSMIC SIDE (thermal):")
    print(f"    T at σ_cosmic={target}:        {T_overlap_cos:.6e} GeV")
    print(f"    σ_cosmic:                      {target:.6f}")
    print(f"    dσ_cosmic/dT = ξ/T:            {dsdT_cos:.6e} GeV⁻¹")
    print()

    # ── 5. The verdict ─────────────────────────────────────────────────
    ratio = dsdT_bh / dsdT_cos if dsdT_cos != 0 else float('inf')

    print(f"  SLOPE RATIO: dσ_BH/dT ÷ dσ_cosmic/dT = {ratio:.6f}")
    print()

    if abs(ratio - 1.0) < 0.05:
        print("  ✓ C¹ MATCH — curves are TANGENT at the junction")
        print("    The slopes agree to within 5%.")
        print("    This is a smooth handoff, not just a crossing.")
    elif abs(ratio - 1.0) < 0.3:
        print("  ~ APPROXIMATE tangent — slopes are similar but not identical")
        print(f"    Ratio = {ratio:.4f} (would need 1.0 for exact tangent)")
    else:
        print("  ✗ NOT tangent — curves CROSS at the junction")
        print(f"    Slope ratio = {ratio:.4f}")
        print("    The σ values match but the curves approach differently.")
        print("    This is C⁰ (values match) but NOT C¹ (slopes don't).")

    print()

    # ── 6. But wait — are they even the SAME curve? ───────────────────
    print("=" * 100)
    print("DEEPER: ARE THEY THE SAME FUNCTION?")
    print("=" * 100)
    print()

    # The BH σ comes from: σ = f(Φ/c²) where Φ is gravitational potential
    # Specifically: σ ~ ξ × Φ/(c²) at the potential-based level
    # or from the combined formula: sigma_at_radius_combined(R, M)
    #
    # The cosmic σ comes from: σ = ξ ln(T/Λ_QCD)
    #
    # If the conversion IDENTIFIES gravitational potential with thermal energy:
    #   Φ/c² ↔ ln(T/Λ_QCD)
    # then dσ/dT should be the same because they're the same function.

    # Let's check: what is σ_BH as a function of T_virial?
    # T_virial = G M m_p / (5 k_B R)
    # σ_grav = sigma_at_radius_combined(R, M)
    # If σ_grav ∝ ln(T_virial/T_0) for some T_0, then they'd match.

    # Fit log model to BH data: σ_BH = A × ln(T/T_0) ?
    # Use least squares on σ = A ln(T) + B
    from math import log
    n = len(bh_sigma_T)
    sum_lnT = sum(log(T) for T, _ in bh_sigma_T)
    sum_s = sum(s for _, s in bh_sigma_T)
    sum_lnT2 = sum(log(T)**2 for T, _ in bh_sigma_T)
    sum_s_lnT = sum(s * log(T) for T, s in bh_sigma_T)

    A_fit = (n * sum_s_lnT - sum_lnT * sum_s) / (n * sum_lnT2 - sum_lnT**2)
    B_fit = (sum_s - A_fit * sum_lnT) / n

    # Compare: σ_cosmic = ξ ln(T) - ξ ln(Λ_QCD) = ξ ln(T) + ξ × (-ln(Λ_QCD))
    # So cosmic has A = ξ = 0.1582, B = -ξ ln(Λ_QCD)
    B_cosmic = -XI_SSBM * log(LAMBDA_QCD_GEV)

    print(f"  Fitting σ_BH(T) = A × ln(T) + B to the BH formation data:")
    print(f"    A_fit = {A_fit:.6f}    (cosmic: A = ξ = {XI_SSBM})")
    print(f"    B_fit = {B_fit:.6f}    (cosmic: B = -ξ ln(Λ_QCD) = {B_cosmic:.6f})")
    print()
    print(f"  RATIO of log-slopes: A_BH / A_cosmic = {A_fit / XI_SSBM:.6f}")
    print()

    # Compute fit residuals
    residuals = [s - (A_fit * log(T) + B_fit) for T, s in bh_sigma_T]
    rms = (sum(r**2 for r in residuals) / len(residuals)) ** 0.5

    print(f"  Fit quality: RMS residual = {rms:.6f}")
    print(f"  (If this is small, σ_BH really is a log function of T)")
    print()

    if abs(A_fit / XI_SSBM - 1.0) < 0.1:
        print("  ✓ σ_BH(T) ≈ ξ ln(T) + const — SAME FUNCTIONAL FORM as σ_cosmic")
        print(f"    The curves aren't just tangent at one point —")
        print(f"    they're the SAME CURVE (shifted vertically).")
        print(f"    The offset comes from different reference scales:")
        print(f"      Cosmic:  σ = ξ ln(T/Λ_QCD)")
        print(f"      BH fit:  σ ≈ {A_fit:.4f} ln(T) + {B_fit:.4f}")
        T0_bh = math.exp(-B_fit / A_fit)
        print(f"             = {A_fit:.4f} ln(T/{T0_bh:.4e} GeV)")
        print(f"    Cosmic reference: Λ_QCD = {LAMBDA_QCD_GEV} GeV")
        print(f"    BH reference:     T_0   = {T0_bh:.4e} GeV")
        print(f"    Ratio: T_0/Λ_QCD = {T0_bh / LAMBDA_QCD_GEV:.4f}")
    elif abs(A_fit / XI_SSBM - 1.0) < 0.5:
        print(f"  ~ Similar functional form but different coefficient")
        print(f"    A_BH/ξ = {A_fit / XI_SSBM:.4f}")
    else:
        print(f"  ✗ Different functional form")
        print(f"    σ_BH is NOT well-described by ξ ln(T)")
        print(f"    A_BH/ξ = {A_fit / XI_SSBM:.4f}")

    print()
    print("=" * 100)


if __name__ == "__main__":
    main()

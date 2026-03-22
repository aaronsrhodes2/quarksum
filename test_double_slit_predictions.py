"""
test_double_slit_predictions.py
================================
Analytical predictions for the double-slit experiment.

ALL predictions are committed here BEFORE simulate_double_slit.py is written.
The simulation must match these numbers. If it doesn't, the simulation is wrong.

This file has no random numbers. No simulation. Pure first-principles calculation
from our cascade (constants.py, nucleon.py) via quantum.py.

Run this to see what the screen MUST look like:
    python test_double_slit_predictions.py

──────────────────────────────────────────────────────────────────────────────
SCENE PARAMETERS
──────────────────────────────────────────────────────────────────────────────

  Particle:    electron (σ-invariant mass)
  Energy:      1.0 eV  (slow, cold electrons → large λ → visible fringes)
  Slits:       d = 100 nm separation, a = 20 nm width
  Screen:      L = 0.10 m from slits, spans ±15 mm

Derived:
  λ_e          ≈ 1.226 nm
  Fringe Δy    ≈ 1.226 mm
  Envelope 0   ≈ 6.13 mm  (first diffraction dark band)
  Fringes      ≈ 10 under central maximum

──────────────────────────────────────────────────────────────────────────────
SSBM PREDICTION (neutrons, σ ≠ 0)
──────────────────────────────────────────────────────────────────────────────

  At σ = +0.10:  m_n increases (QCD binding stronger)
                 λ_n shrinks  → fringes compress
                 Δy_n(σ)/Δy_n(0) = √(m_n(0)/m_n(σ))  ← directly measurable

  Electron fringes: unchanged (Higgs mass, σ-invariant)
  Neutron fringes:  compressed by ~4.9% per unit σ

──────────────────────────────────────────────────────────────────────────────
"""

import math
import sys
import os

# Run from the quarksum root: python test_double_slit_predictions.py
sys.path.insert(0, os.path.dirname(__file__))

from local_library.interface.quantum import (
    de_broglie_electron,
    de_broglie_neutron,
    fringe_spacing,
    diffraction_envelope_zero,
    fringe_count_in_envelope,
    double_slit_intensity,
    fringe_visibility,
    visibility_from_D,
    englert_bound_satisfied,
    neutron_fringe_spacing_ratio,
    fringe_compression_per_sigma,
    build_intensity_profile,
    M_ELECTRON_KG,
    H_PLANCK,
)
from local_library.nucleon import neutron_mass_mev, proton_mass_mev
from local_library.constants import L_PLANCK   # universe's own "almost zero"

# ── Scene parameters (fixed for all tests) ────────────────────────────────────

E_EV       = 1.0          # electron-volts
D_SLIT     = 100e-9       # m  — slit center-to-center separation
A_SLIT     = 20e-9        # m  — slit width
L_SCREEN   = 0.10         # m  — slit-to-screen distance
Y_HALF     = 15e-3        # m  — screen half-width

PASS  = "✓ PASS"
FAIL  = "✗ FAIL"

_failures = []


def check(label, value, expected, tol_frac=0.005):
    """Assert value ≈ expected within tolerance. Print result.

    When expected == 0: switches automatically to absolute tolerance
    (tol_frac is reinterpreted as the maximum absolute value allowed).
    This avoids division-by-zero in percentage-error calculations and
    lets callers write check("V=0", result, 0.0, tol_frac=0.05) naturally.
    """
    if abs(expected) < L_PLANCK:
        # Zero-expected: absolute tolerance
        err_abs = abs(value - expected)
        ok = err_abs <= tol_frac
        status = PASS if ok else FAIL
        print(f"  {status}  {label}")
        print(f"         got {value:.6g}  expected {expected:.6g}  "
              f"(absolute error {err_abs:.3g}, tol {tol_frac:.3g})")
    else:
        err = abs(value - expected) / abs(expected)
        ok = err <= tol_frac
        status = PASS if ok else FAIL
        print(f"  {status}  {label}")
        print(f"         got {value:.6g}  expected {expected:.6g}  "
              f"({err*100:.3f}% error, tol {tol_frac*100:.1f}%)")
    if not ok:
        _failures.append(label)
    return ok


def section(title):
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}")


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — Constants from cascade
# ══════════════════════════════════════════════════════════════════════════════

section("1. Cascade constants sanity")

# h = 2π ℏ
H_EXPECTED = 6.62607015e-34   # J·s (2019 SI exact)
check("Planck constant h (J·s)", H_PLANCK, H_EXPECTED, tol_frac=1e-8)

# Electron mass in kg from MeV conversion
M_E_EXPECTED = 9.1093837015e-31  # kg (CODATA 2018)
check("Electron mass (kg) from cascade MeV", M_ELECTRON_KG, M_E_EXPECTED, tol_frac=1e-5)

# Neutron mass at σ=0
M_N_MEV_0 = neutron_mass_mev(0.0)
M_N_EXPECTED_MEV = 939.565   # MeV (PDG)
check("Neutron mass at σ=0 (MeV)", M_N_MEV_0, M_N_EXPECTED_MEV, tol_frac=0.001)


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — de Broglie wavelengths
# ══════════════════════════════════════════════════════════════════════════════

section("2. de Broglie wavelengths")

# Electron at 1 eV
# λ = h / √(2 m_e E)  =  6.626e-34 / √(2 × 9.109e-31 × 1.602e-19)
# numerically: ≈ 1.2264e-9 m
lam_e = de_broglie_electron(E_EV)
lam_e_expected = H_PLANCK / math.sqrt(2 * M_ELECTRON_KG * E_EV * 1.602176634e-19)
check("λ_electron at 1 eV (m)", lam_e, lam_e_expected, tol_frac=1e-9)
print(f"         λ_e = {lam_e*1e9:.4f} nm")

# Neutron at 1 eV (much heavier → much smaller λ)
lam_n_0 = de_broglie_neutron(E_EV, sigma=0.0)
from local_library.interface.quantum import mev_to_kg
m_n_kg = mev_to_kg(neutron_mass_mev(0.0))
lam_n_expected = H_PLANCK / math.sqrt(2 * m_n_kg * E_EV * 1.602176634e-19)
check("λ_neutron at σ=0, 1 eV (m)", lam_n_0, lam_n_expected, tol_frac=1e-9)
print(f"         λ_n = {lam_n_0*1e12:.4f} pm")

# Mass ratio: electron ~1836× lighter than neutron → λ_e / λ_n = √(m_n/m_e)
mass_ratio = m_n_kg / M_ELECTRON_KG
lam_ratio  = lam_e / lam_n_0
check("λ_e / λ_n = √(m_n/m_e)", lam_ratio, math.sqrt(mass_ratio), tol_frac=1e-6)


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — Fringe geometry (electrons at 1 eV, our scene)
# ══════════════════════════════════════════════════════════════════════════════

section("3. Fringe geometry: electron, 1 eV, d=100nm, a=20nm, L=10cm")

delta_y = fringe_spacing(lam_e, L_SCREEN, D_SLIT)
print(f"\n  Fringe spacing Δy = {delta_y*1e3:.4f} mm")

# Δy = λL/d
delta_y_analytic = lam_e * L_SCREEN / D_SLIT
check("Fringe spacing Δy (m)", delta_y, delta_y_analytic, tol_frac=1e-9)

# First diffraction zero
y_zero = diffraction_envelope_zero(lam_e, L_SCREEN, A_SLIT)
y_zero_analytic = lam_e * L_SCREEN / A_SLIT
check("Envelope first zero (m)", y_zero, y_zero_analytic, tol_frac=1e-9)
print(f"         First zero at y = {y_zero*1e3:.4f} mm")

# Fringe count under central maximum: 2d/a
n_fringes = fringe_count_in_envelope(D_SLIT, A_SLIT)
check("Fringes under central max (count)", n_fringes, 2.0 * D_SLIT / A_SLIT, tol_frac=1e-9)
print(f"         ~ {n_fringes:.0f} fringes under central diffraction lobe")


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — Intensity profile: key values
# ══════════════════════════════════════════════════════════════════════════════

section("4. Intensity profile: specific points")

k = 2.0 * math.pi / lam_e

# Central maximum (y=0): both slits equidistant → constructive
# r1 = r2 = √(L² + (d/2)²) ≈ L for d << L
# Phase difference = 0 → P ∝ |2A|² = 4|A|²
I_centre = double_slit_intensity(0.0, D_SLIT, L_SCREEN, lam_e, D=0.0)
print(f"\n  I(y=0, D=0) = {I_centre:.6g}")

# First fringe minimum: path difference = λ/2 → destructive
# sin(θ_min) = λ/(2d) → y_min ≈ λL/(2d) = Δy/2
y_min1 = delta_y / 2.0
I_min1 = double_slit_intensity(y_min1, D_SLIT, L_SCREEN, lam_e, D=0.0)
print(f"  I(y=Δy/2, D=0) = {I_min1:.6g}  (should be near zero)")

# Ratio I_centre / I_at_half_fringe >> 1 for good contrast
contrast_ratio = I_centre / max(I_min1, 1e-30)
print(f"  Contrast ratio I(0)/I(Δy/2) = {contrast_ratio:.2f}")
ok = contrast_ratio > 5.0
print(f"  {'✓ PASS' if ok else '✗ FAIL'}  Contrast ratio > 5 (expect >> 1 for clean fringes)")
if not ok:
    _failures.append("Contrast ratio at first minimum")

# With D=1: fringes vanish. Measure LOCAL contrast at y=0 vs y=Δy/2.
# Global max/min would measure the diffraction envelope, not fringes.
# At y=0: I_D1(0) = |A1|² + |A2|² (no cross term)
# At y=Δy/2: I_D1(Δy/2) ≈ same (incoherent term barely changes over half fringe)
# → local V = (I(0)-I(Δy/2))/(I(0)+I(Δy/2)) ≈ 0
I_d1_centre = double_slit_intensity(0.0, D_SLIT, L_SCREEN, lam_e, D=1.0, a=A_SLIT)
I_d1_half   = double_slit_intensity(y_min1, D_SLIT, L_SCREEN, lam_e, D=1.0, a=A_SLIT)
V_local_d1  = fringe_visibility(I_d1_centre, I_d1_half)
check("Local fringe visibility with D=1 (y=0 vs y=Δy/2)", V_local_d1, 0.0, tol_frac=0.05)


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — Fringe visibility vs D (Englert duality)
# ══════════════════════════════════════════════════════════════════════════════

section("5. Englert duality  D² + V² ≤ 1")

print()
print(f"  {'D':>6}  {'V_theory':>10}  {'D²+V²':>8}  {'Englert':>8}")
print(f"  {'─'*6}  {'─'*10}  {'─'*8}  {'─'*8}")

D_values = [0.0, 0.25, 0.50, 0.75, 1.0]
for D in D_values:
    V_theory = visibility_from_D(D)
    sum_sq   = D**2 + V_theory**2
    ok       = englert_bound_satisfied(D, V_theory)
    marker   = "✓" if ok else "✗"
    print(f"  {D:6.2f}  {V_theory:10.6f}  {sum_sq:8.6f}  {marker}")

    # Cross-check: compute profile and measure V numerically
    y_arr, I_arr = build_intensity_profile(
        D_SLIT, L_SCREEN, lam_e, D=D,
        y_min=-Y_HALF, y_max=Y_HALF, n_points=2000
    )
    I_max = max(I_arr)
    I_min_val = min(I_arr)
    V_meas = fringe_visibility(I_max, I_min_val)
    # V_measured should match V_theory = √(1-D²) within a few %
    err = abs(V_meas - V_theory) / max(V_theory, 1e-6) if V_theory > 0.01 else abs(V_meas)
    ok2 = err < 0.05 or V_theory < 0.01   # 5% tolerance, skip near-zero
    if not ok2:
        _failures.append(f"Measured V vs theory at D={D}")
        print(f"    ✗ FAIL  Measured V={V_meas:.4f} vs theory {V_theory:.4f} "
              f"({err*100:.1f}%)")

# Verify D=0 gives V≈1
D0_check = visibility_from_D(0.0)
check("V(D=0) = 1.0 exactly", D0_check, 1.0, tol_frac=1e-12)

# Verify D=1 gives V=0
D1_check = visibility_from_D(1.0)
check("V(D=1) = 0.0 exactly", D1_check, 0.0, tol_frac=1e-12)


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — SSBM prediction: neutron fringe compression with σ
# ══════════════════════════════════════════════════════════════════════════════

section("6. SSBM: neutron fringe spacing vs σ  (TESTABLE PREDICTION)")

print()
print(f"  Neutron fringes compress as σ increases (heavier → shorter λ).")
print(f"  Electron fringes: unchanged (σ-invariant mass).")
print()
print(f"  {'σ':>8}  {'m_n (MeV)':>12}  {'λ_n (pm)':>10}  "
      f"{'Δy ratio':>10}  {'% change':>10}")
print(f"  {'─'*8}  {'─'*12}  {'─'*10}  {'─'*10}  {'─'*10}")

sigma_values = [0.0, 0.05, 0.10, 0.20, 0.50, 1.00]
lam_n_ref = de_broglie_neutron(E_EV, sigma=0.0)

for sig in sigma_values:
    m_n_s   = neutron_mass_mev(sig)
    lam_n_s = de_broglie_neutron(E_EV, sigma=sig)
    ratio   = lam_n_s / lam_n_ref          # = Δy_n(σ)/Δy_n(0)
    pct     = (ratio - 1.0) * 100.0
    print(f"  {sig:8.2f}  {m_n_s:12.3f}  "
          f"{lam_n_s*1e12:10.4f}  {ratio:10.6f}  {pct:+10.3f}%")

# Numerical first-order coefficient
ratio_05, coeff = fringe_compression_per_sigma(sigma_small=0.01)
print(f"\n  First-order compression: Δy_n(σ)/Δy_n(0) ≈ 1 − {coeff:.4f}×σ")
print(f"  (At σ=1: expect ~{coeff*100:.1f}% fringe compression — directly measurable)")

# Verify ratio formula: ratio = √(m_n(0)/m_n(σ))
for sig in [0.10, 0.50]:
    ratio_func   = neutron_fringe_spacing_ratio(sig)
    m_0 = neutron_mass_mev(0.0)
    m_s = neutron_mass_mev(sig)
    ratio_manual = math.sqrt(m_0 / m_s)
    check(f"Fringe ratio formula at σ={sig}", ratio_func, ratio_manual, tol_frac=1e-9)

# Electron ratio always 1.0
from local_library.interface.quantum import electron_fringe_spacing_ratio
for sig in [0.10, 1.00]:
    r = electron_fringe_spacing_ratio(sig)
    check(f"Electron fringe ratio at σ={sig} = 1.0", r, 1.0, tol_frac=1e-12)


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — Predicted hit distribution (100k virtual particles)
# ══════════════════════════════════════════════════════════════════════════════

section("7. Physics at known analytical points")

# Direct checks at analytically known positions.
# No peak-finder needed — constructive/destructive positions are exact predictions.

y_arr, I_arr = build_intensity_profile(
    D_SLIT, L_SCREEN, lam_e, D=0.0, a=A_SLIT,
    y_min=-Y_HALF, y_max=Y_HALF, n_points=5000
)
I_total = sum(I_arr)

# --- Constructive at y=0 vs destructive at y=Δy/2 ---
# Ratio I(0) / I(Δy/2) should be >> 1 (fringe contrast)
I_at_0       = double_slit_intensity(0.0,        D_SLIT, L_SCREEN, lam_e, D=0.0, a=A_SLIT)
I_at_half    = double_slit_intensity(delta_y/2,  D_SLIT, L_SCREEN, lam_e, D=0.0, a=A_SLIT)
I_at_one     = double_slit_intensity(delta_y,    D_SLIT, L_SCREEN, lam_e, D=0.0, a=A_SLIT)
I_at_three_2 = double_slit_intensity(1.5*delta_y,D_SLIT, L_SCREEN, lam_e, D=0.0, a=A_SLIT)

print(f"\n  I(0)         = {I_at_0:.6g}   ← central maximum")
print(f"  I(Δy/2)      = {I_at_half:.6g}   ← first minimum (expect ≈0)")
print(f"  I(Δy)        = {I_at_one:.6g}   ← first-order fringe (expect close to I(0)×sinc²)")
print(f"  I(3Δy/2)     = {I_at_three_2:.6g}   ← second minimum (expect ≈0)")

# First minimum must be near zero: I(Δy/2) / I(0) << 1
ratio_min = I_at_half / max(I_at_0, 1e-30)
check("I(Δy/2)/I(0) (first minimum depth)", ratio_min, 0.0, tol_frac=1e-5)

# First-order fringe: I(Δy) / I(0) = sinc²(π×a×Δy/(L×λ)) / sinc²(0)
#   = sinc²(π×a/(d)) = sinc²(π/5) for d/a=5
import math as _m
sinc_arg = _m.pi * A_SLIT / D_SLIT     # = π/5 = 0.6283
sinc2_expected = (_m.sin(sinc_arg) / sinc_arg) ** 2   # ≈ 0.875
ratio_first_order = I_at_one / max(I_at_0, 1e-30)
check("I(Δy)/I(0) = sinc²(π/5) ≈ 0.875", ratio_first_order, sinc2_expected, tol_frac=0.01)

# Second minimum also near zero
ratio_min2 = I_at_three_2 / max(I_at_0, 1e-30)
check("I(3Δy/2)/I(0) (second minimum depth)", ratio_min2, 0.0, tol_frac=1e-5)

# Central maximum is the GLOBAL maximum (brighter than first-order fringe)
ok_max = I_at_0 > I_at_one
print(f"\n  {'✓ PASS' if ok_max else '✗ FAIL'}  I(0) > I(Δy) — central fringe is brightest")
if not ok_max:
    _failures.append("Central fringe is global maximum")

# Probability fraction in central diffraction lobe
i_zero_lo = max(0, int(((-y_zero) - (-Y_HALF)) / (2*Y_HALF) * len(y_arr)))
i_zero_hi = min(len(y_arr)-1, int((y_zero - (-Y_HALF)) / (2*Y_HALF) * len(y_arr)))
I_central_lobe = sum(I_arr[i_zero_lo:i_zero_hi+1])
frac_in_lobe = I_central_lobe / max(I_total, 1e-30)
print(f"\n  Fraction of probability in central diffraction lobe: {frac_in_lobe*100:.1f}%")
ok_lobe = frac_in_lobe > 0.5
print(f"  {'✓ PASS' if ok_lobe else '✗ FAIL'}  > 50% in central lobe (expected for d/a=5)")
if not ok_lobe:
    _failures.append("Fraction in central lobe")


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — ASCII preview of predicted pattern
# ══════════════════════════════════════════════════════════════════════════════

section("8. Predicted pattern preview (D=0, no observer)")

# Coarse profile for display
y_disp, I_disp = build_intensity_profile(
    D_SLIT, L_SCREEN, lam_e, D=0.0, a=A_SLIT,
    y_min=-Y_HALF, y_max=Y_HALF, n_points=80
)

I_max_disp = max(I_disp)
bar_width = 50
print()
for i in range(len(y_disp)):
    y_mm = y_disp[i] * 1e3
    bar = int(I_disp[i] / I_max_disp * bar_width)
    print(f"  {y_mm:+6.2f}mm | {'█' * bar}")

section("8b. Predicted pattern preview (D=1, full observer — no fringes)")

y_disp2, I_disp2 = build_intensity_profile(
    D_SLIT, L_SCREEN, lam_e, D=1.0, a=A_SLIT,
    y_min=-Y_HALF, y_max=Y_HALF, n_points=80
)
I_max_disp2 = max(I_disp2)
print()
for i in range(len(y_disp2)):
    y_mm = y_disp2[i] * 1e3
    bar = int(I_disp2[i] / I_max_disp2 * bar_width)
    print(f"  {y_mm:+6.2f}mm | {'█' * bar}")


# ══════════════════════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

section("SUMMARY")
print()
if not _failures:
    print(f"  ✓ ALL PREDICTIONS CONSISTENT — {len(_failures)} failures")
    print()
    print("  COMMITTED PREDICTIONS FOR simulate_double_slit.py:")
    print(f"    λ_e(1 eV)    = {lam_e*1e9:.4f} nm")
    print(f"    Fringe Δy    = {delta_y*1e3:.4f} mm")
    print(f"    Envelope 0   = {y_zero*1e3:.4f} mm")
    print(f"    Fringes      ≈ {n_fringes:.0f} under central lobe")
    print(f"    V(D=0)       = 1.000  (full fringes)")
    print(f"    V(D=1)       ≈ 0.000  (no fringes)")
    print(f"    Neutron Δy shifts by ≈ {coeff*100:.1f}% per unit σ")
    print(f"    Electron Δy: σ-invariant")
else:
    print(f"  ✗ {len(_failures)} PREDICTION(S) FAILED:")
    for f in _failures:
        print(f"    - {f}")
    print()
    print("  Fix quantum.py before running the simulation.")

print()

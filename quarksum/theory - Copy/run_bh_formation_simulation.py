#!/usr/bin/env python3
"""Black Hole Formation — Dual Model Simulation Runner.

Runs a stellar core collapse through BOTH Standard GR and SSBM models
simultaneously, comparing their predictions at every radius step.

WHAT THIS SIMULATES:
  A 10 M☉ iron core collapsing under gravity, tracked from R = 100 r_s
  (stellar envelope) down to R = 0.001 r_s (deep inside the horizon).

  Standard GR:  collapse → horizon → singularity (ρ → ∞)
  SSBM:         collapse → horizon → σ activation → bond cascade → conversion

PROVENANCE (every input is measured or derived):
  - Collapsing mass: 10 M☉ (typical core-collapse supernova progenitor)
  - G, c, ℏ, k_B: exact 2019 SI definitions (from QuarkSum)
  - m_p, m_n: AME2020 mass excesses (from QuarkSum)
  - Quark masses: PDG 2024 MS-bar central values (from CONSTANTS)
  - Fe-56 binding: 8.790 MeV/nucleon (AME2020 experimental)
  - Nuclear density: 0.16 fm⁻³ × m_p (empirical saturation, PDG review)
  - Bond lengths: measured (from scale_field)
  - ξ = 0.1582: Planck 2018 Ω_b / (Ω_b + Ω_c)
  - Λ_QCD = 0.332 GeV: PDG 2024 (N_f = 3, MS-bar)
  - Planck density: derived from ℏ, G, c

DARK MATTER IN SSBM:
  In the SSBM/RODM hypothesis, "dark matter" IS reformed baryonic matter
  from prior conversion events — matter whose QCD scale has been shifted
  by σ ≠ 0.  It is NOT a separate particle species.

  The simulation includes dark matter implicitly through:
  - ξ = Ω_b / (Ω_b + Ω_c) — the baryon fraction of total matter
  - The conversion energy E = ξMc² — the energy that creates the
    reformed matter fraction
  - The total mass M includes ALL gravitating matter (baryonic + dark)
  - Ω_m = Ω_b + Ω_c appears in the Friedmann equation through r_s = R_H

  So yes: when we write M = 10 M☉, that is the TOTAL gravitating mass.
  The conversion event converts the baryonic fraction (ξ) and the rest
  (1-ξ) is already in the reformed/dark state from the parent universe.

  This is the RODM closure: dark matter is not missing matter,
  it is matter whose scale field σ ≠ 0.

NO MAGIC NUMBERS.
"""

import sys
import math

# Ensure the correct import paths
sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/quarksum")
sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/Materia/qamss")

from materia.core.constants import CONSTANTS, PLANCK
from materia.core.scale_field import (
    XI_SSBM, LAMBDA_QCD_GEV, BOND_LENGTHS_M,
    bond_failure_radius_m, sigma_at_radius_combined,
)
from materia.models.black_hole import (
    schwarzschild_radius_m, photon_sphere_radius_m, isco_radius_m,
    hawking_temperature_K, hawking_evaporation_time_s,
    bekenstein_hawking_entropy, kretschner_scalar_inv_m4,
    tidal_acceleration_m_s2,
    M_SUN_KG,
)
from materia.models.bh_formation import (
    run_formation, print_formation_report,
    gr_snapshot_at_radius, ssbm_snapshot_at_radius,
    free_fall_time_s,
)

# ── Configuration ──────────────────────────────────────────────────────

MASS_SOLAR = 10.0       # Solar masses (typical core-collapse progenitor)
N_POINTS = 500          # Radial evaluation points (need more for huge range)
R_START_FACTOR = 100.0  # Start at 100 × r_s (stellar envelope)
R_END_FACTOR = 1e-14    # End at 10⁻¹⁴ × r_s (~3e-10 m, sub-quark scale)
                        # Bond failure radii: molecular ~10⁻⁵ m (3e-10 r_s)
                        #                     nuclear ~5e-9 m (2e-13 r_s)
                        # Must go well below to see full cascade + conversion

M_KG = MASS_SOLAR * M_SUN_KG
R_S = schwarzschild_radius_m(M_KG)

# ── Run the simulation ─────────────────────────────────────────────────

print("Running dual-model BH formation simulation...")
print(f"  Mass: {MASS_SOLAR} M☉ = {M_KG:.4e} kg")
print(f"  r_s = {R_S:.4e} m = {R_S * 1e-3:.2f} km")
print(f"  Range: {R_START_FACTOR} r_s → {R_END_FACTOR} r_s")
print(f"  Points: {N_POINTS}")
print()

snapshots = run_formation(
    mass_solar=MASS_SOLAR,
    n_points=N_POINTS,
    R_start_factor=R_START_FACTOR,
    R_end_factor=R_END_FACTOR,
)

# ── Print the full report ──────────────────────────────────────────────

report = print_formation_report(snapshots)
print(report)

# ── Cross-checks and assertions ────────────────────────────────────────

print()
print("=" * 100)
print("CROSS-CHECKS AND ASSERTIONS")
print("=" * 100)
print()

failures = 0

# 1. Both models agree outside horizon
print("1. Models agree outside horizon:")
outside = [s for s in snapshots if not s.gr.is_trapped_surface]
disagreements_outside = [s for s in outside if not s.models_agree]
if len(disagreements_outside) == 0:
    print(f"   ✓ All {len(outside)} pre-horizon snapshots: models agree")
else:
    print(f"   ✗ {len(disagreements_outside)} disagreements outside horizon!")
    failures += 1

# 2. GR: density increases monotonically inward
print("2. GR density increases monotonically:")
rho_prev = 0.0
monotonic = True
for s in snapshots:
    if s.gr.mean_density_kg_m3 < rho_prev * 0.99:  # allow 1% numerical noise
        monotonic = False
        break
    rho_prev = s.gr.mean_density_kg_m3
if monotonic:
    print(f"   ✓ Density monotonically increases from {snapshots[0].gr.mean_density_kg_m3:.3e} "
          f"to {snapshots[-1].gr.mean_density_kg_m3:.3e} kg/m³")
else:
    print("   ✗ Density NOT monotonic!")
    failures += 1

# 3. GR: Kretschner scalar increases inward
print("3. GR Kretschner scalar increases inward:")
K_start = snapshots[0].gr.kretschner_scalar
K_end = snapshots[-1].gr.kretschner_scalar
if K_end > K_start:
    print(f"   ✓ K increases from {K_start:.3e} to {K_end:.3e} m⁻⁴")
else:
    print(f"   ✗ K does not increase! Start: {K_start:.3e}, End: {K_end:.3e}")
    failures += 1

# 4. GR: proper time to singularity decreases inside horizon
print("4. GR proper time to singularity decreases inside horizon:")
inside = [s for s in snapshots if s.gr.is_trapped_surface]
if inside:
    tau_first = inside[0].gr.proper_time_to_singularity_s
    tau_last = inside[-1].gr.proper_time_to_singularity_s
    if tau_last < tau_first:
        print(f"   ✓ τ decreases from {tau_first:.3e} s to {tau_last:.3e} s")
    else:
        print(f"   ✗ τ does not decrease!")
        failures += 1
else:
    print("   (no inside-horizon snapshots)")

# 5. GR: Penrose theorem triggered at horizon
print("5. GR Penrose theorem triggered:")
penrose_triggered = any(s.gr.penrose_theorem_triggered for s in snapshots)
if penrose_triggered:
    first_penrose = next(s for s in snapshots if s.gr.penrose_theorem_triggered)
    r_rs = first_penrose.gr.core_radius_m / R_S
    print(f"   ✓ Triggered at R/r_s = {r_rs:.4f}")
else:
    print("   ✗ Penrose theorem never triggered!")
    failures += 1

# 6. SSBM: σ increases inward
print("6. SSBM σ field increases inward:")
sigma_start = snapshots[0].ssbm.sigma_center
sigma_end = snapshots[-1].ssbm.sigma_center
if sigma_end > sigma_start:
    print(f"   ✓ σ_center: {sigma_start:.6f} → {sigma_end:.6f}")
else:
    print(f"   ✗ σ does not increase! Start: {sigma_start:.6f}, End: {sigma_end:.6f}")
    failures += 1

# 7. SSBM: bonds fail in order (longest first)
print("7. SSBM bond failure order (longest length scale first):")
bond_names_by_length = sorted(BOND_LENGTHS_M.keys(),
                               key=lambda k: BOND_LENGTHS_M[k], reverse=True)
failure_order = []
for bond_name in bond_names_by_length:
    for i, s in enumerate(snapshots):
        for b in s.ssbm.bonds:
            if b.name == bond_name and b.has_failed:
                failure_order.append((bond_name, i))
                break
        else:
            continue
        break
# Check that failure indices are non-decreasing (larger indices = smaller radii)
indices = [idx for _, idx in failure_order]
if indices == sorted(indices):
    print(f"   ✓ Bonds fail in correct order: {[n for n, _ in failure_order]}")
else:
    print(f"   ✗ Bond failure order incorrect!")
    failures += 1

# 8. SSBM: conversion event reached (all bonds failed)
print("8. SSBM conversion event reached:")
conversion_snaps = [s for s in snapshots if s.ssbm.phase == "conversion"]
if conversion_snaps:
    conv = conversion_snaps[0]
    print(f"   ✓ Conversion at R = {conv.ssbm.core_radius_m:.4e} m "
          f"({conv.ssbm.core_radius_m / R_S:.6f} r_s)")
    print(f"     σ_center = {conv.ssbm.sigma_center:.6f}")
    print(f"     All {conv.ssbm.n_bonds_total} bond types failed")
else:
    print("   ✗ No conversion event in simulation range!")
    failures += 1

# 9. Both models: compactness β → 0.5 at horizon
print("9. Compactness β → 0.5 at horizon:")
horizon_snap = min(snapshots, key=lambda s: abs(s.gr.core_radius_m - R_S))
beta_at_hz = horizon_snap.gr.compactness
if abs(beta_at_hz - 0.5) < 0.05:
    print(f"   ✓ β = {beta_at_hz:.4f} at R/r_s = {horizon_snap.gr.core_radius_m / R_S:.4f}")
else:
    print(f"   ✗ β = {beta_at_hz:.4f} at horizon (expected ~0.5)")
    failures += 1

# 10. SSBM: conversion energy = ξMc²
print("10. SSBM conversion energy = ξMc²:")
E_conv = conversion_snaps[0].ssbm.conversion_energy_J if conversion_snaps else 0
E_expected = XI_SSBM * M_KG * CONSTANTS.c ** 2
if E_conv > 0 and abs(E_conv / E_expected - 1.0) < 1e-10:
    print(f"   ✓ E_conv = {E_conv:.4e} J = ξMc² (exact)")
else:
    print(f"   ✗ E_conv mismatch: {E_conv:.4e} vs {E_expected:.4e}")
    failures += 1

# 11. Dark matter accounting: ξ = Ω_b / (Ω_b + Ω_c)
print("11. Dark matter in SSBM (RODM accounting):")
from materia.core.cosmology import COSMOLOGY
Omega_b = COSMOLOGY.Omega_b
Omega_c = COSMOLOGY.Omega_c
xi_check = Omega_b / (Omega_b + Omega_c)
if abs(xi_check - XI_SSBM) < 0.002:  # Small difference from rounding in Planck 2018 values
    print(f"   ✓ ξ = Ω_b/(Ω_b+Ω_c) = {xi_check:.4f} ≈ {XI_SSBM}")
    print(f"     Baryonic fraction (to be converted): {XI_SSBM * 100:.1f}%")
    print(f"     Dark/reformed fraction (already shifted): {(1 - XI_SSBM) * 100:.1f}%")
    print(f"     Total matter: Ω_m = Ω_b + Ω_c = {Omega_b + Omega_c:.4f}")
else:
    print(f"   ✗ ξ mismatch: {xi_check:.4f} vs {XI_SSBM}")
    failures += 1

# 12. Key radius comparisons
print("12. Key radii:")
r_ph = photon_sphere_radius_m(M_KG)
r_isco = isco_radius_m(M_KG)
print(f"   ISCO:          {r_isco:.4e} m = {r_isco / R_S:.1f} r_s")
print(f"   Photon sphere: {r_ph:.4e} m = {r_ph / R_S:.1f} r_s")
print(f"   Event horizon: {R_S:.4e} m = {R_S / R_S:.1f} r_s")
# SSBM conversion radius
if conversion_snaps:
    r_conv = conversion_snaps[0].ssbm.core_radius_m
    print(f"   Conversion:    {r_conv:.4e} m = {r_conv / R_S:.6f} r_s (SSBM only)")

print()

# ── Summary ────────────────────────────────────────────────────────────

print("=" * 100)
if failures == 0:
    print("ALL CROSS-CHECKS PASSED (0 failures)")
    print()
    print("SUMMARY:")
    print("  Standard GR and SSBM agree on ALL exterior observables.")
    print("  They diverge ONLY inside the event horizon.")
    print("  GR predicts: singularity (infinite density, geodesic incompleteness)")
    print("  SSBM predicts: conversion event (finite density, reformed matter cavity)")
    print()
    print("  The interior is causally disconnected from exterior observers.")
    print("  No exterior measurement can tell them apart.")
    print("  But the SSBM interior IS a nascent universe — and we may be living in one.")
else:
    print(f"FAILURES: {failures}")
print("=" * 100)

sys.exit(failures)

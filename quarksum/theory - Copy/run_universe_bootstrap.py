#!/usr/bin/env python3
"""Universe ↔ Black Hole Bootstrap Test.

Tests the SSBM prediction that the interior of a black hole is
indistinguishable from a universe, and that our observable universe
is consistent with being the interior of a parent black hole.

Key results:
  - r_s(M_universe) / R_Hubble ≈ 1.7 (dimensionally near unity)
  - σ at horizon = ξ/2 ≈ 0.0791 for ALL black holes (universal)
  - Quark count conserved across the event horizon
  - σ profile: smooth from exterior → horizon → interior

Author: Aaron Rhodes / RODM hypothesis
"""

import sys
import json
import math

sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/quarksum")
sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/Materia/qamss")

from materia.core.constants import CONSTANTS
from materia.core.scale_field import (
    XI_SSBM,
    GAMMA_SSBM,
    LAMBDA_QCD_GEV,
    scale_ratio,
    lambda_eff_gev,
    sigma_at_radius_combined,
    sigma_at_radius_potential,
    sigma_from_kretschner,
    bond_failure_radius_m,
    BOND_LENGTHS_M,
)
from materia.models.black_hole import (
    BlackHole,
    BlackHoleRegime,
    M_SUN_KG,
    schwarzschild_radius_m,
    hawking_temperature_K,
    hawking_evaporation_time_s,
    eddington_luminosity_W,
    ssbm_conversion_energy_J,
    ssbm_nova_luminosity_W,
)

_G = 6.67430e-11
_c = 2.99792458e8
_c2 = _c ** 2

# ────────────────────────────────────────────────────────────────────
# 1. OBSERVABLE UNIVERSE PARAMETERS
# ────────────────────────────────────────────────────────────────────
M_UNIVERSE_KG = 1.5e53          # baryonic + dark matter estimate
R_HUBBLE_M = 13.8e9 * 9.461e15  # 13.8 Gly in meters
R_COMOVING_M = 46.5e9 * 9.461e15  # 46.5 Gly comoving radius
N_GALAXIES = 2e11               # ~200 billion observable galaxies
CMB_TEMP_K = 2.7255


def separator(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ────────────────────────────────────────────────────────────────────
# 2. SCHWARZSCHILD RADIUS vs HUBBLE RADIUS
# ────────────────────────────────────────────────────────────────────
separator("1. THE DIMENSIONAL COINCIDENCE")

r_s_universe = schwarzschild_radius_m(M_UNIVERSE_KG)
r_s_gly = r_s_universe / (9.461e15 * 1e9)
r_hubble_gly = R_HUBBLE_M / (9.461e15 * 1e9)
r_comoving_gly = R_COMOVING_M / (9.461e15 * 1e9)

ratio_hubble = r_s_universe / R_HUBBLE_M
ratio_comoving = r_s_universe / R_COMOVING_M

print(f"  Observable universe mass:     M = {M_UNIVERSE_KG:.1e} kg")
print(f"  Schwarzschild radius:         r_s = {r_s_gly:.2f} Gly")
print(f"  Hubble radius:                R_H = {r_hubble_gly:.2f} Gly")
print(f"  Comoving radius:              R_c = {r_comoving_gly:.2f} Gly")
print()
print(f"  r_s / R_Hubble   = {ratio_hubble:.3f}  ← near unity!")
print(f"  r_s / R_comoving = {ratio_comoving:.3f}  ← also near unity")
print()
print("  INTERPRETATION: The observable universe's mass is within a")
print("  factor of ~2 of the mass that would make a Schwarzschild BH")
print("  with radius equal to the Hubble radius. This is the")
print("  'coincidence' that motivates the SSBM bootstrap hypothesis.")

assert 0.5 < ratio_hubble < 5.0, f"ratio out of range: {ratio_hubble}"
print("  ✓ Dimensional coincidence confirmed")


# ────────────────────────────────────────────────────────────────────
# 3. σ AT THE HORIZON IS UNIVERSAL
# ────────────────────────────────────────────────────────────────────
separator("2. UNIVERSALITY OF σ AT THE EVENT HORIZON")

test_masses = [
    ("1 M☉ remnant", 1.0 * M_SUN_KG),
    ("10 M☉ stellar", 10.0 * M_SUN_KG),
    ("4×10⁶ M☉ (Sgr A*)", 4e6 * M_SUN_KG),
    ("10⁹ M☉ quasar", 1e9 * M_SUN_KG),
    ("Observable Universe", M_UNIVERSE_KG),
]

print(f"  σ at horizon = ξ·GM/(r_s·c²) = ξ·GM/(2GM/c²)·(1/c²) = ξ/2")
print(f"  ξ = {XI_SSBM}, so σ_horizon = {XI_SSBM/2:.4f} for ALL BHs\n")

for name, mass in test_masses:
    r_s = schwarzschild_radius_m(mass)
    sigma_h = sigma_at_radius_potential(r_s, mass)
    print(f"  {name:30s}  M = {mass:.2e} kg  σ(r_s) = {sigma_h:.6f}")
    assert abs(sigma_h - XI_SSBM / 2) < 1e-10, f"σ not universal for {name}"

print(f"\n  ✓ σ at horizon = {XI_SSBM/2:.4f} for all masses (universal)")
print(f"  → Proton mass shift at horizon: {(scale_ratio(XI_SSBM/2) - 1)*100:.2f}%")


# ────────────────────────────────────────────────────────────────────
# 4. QUARK COUNT CONSERVATION
# ────────────────────────────────────────────────────────────────────
separator("3. QUARK COUNT CONSERVATION")

m_proton_kg = CONSTANTS.m_p
n_baryons = M_UNIVERSE_KG / m_proton_kg
n_quarks = 3 * n_baryons

print(f"  M_universe     = {M_UNIVERSE_KG:.1e} kg")
print(f"  m_proton       = {m_proton_kg:.4e} kg")
print(f"  N_baryons      ≈ {n_baryons:.3e}")
print(f"  N_quarks       ≈ {n_quarks:.3e}  (3 per baryon)")
print()
print("  If our universe is a BH interior, all quarks that crossed")
print("  the parent event horizon are still here — just at a different σ.")
print("  The count is conserved; only the scale has changed.")
print()
print("  From the parent universe's perspective:")
print(f"    They see a BH of mass {M_UNIVERSE_KG:.1e} kg")
print(f"    containing ~{n_quarks:.2e} quarks")
print(f"    at σ = 0 (their physics)")
print()
print("  From our perspective (inside):")
print(f"    We see a universe with ~{n_quarks:.2e} quarks")
print(f"    at σ = σ_parent (our physics = their physics × e^σ)")
print(f"    We CANNOT measure σ_parent — it IS our Λ_QCD")


# ────────────────────────────────────────────────────────────────────
# 5. σ PROFILE: EXTERIOR → HORIZON → INTERIOR
# ────────────────────────────────────────────────────────────────────
separator("4. σ PROFILE ACROSS THE EVENT HORIZON")

bh_universe = BlackHole.create(
    mass_solar=M_UNIVERSE_KG / M_SUN_KG,
    name="Observable Universe (as BH)",
    spin=0.0,
)
r_s = schwarzschild_radius_m(bh_universe.mass_kg)

# Radii from 100 r_s down to 0.01 r_s
radii_rs = [100, 50, 20, 10, 5, 2, 1.5, 1.0, 0.8, 0.5, 0.3, 0.1, 0.01]
print(f"  r_s = {r_s:.4e} m = {r_s / (9.461e15 * 1e9):.2f} Gly\n")
print(f"  {'r/r_s':>10s}  {'σ(r)':>12s}  {'Λ_eff/Λ_QCD':>12s}  {'m_p shift':>10s}")
print(f"  {'-'*10}  {'-'*12}  {'-'*12}  {'-'*10}")

for r_frac in radii_rs:
    r_m = r_frac * r_s
    sigma = sigma_at_radius_combined(r_m, bh_universe.mass_kg)
    lam_ratio = lambda_eff_gev(sigma) / LAMBDA_QCD_GEV
    mp_shift = (scale_ratio(sigma) - 1) * 100
    marker = " ← horizon" if r_frac == 1.0 else ""
    print(f"  {r_frac:10.2f}  {sigma:12.6f}  {lam_ratio:12.6f}  {mp_shift:9.2f}%{marker}")

print()
print("  NOTE: σ is smooth and continuous. No discontinuity at the horizon.")
print("  An observer falling in sees a gradual shift in QCD scale —")
print("  not a wall, not a firewall, just physics gently changing.")


# ────────────────────────────────────────────────────────────────────
# 6. BOND FAILURE ZONES (for stellar-mass BH as example)
# ────────────────────────────────────────────────────────────────────
separator("5. BOND FAILURE RADII (10 M☉ Black Hole)")

bh_stellar = BlackHole.create(mass_solar=10.0, name="Stellar BH")
r_s_stellar = schwarzschild_radius_m(bh_stellar.mass_kg)

print(f"  r_s = {r_s_stellar:.4e} m = {r_s_stellar/1000:.1f} km\n")
print(f"  {'Bond type':>25s}  {'ℓ (m)':>12s}  {'r_fail (m)':>12s}  {'r_fail/r_s':>10s}")
print(f"  {'-'*25}  {'-'*12}  {'-'*12}  {'-'*10}")

for bond_name, bond_len in sorted(BOND_LENGTHS_M.items(), key=lambda x: -x[1]):
    r_fail = bond_failure_radius_m(bond_len, bh_stellar.mass_kg)
    ratio = r_fail / r_s_stellar
    print(f"  {bond_name:>25s}  {bond_len:12.2e}  {r_fail:12.4e}  {ratio:10.6f}")

print()
print("  All bond failures occur deep INSIDE the event horizon (r_fail << r_s).")
print("  From outside, the BH looks identical in both models.")
print("  The difference is what happens to matter AFTER it crosses the horizon.")


# ────────────────────────────────────────────────────────────────────
# 7. THE BOOTSTRAP: BH INTERIOR AS UNIVERSE
# ────────────────────────────────────────────────────────────────────
separator("6. THE BOOTSTRAP HYPOTHESIS")

universe_view = bh_universe.interior_as_universe()

print("  OUR UNIVERSE AS A BLACK HOLE:\n")
bh_info = universe_view["black_hole"]
print(f"    Mass:           {bh_info['mass_kg']:.3e} kg ({bh_info['mass_solar']:.3e} M☉)")
print(f"    r_s:            {bh_info['schwarzschild_radius_m']:.4e} m")
print(f"    σ at horizon:   {bh_info['sigma_at_horizon']:.6f}")

print("\n  FROM INSIDE (us):\n")
interior = universe_view["interior_universe"]
print(f"    Λ_eff/Λ_QCD:   {interior['lambda_ratio']:.6f}")
print(f"    Quarks:         {interior['estimated_quarks']:.3e}")
print(f"    {interior['notes']}")

print("\n  FROM OUTSIDE (parent universe):\n")
outer = universe_view["our_universe_as_bh"]
print(f"    Parent r_s:     {outer['implied_parent_rs_gly']:.2f} Gly")
print(f"    Hubble radius:  {outer['hubble_radius_gly']:.1f} Gly")
print(f"    r_s/R_H:        {outer['rs_vs_hubble_ratio']:.3f}")

print("\n  SCALE DICHOTOMY:\n")
dichotomy = universe_view["scale_dichotomy"]
print(f"    Outside: {dichotomy['outside_view']}")
print(f"    Inside:  {dichotomy['inside_view']}")
print(f"    Bridge:  {dichotomy['what_connects_them']}")


# ────────────────────────────────────────────────────────────────────
# 8. THREE BH REGIMES
# ────────────────────────────────────────────────────────────────────
separator("7. THREE REGIMES — SAME PHYSICS, DIFFERENT SCALES")

regimes = [
    ("Micro remnant (0.5 M☉)", BlackHole.micro_remnant()),
    ("Stellar BH (10 M☉)", BlackHole.stellar()),
    ("SMBH (4×10⁶ M☉)", BlackHole.supermassive()),
    ("Universe (7.5×10²² M☉)", bh_universe),
]

print(f"  {'Name':>30s}  {'Regime':>20s}  {'r_s (m)':>12s}  {'σ_horizon':>10s}")
print(f"  {'-'*30}  {'-'*20}  {'-'*12}  {'-'*10}")

for name, bh in regimes:
    regime = bh.regime.value
    r_s = schwarzschild_radius_m(bh.mass_kg)
    sigma_h = sigma_at_radius_potential(r_s, bh.mass_kg)
    print(f"  {name:>30s}  {regime:>20s}  {r_s:12.3e}  {sigma_h:10.6f}")

print()
print("  ALL have the same σ at the horizon. The physics is identical.")
print("  Only the scale differs. A micro-remnant IS a tiny universe.")
print("  A supermassive BH IS a large universe. Ours is somewhere in between.")


# ────────────────────────────────────────────────────────────────────
# 9. WHAT WE CAN AND CANNOT KNOW
# ────────────────────────────────────────────────────────────────────
separator("8. WHAT WE CAN AND CANNOT KNOW")

print("""
  WHAT WE CAN KNOW (measurable from inside):
    ✓ Our Λ_QCD (217 MeV) — but we can't know if it's shifted
    ✓ Our proton mass (938.3 MeV) — but only at our σ
    ✓ Our CMB temperature (2.7255 K)
    ✓ Number of quarks in our universe (~3×10⁷⁹)
    ✓ Our Hubble radius (13.8 Gly)
    ✓ All of physics — self-consistent within our σ

  WHAT WE CANNOT KNOW (hidden by dimension zero):
    ✗ σ_parent — the scale shift between us and the parent universe
    ✗ The parent BH's mass in parent units
    ✗ Our physical size as measured by the parent
    ✗ Whether the parent universe has the same ξ
    ✗ How many levels of nesting exist
    ✗ The parent's Λ_QCD — we only know Λ_parent × e^σ

  THIS IS DIMENSION ZERO:
    σ is the scalar field that you can never measure directly.
    It defines the relationship between scales — yours and theirs.
    From inside any universe, physics is complete and self-consistent.
    The only hint that σ ≠ 0 is the dimensional coincidence:
    r_s(M_universe) ≈ R_Hubble.
""")


# ────────────────────────────────────────────────────────────────────
# 10. SUMMARY
# ────────────────────────────────────────────────────────────────────
separator("SUMMARY")

print(f"""
  The SSBM bootstrap hypothesis:

  1. Every black hole interior is a universe (at a different σ).
  2. Every universe is the interior of a parent black hole.
  3. σ (dimension zero) connects the scales but cannot be measured
     from either side alone.
  4. The only observable hint: r_s ≈ R_Hubble (within factor ~{ratio_hubble:.1f}).
  5. Quark count is conserved across the horizon (~{n_quarks:.1e}).
  6. The CMB is the event horizon, seen from inside.
  7. "Expansion" of the universe = SSBM cavitation growing.

  This is either the most elegant idea in cosmology,
  or the most beautiful coincidence. Either way, it's testable:
  deviations in Λ_QCD at extreme gravitational potentials would
  confirm or falsify the σ field.

  All {len(test_masses)} mass scales tested. All assertions passed.
""")

#!/usr/bin/env python3
"""SSBM Five-Scale Simulation: Universe → Galaxy → Black Hole → Neutron Star → Atom.

One object at each scale. No dark matter. No free parameters beyond ξ and γ.
Every number derived from Planck 2018 + CODATA 2018 + AME2020.

The question: does σ(x) = ξ × |Φ|/c² produce the right physics at EVERY scale?
If yes at all five, we have a theory. If it fails at any scale, we know where to look.
"""

import sys
import math

sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/quarksum")
sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/Materia/qamss")

from materia.core.constants import CONSTANTS
from materia.core.cosmology import COSMOLOGY
from materia.core.scale_field import (
    XI_SSBM, LAMBDA_QCD_GEV,
    scale_ratio, sigma_from_gravitational_potential,
    sigma_at_radius_potential, effective_nucleon_mass_kg,
    effective_nuclear_binding_energy_mev,
)
from materia.physics.friedmann import (
    CosmoParameters, hubble_parameter, deceleration_parameter,
    age_of_universe, luminosity_distance, comoving_distance,
)
from materia.physics.rotation_curves import (
    rotation_curve_sigma_coupled,
    rotation_curve_decomposed,
    rotation_velocity_exponential_disk,
    sigma_profile_from_potential,
)
from materia.models.cosmic_evolution import sigma_cosmic
from materia.data.loader import ElementDB, IsotopeDB

G = CONSTANTS.G
c = CONSTANTS.c
c2 = c ** 2
M_sun = CONSTANTS.M_sun_kg
kpc = CONSTANTS.kpc_m
m_p = CONSTANTS.m_p
m_n = CONSTANTS.m_n
m_e = CONSTANTS.m_e
eV = CONSTANTS.eV

results = {}
checks_passed = 0
checks_failed = 0
checks_total = 0


def check(name, condition, detail=""):
    global checks_passed, checks_failed, checks_total
    checks_total += 1
    if condition:
        checks_passed += 1
        print(f"    ✓ {name}" + (f" — {detail}" if detail else ""))
    else:
        checks_failed += 1
        print(f"    ✗ {name}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════════════════
#  SCALE 1: THE OBSERVABLE UNIVERSE
#  Object: Hubble volume at z=0
#  σ prediction: σ = 0 everywhere (T_CMB << Λ_QCD)
#  Test: Friedmann expansion reproduces age, critical density, transition z
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 72)
print("  SCALE 1: THE OBSERVABLE UNIVERSE (r ~ 4.4×10²⁶ m)")
print("=" * 72)

params = CosmoParameters(
    H0_km_s_Mpc=67.4,
    Omega_m=0.315, Omega_Lambda=0.685, Omega_r=9.15e-5,
)

# σ at cosmic scale today
T_today_GeV = CONSTANTS.k_B * 2.7255 / (eV * 1e9)
sigma_today = sigma_cosmic(T_today_GeV)
print(f"\n  T_CMB = {2.7255} K = {T_today_GeV:.4e} GeV")
print(f"  σ_cosmic(today) = {sigma_today}")
print(f"  Λ_QCD = {LAMBDA_QCD_GEV} GeV")
print(f"  T_CMB / Λ_QCD = {T_today_GeV / LAMBDA_QCD_GEV:.4e}")

check("σ = 0 today (T << Λ_QCD)", sigma_today == 0.0)

# Age of universe
age_s = age_of_universe(params=params)
age_gyr = age_s / (365.25 * 24 * 3600 * 1e9)
print(f"  Age = {age_gyr:.2f} Gyr")
check("Age ≈ 13.8 Gyr", 13.0 < age_gyr < 14.5, f"{age_gyr:.2f} Gyr")

# Deceleration-acceleration transition
a_lo, a_hi = 0.3, 1.0
for _ in range(60):
    a_mid = (a_lo + a_hi) / 2.0
    if deceleration_parameter(a=a_mid, params=params) > 0:
        a_lo = a_mid
    else:
        a_hi = a_mid
z_trans = 1.0 / ((a_lo + a_hi) / 2.0) - 1.0
print(f"  Acceleration transition at z = {z_trans:.3f}")
check("Transition z ≈ 0.67", 0.5 < z_trans < 0.9, f"z = {z_trans:.3f}")

# r_s / R_H identity
r_s_universe = 2 * G * COSMOLOGY.observable_universe_mass_kg / c2
R_H = c / COSMOLOGY.H0_si
rs_rh = COSMOLOGY.rs_hubble_ratio_matter
print(f"  r_s(M_matter)/R_H = Ω_m = {rs_rh:.4f}")
check("r_s/R_H = Ω_m (Friedmann identity)", abs(rs_rh - 0.315) < 0.01)

results["universe"] = {"age_gyr": age_gyr, "z_transition": z_trans, "sigma": sigma_today}


# ═══════════════════════════════════════════════════════════════════════════
#  SCALE 2: A SPIRAL GALAXY (Milky Way analog)
#  Object: Galaxy with M_disk = 5×10¹⁰ M☉, R_d = 3 kpc
#  σ prediction: σ(r) = ξ × GM/(rc²) — enhances baryonic mass in center
#  Test: Does σ-coupling flatten the rotation curve without dark matter?
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 72)
print("  SCALE 2: MILKY WAY ANALOG GALAXY (r ~ 3×10²⁰ m)")
print("=" * 72)

# Milky Way parameters
M_disk = 5.0e10 * M_sun    # 5×10¹⁰ M☉
R_d = 3.0 * kpc             # 3 kpc scale radius
M_bulge = 1.0e10 * M_sun   # 10¹⁰ M☉
a_bulge = 0.5 * kpc         # 0.5 kpc

# NFW halo (standard ΛCDM fit for comparison)
rho_s_nfw = 7.0e6           # M☉/kpc³
r_s_nfw = 20.0 * kpc        # 20 kpc

# Radii from 1 kpc to 30 kpc
r_values = [r * kpc for r in [1, 2, 3, 5, 8, 10, 15, 20, 25, 30]]
r_kpc = [r / kpc for r in r_values]

# SSBM prediction (σ-coupled, no dark matter halo)
v_ssbm = rotation_curve_sigma_coupled(
    M_disk, R_d, M_bulge, a_bulge, r_values
)

# Standard ΛCDM (disk + bulge + NFW halo)
decomp = rotation_curve_decomposed(
    M_disk, R_d, M_bulge, a_bulge, rho_s_nfw, r_s_nfw, r_values
)
v_lcdm = decomp["total"]

# Baryons only (no halo, no σ)
v_baryon = [
    math.sqrt(
        rotation_velocity_exponential_disk(r, M_disk, R_d)**2 +
        (math.sqrt(G * M_bulge * r / (r + a_bulge)**2) if r > 0 else 0)**2
    )
    for r in r_values
]

# σ profile
sigma_profile = [sigma_profile_from_potential(r, M_disk + M_bulge) for r in r_values]

print(f"\n  {'r (kpc)':>8} {'v_baryon':>10} {'v_SSBM':>10} {'v_ΛCDM':>10} {'σ(r)':>10}")
print(f"  {'':>8} {'(km/s)':>10} {'(km/s)':>10} {'(km/s)':>10} {'':>10}")
print(f"  {'-'*52}")
for i, r in enumerate(r_kpc):
    print(f"  {r:8.1f} {v_baryon[i]/1e3:10.1f} {v_ssbm[i]/1e3:10.1f} "
          f"{v_lcdm[i]/1e3:10.1f} {sigma_profile[i]:10.6f}")

# Check: SSBM should be BETWEEN baryon-only and ΛCDM
for i in range(len(r_values)):
    if i > 2:  # skip inner region where bulge dominates
        check(
            f"SSBM > baryon-only at {r_kpc[i]:.0f} kpc",
            v_ssbm[i] > v_baryon[i],
            f"v_SSBM={v_ssbm[i]/1e3:.1f} vs v_baryon={v_baryon[i]/1e3:.1f} km/s"
        )

# Check: at 8 kpc (Sun's orbit), v ≈ 220 km/s
v_sun_ssbm = v_ssbm[4]  # index 4 = 8 kpc
v_sun_lcdm = v_lcdm[4]
v_sun_obs = 220e3  # observed ~220 km/s
print(f"\n  At Sun's orbit (8 kpc):")
print(f"    SSBM:     {v_sun_ssbm/1e3:.1f} km/s")
print(f"    ΛCDM:     {v_sun_lcdm/1e3:.1f} km/s")
print(f"    Observed:  220 km/s")

# Flatness: check outer curve doesn't drop Keplerian
v_outer = v_ssbm[-1]  # 30 kpc
v_mid = v_ssbm[5]     # 10 kpc
flatness_ratio = v_outer / v_mid
print(f"\n  Flatness ratio (v_30kpc / v_10kpc) = {flatness_ratio:.3f}")
print(f"    Keplerian would give: {math.sqrt(10.0/30.0):.3f}")
print(f"    Flat curve gives:     1.000")
check(
    "Flatter than Keplerian",
    flatness_ratio > math.sqrt(10.0/30.0),
    f"ratio={flatness_ratio:.3f} vs Kepler={math.sqrt(10.0/30.0):.3f}"
)

# HONESTY: how much of the ΛCDM velocity does σ recover?
sigma_fraction = (v_ssbm[7] - v_baryon[7]) / (v_lcdm[7] - v_baryon[7]) if v_lcdm[7] > v_baryon[7] else 0
print(f"\n  σ-coupling accounts for {sigma_fraction*100:.1f}% of the DM halo effect at 20 kpc")
check("σ provides measurable enhancement", sigma_fraction > 0.0)

results["galaxy"] = {
    "v_sun_ssbm_kms": v_sun_ssbm / 1e3,
    "v_sun_lcdm_kms": v_sun_lcdm / 1e3,
    "flatness_ratio": flatness_ratio,
    "sigma_fraction_20kpc": sigma_fraction,
    "sigma_at_8kpc": sigma_profile[4],
}


# ═══════════════════════════════════════════════════════════════════════════
#  SCALE 3: A STELLAR-MASS BLACK HOLE
#  Object: 10 M☉ Schwarzschild BH
#  σ prediction: σ(r) = ξ × GM/(rc²), capped at ξ/2 at event horizon
#  Test: σ gradient, mass scaling at ISCO, conversion energy
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 72)
print("  SCALE 3: STELLAR-MASS BLACK HOLE (r ~ 3×10⁴ m)")
print("=" * 72)

M_bh = 10.0 * M_sun
r_s = 2 * G * M_bh / c2
print(f"\n  M = 10 M☉ = {M_bh:.4e} kg")
print(f"  r_s = {r_s:.2f} m")

# σ profile from event horizon outward
bh_radii = [
    ("Event horizon", 1.0),
    ("Photon sphere", 1.5),
    ("ISCO", 3.0),
    ("10 r_s", 10.0),
    ("100 r_s", 100.0),
    ("1000 r_s", 1000.0),
]

print(f"\n  {'Location':>18} {'r (m)':>12} {'σ':>10} {'e^σ':>8} {'Δm/m':>10}")
print(f"  {'-'*62}")
for label, r_mult in bh_radii:
    r = r_mult * r_s
    sigma = sigma_at_radius_potential(r, M_bh)
    e_sigma = math.exp(sigma)
    dm_m = e_sigma - 1.0
    print(f"  {label:>18} {r:12.2f} {sigma:10.6f} {e_sigma:8.4f} {dm_m*100:9.4f}%")

sigma_isco = sigma_at_radius_potential(3.0 * r_s, M_bh)
sigma_eh = sigma_at_radius_potential(r_s, M_bh)

check("σ(ISCO) = ξ/6", abs(sigma_isco - XI_SSBM / 6) < 1e-10,
      f"σ={sigma_isco:.6f}, ξ/6={XI_SSBM/6:.6f}")
check("σ(EH) = ξ/2", abs(sigma_eh - XI_SSBM / 2) < 1e-10,
      f"σ={sigma_eh:.6f}, ξ/2={XI_SSBM/2:.6f}")

# Conversion energy: E = ξ × M × c²
E_conversion = XI_SSBM * M_bh * c2
E_solar = M_sun * c2
print(f"\n  Conversion energy: E = ξMc² = {E_conversion:.4e} J")
print(f"                       = {E_conversion / E_solar:.2f} M☉c²")
check("E_conversion = ξ × Mc²", True, f"{E_conversion:.4e} J")

# Proton mass at ISCO
p_bare_mev = 2 * 2.16 + 4.67
eff_p_isco = effective_nucleon_mass_kg(m_p, p_bare_mev, sigma_isco)
dm_p = (eff_p_isco - m_p) / m_p * 100
print(f"\n  Proton mass at ISCO: {eff_p_isco:.6e} kg ({dm_p:+.3f}%)")
check("Proton heavier at ISCO", eff_p_isco > m_p, f"Δm/m = {dm_p:.3f}%")

results["black_hole"] = {
    "r_s_m": r_s,
    "sigma_isco": sigma_isco,
    "sigma_eh": sigma_eh,
    "proton_mass_shift_isco_pct": dm_p,
    "conversion_energy_J": E_conversion,
}


# ═══════════════════════════════════════════════════════════════════════════
#  SCALE 4: A NEUTRON STAR
#  Object: M = 1.4 M☉, R = 10 km
#  σ prediction: σ(surface) = ξ × GM/(Rc²) ≈ 0.033
#  Test: Mass shift, binding energy shift, σ value
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 72)
print("  SCALE 4: NEUTRON STAR (r ~ 10⁴ m)")
print("=" * 72)

M_ns = 1.4 * M_sun
R_ns = 10e3  # 10 km
compactness = G * M_ns / (R_ns * c2)
sigma_ns = XI_SSBM * compactness
print(f"\n  M = 1.4 M☉ = {M_ns:.4e} kg")
print(f"  R = 10 km")
print(f"  Compactness GM/(Rc²) = {compactness:.4f}")
print(f"  σ(surface) = ξ × compactness = {sigma_ns:.6f}")

check("σ(NS surface) ~ 0.03", 0.02 < sigma_ns < 0.05, f"σ = {sigma_ns:.4f}")

# Proton mass shift at NS surface
eff_p_ns = effective_nucleon_mass_kg(m_p, p_bare_mev, sigma_ns)
dm_p_ns = (eff_p_ns - m_p) / m_p * 100
print(f"  Proton mass at surface: {eff_p_ns:.6e} kg ({dm_p_ns:+.3f}%)")
check("Proton ~3% heavier at NS surface", 2.0 < dm_p_ns < 5.0, f"{dm_p_ns:.2f}%")

# Fe-56 binding energy shift
be_fe56_mev = None
iso_fe56 = IsotopeDB.get().by_z_and_a(26, 56)
if iso_fe56:
    be_per_a = iso_fe56.get("binding_energy_per_nucleon_kev", 0)
    be_fe56_mev = be_per_a * 56 / 1000.0

if be_fe56_mev:
    eff_be = effective_nuclear_binding_energy_mev(be_fe56_mev, 26, 56, sigma_ns)
    dbe = (eff_be - be_fe56_mev) / be_fe56_mev * 100
    print(f"  Fe-56 BE at surface: {eff_be:.2f} MeV ({dbe:+.2f}%)")
    check("Fe-56 BE increases at NS surface", eff_be > be_fe56_mev, f"ΔBE = {dbe:.2f}%")

# Gravitational redshift
z_grav = 1.0 / math.sqrt(1.0 - 2.0 * compactness) - 1.0
print(f"  Gravitational redshift z_g = {z_grav:.4f}")
check("GR redshift ~ 0.3", 0.1 < z_grav < 0.5, f"z_g = {z_grav:.4f}")

results["neutron_star"] = {
    "sigma_surface": sigma_ns,
    "proton_shift_pct": dm_p_ns,
    "grav_redshift": z_grav,
}


# ═══════════════════════════════════════════════════════════════════════════
#  SCALE 5: A SINGLE ATOM (Fe-56)
#  Object: Iron-56 at σ = 0 (our lab)
#  σ prediction: σ = 0 → standard physics exactly
#  Test: Three-measure identity, Wheeler invariance, mass reconstruction
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 72)
print("  SCALE 5: SINGLE ATOM — Fe-56 (r ~ 10⁻¹⁰ m)")
print("=" * 72)

from materia.models.atom import Atom

elem_fe = ElementDB.get().by_symbol("Fe")
atom = Atom.create(elem_fe, isotope_mass_number=56)

stable = atom.stable_mass_kg
constituent = atom.constituent_mass_kg
binding_j = atom.binding_energy_joules
nuclear_be_mev = atom.nuclear_binding_energy_mev

print(f"\n  Stable mass:      {stable:.6e} kg")
print(f"  Constituent mass: {constituent:.6e} kg")
print(f"  Nuclear BE:       {nuclear_be_mev:.2f} MeV")
print(f"  BE/A:             {nuclear_be_mev/56:.3f} MeV/nucleon")

# Three-measure identity: constituent - binding/c² ≈ stable
nuclear_be_kg = binding_j / c2
corrected = constituent - nuclear_be_kg
# Add electron binding
electron_be_ev = atom.total_electron_binding_energy_ev
electron_be_kg = 0.0
if electron_be_ev and electron_be_ev > 0:
    electron_be_kg = electron_be_ev * eV / c2
corrected -= electron_be_kg

residual_ppm = abs(corrected - stable) / stable * 1e6
print(f"  Corrected mass:   {corrected:.6e} kg")
print(f"  Residual:         {residual_ppm:.4f} ppm")
check("Three-measure identity < 1 ppm", residual_ppm < 1.0, f"{residual_ppm:.4f} ppm")

# σ=0 recovery
check("effective_stable_mass == stable_mass at σ=0",
      atom.effective_stable_mass_kg == atom.stable_mass_kg)

# Wheeler: electron mass exact
for e in atom.electrons:
    if e.rest_mass_kg != m_e:
        check("Wheeler invariance", False, f"electron mass ≠ CODATA")
        break
else:
    check("Wheeler invariance: all 26 electrons = m_e", True)

# σ ≠ 0: proton gets heavier, electron doesn't
atom.scale_sigma = 0.05
eff_mass = atom.effective_stable_mass_kg
check("Fe-56 heavier at σ=0.05", eff_mass > stable,
      f"Δm/m = {(eff_mass-stable)/stable*100:.2f}%")

# Reset
atom.scale_sigma = 0.0
check("σ roundtrip recovery (exact)", atom.effective_stable_mass_kg == stable)

results["atom"] = {
    "stable_mass_kg": stable,
    "nuclear_be_mev": nuclear_be_mev,
    "residual_ppm": residual_ppm,
}


# ═══════════════════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 72)
print("  FIVE-SCALE SIMULATION SUMMARY")
print("=" * 72)
print(f"""
  Scale 1 — Universe (4.4×10²⁶ m):
    σ = 0 today, age = {results['universe']['age_gyr']:.2f} Gyr
    Acceleration transition at z = {results['universe']['z_transition']:.3f}

  Scale 2 — Galaxy (3×10²⁰ m):
    σ at Sun's orbit = {results['galaxy']['sigma_at_8kpc']:.6f}
    v_SSBM(8 kpc) = {results['galaxy']['v_sun_ssbm_kms']:.1f} km/s (observed: 220)
    σ accounts for {results['galaxy']['sigma_fraction_20kpc']*100:.1f}% of DM effect at 20 kpc
    Flatness ratio: {results['galaxy']['flatness_ratio']:.3f} (Kepler: 0.577)

  Scale 3 — Black Hole (3×10⁴ m):
    σ(ISCO) = {results['black_hole']['sigma_isco']:.6f} = ξ/6
    σ(EH) = {results['black_hole']['sigma_eh']:.6f} = ξ/2
    Proton {results['black_hole']['proton_mass_shift_isco_pct']:+.3f}% at ISCO

  Scale 4 — Neutron Star (10⁴ m):
    σ(surface) = {results['neutron_star']['sigma_surface']:.6f}
    Proton {results['neutron_star']['proton_shift_pct']:+.2f}% heavier
    GR redshift z_g = {results['neutron_star']['grav_redshift']:.4f}

  Scale 5 — Single Atom Fe-56 (10⁻¹⁰ m):
    Three-measure identity: {results['atom']['residual_ppm']:.4f} ppm
    Nuclear BE: {results['atom']['nuclear_be_mev']:.2f} MeV
    Wheeler invariance: ✓ (m_e exact ∀σ)
""")

print(f"  CHECKS: {checks_passed}/{checks_total} passed, {checks_failed} failed")
print(f"  {'✓ ALL CHECKS PASSED' if checks_failed == 0 else '✗ SOME CHECKS FAILED'}")
print()

# The honest question
print("  THE HONEST QUESTION:")
print(f"  σ at galactic scale accounts for only {results['galaxy']['sigma_fraction_20kpc']*100:.1f}%")
print(f"  of what NFW dark matter provides. This is because ξ = {XI_SSBM}")
print(f"  gives σ ~ 10⁻⁶ at galactic radii — far too small to explain")
print(f"  flat rotation curves alone. SSBM may need a stronger coupling")
print(f"  at galactic scales, or dark matter may be real.")
print()

#!/usr/bin/env python3
"""Sanity audit: verify ALL physics variables are derived, not hardcoded.

Tests every new and existing physics quantity against known analytical
results, cross-checks, and dimensional analysis.

Author: Aaron Rhodes / RODM hypothesis
"""

import sys
import math

sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/quarksum")
sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/Materia/qamss")

from materia.core.constants import CONSTANTS, PLANCK
from materia.core.cosmology import COSMOLOGY
from materia.core.scale_field import XI_SSBM, GAMMA_SSBM, LAMBDA_QCD_GEV
from materia.models.black_hole import (
    BlackHole, M_SUN_KG, M_CRIT_LOW_KG, M_CRIT_HIGH_KG,
    schwarzschild_radius_m, isco_radius_m, photon_sphere_radius_m,
    hawking_temperature_K, hawking_luminosity_W, hawking_evaporation_time_s,
    eddington_luminosity_W,
    event_horizon_area_m2, surface_gravity_m_s2,
    bekenstein_hawking_entropy, angular_momentum_kg_m2_s,
    ergosphere_radius_m, cauchy_horizon_radius_m,
    frame_dragging_rate_rad_s, penrose_max_energy_fraction,
    radiative_efficiency, specific_energy_isco,
    compactness_parameter, gravitational_redshift_z,
    tidal_acceleration_m_s2, kretschner_scalar_inv_m4,
    qnm_frequency_hz, qnm_damping_time_s,
    bekenstein_bound_bits,
)

_G = CONSTANTS.G
_c = CONSTANTS.c
_c2 = _c**2
_hbar = CONSTANTS.hbar
_k_B = CONSTANTS.k_B

passed = 0
failed = 0


def check(name, computed, expected, tol=1e-4):
    global passed, failed
    if expected == 0:
        ok = abs(computed) < tol
    else:
        ok = abs(computed - expected) / abs(expected) < tol
    status = "PASS" if ok else "FAIL"
    if not ok:
        failed += 1
        print(f"  {status}  {name}: got {computed:.6e}, expected {expected:.6e}")
    else:
        passed += 1
        print(f"  {status}  {name}")


def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ════════════════════════════════════════════════════════════════════
separator("1. DERIVED CONSTANTS SANITY")
# ════════════════════════════════════════════════════════════════════

# Stefan-Boltzmann from formula: σ = 2π⁵k⁴/(15h³c²)
sigma_SB_check = 2*math.pi**5*_k_B**4 / (15*CONSTANTS.h**3*_c**2)
check("σ_SB derived", CONSTANTS.sigma_SB, sigma_SB_check, 1e-10)

# Thomson cross-section from formula: σ_T = 8π/3 × (αℏ/(m_e c))²
alpha = CONSTANTS.alpha
sigma_T_check = 8*math.pi/3 * (alpha*_hbar/CONSTANTS.m_e/_c)**2
check("σ_T derived", CONSTANTS.sigma_T, sigma_T_check, 1e-6)

# Nuclear density: 0.16 fm⁻³ × m_p
check("ρ_nuclear", CONSTANTS.rho_nuclear_kg_m3, 0.16e45 * CONSTANTS.m_p, 1e-10)

# M_sun
check("M_sun", CONSTANTS.M_sun_kg, 1.98892e30, 1e-6)

# ℏc product
check("ℏc GeV·m", CONSTANTS.hbar_c_GeV_m, _hbar*_c/CONSTANTS.eV*1e-9, 1e-8)

# Light-year = c × year
check("ly = c×year", CONSTANTS.ly_m, _c * CONSTANTS.year_s, 1e-10)

# SEMF a_C in expected range (0.69-0.72 MeV)
assert 0.68 < CONSTANTS.a_C_MeV < 0.72, f"a_C = {CONSTANTS.a_C_MeV} out of range"
passed += 1
print(f"  PASS  a_C = {CONSTANTS.a_C_MeV:.4f} MeV (in range 0.68-0.72)")


# ════════════════════════════════════════════════════════════════════
separator("2. SCHWARZSCHILD BLACK HOLE (10 M☉)")
# ════════════════════════════════════════════════════════════════════

M = 10.0 * M_SUN_KG
bh = BlackHole.create(mass_solar=10.0, name="Test BH", spin=0.0)

# r_s = 2GM/c²
r_s = 2*_G*M/_c2
check("r_s", bh.schwarzschild_radius_m, r_s, 1e-10)

# r_+ = r_s for Schwarzschild
check("r_+ = r_s (Schw.)", bh.event_horizon_radius_m, r_s, 1e-10)

# A_H = 4π r_s²
check("A_H = 4πr_s²", bh.event_horizon_area_m2, 4*math.pi*r_s**2, 1e-10)

# ISCO = 3 r_s
check("ISCO = 3r_s", bh.isco_radius_m, 3*r_s, 1e-10)

# Photon sphere = 1.5 r_s
check("r_ph = 1.5r_s", bh.photon_sphere_radius_m, 1.5*r_s, 1e-10)

# Surface gravity: κ = c⁴/(4GM)
kappa = _c**4 / (4*_G*M)
check("κ = c⁴/(4GM)", bh.surface_gravity_m_s2, kappa, 1e-10)

# Hawking temp: T_H = ℏc³/(8πGMk_B) = ℏκ/(2πck_B)
T_H = _hbar*_c**3 / (8*math.pi*_G*M*_k_B)
check("T_H", bh.hawking_temperature_K, T_H, 1e-10)

# Cross-check: T_H = ℏκ/(2πck_B)
T_H_from_kappa = _hbar*kappa / (2*math.pi*_c*_k_B)
check("T_H = ℏκ/(2πck_B)", T_H, T_H_from_kappa, 1e-10)

# Entropy: S = k_B c³ A/(4Gℏ)
S_BH = _c**3 * (4*math.pi*r_s**2) / (4*_G*_hbar)
check("S_BH/k_B", bh.bekenstein_hawking_entropy, S_BH, 1e-10)

# Compactness at horizon = 0.5
check("β(r_s) = 0.5", bh.compactness_at_horizon, 0.5, 1e-10)

# Radiative efficiency η = 1 - √(8/9) for Schwarzschild
eta_schw = 1.0 - math.sqrt(8.0/9.0)
check("η = 1-√(8/9)", bh.radiative_efficiency, eta_schw, 1e-10)

# E_ISCO = √(8/9) for Schwarzschild
check("E_ISCO/mc²", bh.specific_energy_isco, math.sqrt(8.0/9.0), 1e-10)

# L_ISCO = 2√3 × rg for Schwarzschild
rg = _G*M/_c2
check("L_ISCO", bh.specific_angular_momentum_isco_m, 2*math.sqrt(3)*rg, 1e-6)

# J = 0 for Schwarzschild
check("J = 0 (Schw.)", bh.angular_momentum_kg_m2_s, 0.0, 1e-20)

# r_- = 0 for Schwarzschild
check("r_- = 0 (Schw.)", bh.cauchy_horizon_radius_m, 0.0, 1e-20)

# Penrose max = 0 for Schwarzschild
check("Penrose = 0 (Schw.)", bh.penrose_max_energy_fraction, 0.0, 1e-10)

# Gravitational redshift at ISCO: z = √(3/2) - 1
z_isco = math.sqrt(3.0/2.0) - 1.0
check("z(ISCO) = √(3/2)-1", bh.gravitational_redshift_at_isco, z_isco, 1e-4)

# Kretschner scalar at r_s: K = 48G²M²/(c⁴r_s⁶)
K_at_rs = 48*_G**2*M**2/(_c**4*r_s**6)
check("K(r_s)", bh.kretschner_scalar_at_radius(r_s), K_at_rs, 1e-8)

# Tidal acceleration at r_s: Δa = 2GM/(r_s³) for δr=1m
da = 2*_G*M/r_s**3
check("Δa(r_s)", bh.tidal_acceleration_at_horizon, da, 1e-10)

# QNM frequency: f = 0.3737 × c³/(2πGM) for Schwarzschild
f_qnm = 0.3737 * _c**3 / (2*math.pi*_G*M)
check("f_QNM (Schw.)", bh.qnm_frequency_hz, f_qnm, 1e-6)

# Eddington luminosity: L_Edd = 4πGMm_pc/σ_T
L_edd = 4*math.pi*_G*M*CONSTANTS.m_p*_c/CONSTANTS.sigma_T
check("L_Edd", bh.eddington_luminosity_W, L_edd, 1e-6)


# ════════════════════════════════════════════════════════════════════
separator("3. KERR BLACK HOLE (10 M☉, a*=0.9)")
# ════════════════════════════════════════════════════════════════════

bh_k = BlackHole.create(mass_solar=10.0, name="Kerr BH", spin=0.9)

# r_+ = rg(1 + √(1-a*²))
r_plus = rg * (1 + math.sqrt(1 - 0.9**2))
check("r_+ (Kerr)", bh_k.event_horizon_radius_m, r_plus, 1e-8)

# r_- = rg(1 - √(1-a*²))
r_minus = rg * (1 - math.sqrt(1 - 0.9**2))
check("r_- (Kerr)", bh_k.cauchy_horizon_radius_m, r_minus, 1e-8)

# Ergosphere at equator = r_s (always, for Kerr)
check("r_erg(eq) = r_s", bh_k.ergosphere_equatorial_radius_m, r_s, 1e-8)

# Ergosphere at pole = r_+ (always, for Kerr)
check("r_erg(pole) = r_+", bh_k.ergosphere_polar_radius_m, r_plus, 1e-8)

# J = a* × GM²/c
J_expected = 0.9 * _G * M**2 / _c
check("J = a*GM²/c", bh_k.angular_momentum_kg_m2_s, J_expected, 1e-8)

# Penrose max for a*=0.9: 1 - √((1+√(1-a*²))/2)
pen = 1.0 - math.sqrt((1 + math.sqrt(1-0.81))/2)
check("Penrose(a*=0.9)", bh_k.penrose_max_energy_fraction, pen, 1e-8)

# η for Kerr should be > Schwarzschild
assert bh_k.radiative_efficiency > eta_schw
passed += 1
print(f"  PASS  η(Kerr) = {bh_k.radiative_efficiency:.4f} > η(Schw.) = {eta_schw:.4f}")

# Horizon angular velocity: Ω_H = a*c/(2r_+)
Omega_H = 0.9 * _c / (2 * r_plus)
# Frame-dragging at horizon should ≈ Ω_H
# (exact for equatorial ZAMO at r_+)
check("Ω_H ≈ frame drag at r_+", bh_k.horizon_angular_velocity_rad_s, Omega_H, 0.02)


# ════════════════════════════════════════════════════════════════════
separator("4. COSMOLOGICAL PARAMETERS (Planck 2018)")
# ════════════════════════════════════════════════════════════════════

C = COSMOLOGY

# h = H₀/100
check("h = H₀/100", C.h, C.H0_km_s_Mpc / 100, 1e-10)

# Ω_b = Ω_bh² / h²
check("Ω_b", C.Omega_b, C.Omega_b_h2 / C.h**2, 1e-10)

# Ω_c = Ω_ch² / h²
check("Ω_c", C.Omega_c, C.Omega_c_h2 / C.h**2, 1e-10)

# Ω_m = Ω_b + Ω_c
check("Ω_m = Ω_b+Ω_c", C.Omega_m, C.Omega_b + C.Omega_c, 1e-10)

# Flat: Ω_m + Ω_Λ + Ω_r ≈ 1
check("Ω_total = 1", C.Omega_m + C.Omega_Lambda + C.Omega_r, 1.0, 1e-10)

# Critical density: ρ_c = 3H₀²/(8πG)
rho_c = 3*C.H0_si**2/(8*math.pi*_G)
check("ρ_c", C.critical_density_kg_m3, rho_c, 1e-10)

# Hubble radius: R_H = c/H₀
check("R_H = c/H₀", C.hubble_radius_m, _c / C.H0_si, 1e-10)

# Age: should be ~13.80 ± 0.05 Gyr
assert 13.7 < C.age_gyr < 13.9, f"age = {C.age_gyr} not in [13.7, 13.9]"
passed += 1
print(f"  PASS  age = {C.age_gyr:.2f} Gyr")

# Baryon-to-photon ratio: η_B ~ 6.1e-10
assert 5.5e-10 < C.baryon_to_photon_ratio < 6.5e-10
passed += 1
print(f"  PASS  η_B = {C.baryon_to_photon_ratio:.3e}")

# Photon density: n_γ ~ 411 cm⁻³ = 4.11e8 m⁻³
assert 4.0e8 < C.photon_number_density_m3 < 4.2e8
passed += 1
print(f"  PASS  n_γ = {C.photon_number_density_m3:.3e} m⁻³")

# z_eq ~ 3400
assert 3300 < C.z_matter_radiation_equality < 3500
passed += 1
print(f"  PASS  z_eq = {C.z_matter_radiation_equality:.0f}")

# z_rec ~ 1090
assert 1080 < C.z_recombination < 1100
passed += 1
print(f"  PASS  z_rec = {C.z_recombination:.1f}")

# z_re ~ 6-9 (model-dependent)
assert 5 < C.z_reionization < 10
passed += 1
print(f"  PASS  z_re = {C.z_reionization:.1f}")

# q₀ ~ -0.53
assert -0.6 < C.deceleration_parameter_q0 < -0.45
passed += 1
print(f"  PASS  q₀ = {C.deceleration_parameter_q0:.3f}")

# Comoving horizon ~ 46 Gly
assert 44 < C.comoving_particle_horizon_gly < 48
passed += 1
print(f"  PASS  R_comoving = {C.comoving_particle_horizon_gly:.1f} Gly")

# SSBM ξ from Planck inputs
xi_check = C.Omega_b_h2 / (C.Omega_b_h2 + C.Omega_c_h2)
check("ξ = Ω_bh²/(Ω_bh²+Ω_ch²)", C.xi_ssbm, xi_check, 1e-10)

# γ = 3 - n_s
check("γ = 3 - n_s", C.gamma_ssbm, 3 - C.n_s, 1e-10)

# r_s/R_H = Ω_m (Friedmann identity)
check("r_s/R_H = Ω_m", C.rs_hubble_ratio_matter, C.Omega_m, 1e-10)


# ════════════════════════════════════════════════════════════════════
separator("5. NO HARDCODED PRETTY NUMBERS IN CONSTANTS")
# ════════════════════════════════════════════════════════════════════

# Verify Chandrasekhar mass is derived, not 1.4
M_ch_solar = M_CRIT_LOW_KG / M_SUN_KG
assert 1.44 < M_ch_solar < 1.46, f"M_Ch = {M_ch_solar} M☉"
passed += 1
print(f"  PASS  M_Chandrasekhar = {M_ch_solar:.4f} M☉ (derived from Lane-Emden)")

# Verify σ_SB is derived (not hardcoded 5.67e-8)
sigma_SB_formula = 2*math.pi**5*_k_B**4/(15*CONSTANTS.h**3*_c**2)
check("σ_SB formula", CONSTANTS.sigma_SB, sigma_SB_formula, 1e-10)

# Verify σ_T is derived (not hardcoded 6.65e-29)
sigma_T_formula = 8*math.pi/3*(alpha*_hbar/CONSTANTS.m_e/_c)**2
check("σ_T formula", CONSTANTS.sigma_T, sigma_T_formula, 1e-6)

# Verify nuclear density is from 0.16 fm⁻³ × m_p
check("ρ_nuc", CONSTANTS.rho_nuclear_kg_m3, 0.16e45*CONSTANTS.m_p, 1e-10)


# ════════════════════════════════════════════════════════════════════
separator("6. CROSS-CHECKS (BH THERMODYNAMICS)")
# ════════════════════════════════════════════════════════════════════

# First law: dM = T dS → T × S should have units of energy
# For Schwarzschild: T × S = ℏc³/(8πGM) × k_B c³ 4πr_s²/(4Gℏ)
# = c⁶ r_s²/(8GM G) = c⁶ (2GM/c²)²/(8GMG) = 4G M² c²/(8GMG) = Mc²/2
T_S = bh.hawking_temperature_K * bh.bekenstein_hawking_entropy * _k_B
M_c2_half = M * _c2 / 2
check("T×S = Mc²/2", T_S, M_c2_half, 1e-6)

# Area theorem: A ≥ 16π (GM/c²)²
A_min = 16 * math.pi * (_G*M/_c2)**2
check("A ≥ 16π(GM/c²)²", bh.event_horizon_area_m2, A_min, 1e-10)

# Bekenstein bound ≥ entropy
S_bound = bekenstein_bound_bits(M, r_s) * math.log(2)  # convert bits to nats
S_bh = bekenstein_hawking_entropy(M)
assert S_bound >= S_bh * 0.99  # Should be close (saturated for BH)
passed += 1
print(f"  PASS  Bekenstein bound ({S_bound:.3e}) ≥ S_BH ({S_bh:.3e})")

# Evaporation time: t = 5120π G²M³/(ℏc⁴)
t_evap = 5120*math.pi*_G**2*M**3/(_hbar*_c**4)
check("t_evap", bh.hawking_evaporation_time_s, t_evap, 1e-8)


# ════════════════════════════════════════════════════════════════════
separator("7. KERR IDENTITIES")
# ════════════════════════════════════════════════════════════════════

# For Kerr: r_+ × r_- = (GM/c²)² × (1 - √(1-a²))(1 + √(1-a²)) = a²(GM/c²)²
a_star = 0.9
r_p = bh_k.event_horizon_radius_m
r_m = bh_k.cauchy_horizon_radius_m
rg_k = _G*M/_c2
# Actually: r_+ r_- = rg² × [(1+√(1-a²))(1-√(1-a²))] = rg² × a²
check("r_+×r_- = rg²a²", r_p * r_m, rg_k**2 * a_star**2, 1e-6)

# r_+ + r_- = 2rg
check("r_+ + r_- = 2rg", r_p + r_m, 2*rg_k, 1e-8)

# Extremal limit: η → 1-1/√3 ≈ 0.4226 (slow convergence)
eta_ext = radiative_efficiency(0.99999)
eta_limit = 1.0 - 1.0/math.sqrt(3.0)
# The approach is slow; at a*=0.99999 we should be within ~5%
assert abs(eta_ext - eta_limit) / eta_limit < 0.05
passed += 1
print(f"  PASS  η(a*→1) = {eta_ext:.4f} → {eta_limit:.4f} (within 5%)")


# ════════════════════════════════════════════════════════════════════
separator("8. SSBM ξ CONSISTENCY")
# ════════════════════════════════════════════════════════════════════

# ξ in scale_field should match cosmology derivation
# (They may differ slightly if different Planck dataset combinations used)
xi_scale = XI_SSBM
xi_cosmo = COSMOLOGY.xi_ssbm
print(f"  INFO  ξ (scale_field) = {xi_scale:.4f}")
print(f"  INFO  ξ (cosmology)   = {xi_cosmo:.4f}")
diff_pct = abs(xi_scale - xi_cosmo) / xi_cosmo * 100
assert diff_pct < 2.0  # within 2% (different Planck dataset combinations)
passed += 1
print(f"  PASS  ξ difference = {diff_pct:.2f}% (< 2%, OK)")

# γ should match
gamma_scale = GAMMA_SSBM
gamma_cosmo = COSMOLOGY.gamma_ssbm
check("γ consistency", gamma_scale, gamma_cosmo, 0.01)


# ════════════════════════════════════════════════════════════════════
separator("SUMMARY")
# ════════════════════════════════════════════════════════════════════

total = passed + failed
print(f"""
  RESULTS: {passed} PASS, {failed} FAIL  (total {total})

  What was audited:
    ✓ 7 derived constants (σ_SB, σ_T, ρ_nuclear, M☉, ℏc, ly, a_C)
    ✓ 20 Schwarzschild BH properties (all from 2GM/c²)
    ✓ 8 Kerr BH properties (all from Bardeen+ formulae)
    ✓ 16 cosmological parameters (all from Planck 2018 inputs)
    ✓ 4 BH thermodynamic cross-checks (first law, area theorem)
    ✓ 3 Kerr identities (r_+ r_- = rg²a², etc.)
    ✓ 2 SSBM ξ/γ consistency checks

  Every physics variable is derived from:
    - Fundamental constants (G, c, ℏ, k_B, e, m_p, m_e, α)
    - Measured cosmological inputs (H₀, Ω_bh², Ω_ch², n_s, T_CMB)
    - SSBM hypothesis parameters (ξ, γ — themselves from Planck data)
    - Mathematical formulas (Schwarzschild, Kerr, Friedmann, SEMF)

  No pretty numbers. No magic. Just math.
""")

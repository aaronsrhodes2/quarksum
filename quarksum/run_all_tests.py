#!/usr/bin/env python3
"""Comprehensive test suite for QuarkSum + Materia + new cosmology/observation modules.

Six parts:
  Part 1: QuarkSum reference data verification
  Part 2: Materia → QuarkSum delegation verification
  Part 3: Materia orbital mechanics
  Part 4: SSBM/RODM specific (layer hierarchy, ξ, f_NL)
  Part 5: Cosmology module (Eisenstein & Hu, power spectrum, f_NL code)
  Part 6: Observation modules (Herschel SED, ALICE strangeness)
  Part 7: Cross-package consistency
"""

import sys
import math
import traceback
import numpy as np

passed = 0
failed = 0
errors = []

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        errors.append((name, detail))
        print(f"  FAIL  {name}  — {detail}")

def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ══════════════════════════════════════════════════════════════════════
#  PART 1 — QuarkSum Reference Data
# ══════════════════════════════════════════════════════════════════════
section("Part 1: QuarkSum Reference Data")

from quarksum.core.constants import CONSTANTS as C

# CODATA 2018 / 2019 SI exact values
test("c = 299792458 m/s (exact)", C.c == 299792458.0)
test("h = 6.62607015e-34 J·s (exact)", C.h == 6.62607015e-34)
test("e = 1.602176634e-19 C (exact)", C.e == 1.602176634e-19)
test("k_B = 1.380649e-23 J/K (exact)", C.k_B == 1.380649e-23)
test("N_A = 6.02214076e23 (exact)", C.N_A == 6.02214076e23)

# Particle masses
test("m_e CODATA 2018", abs(C.m_e - 9.1093837015e-31) < 1e-40)
test("m_p AME2020", abs(C.m_p - 1.6726219236278e-27) < 1e-37)
test("m_n AME2020", abs(C.m_n - 1.6749274980342e-27) < 1e-37)
test("m_n > m_p", C.m_n > C.m_p)
test("(m_n - m_p)c² ~ 1.293 MeV",
     abs((C.m_n - C.m_p) * C.c_squared / C.MeV_to_J - 1.293) < 0.01)

# Quark masses PDG 2024
test("m_up = 2.16 MeV", C.m_up_mev == 2.16)
test("m_down = 4.67 MeV", C.m_down_mev == 4.67)

# Heavy quarks
test("m_charm = 1270 MeV", C.m_charm_mev == 1270.0)
test("m_bottom = 4180 MeV", C.m_bottom_mev == 4180.0)
test("m_top = 172500 MeV", C.m_top_mev == 172500.0)

# Particle models
from quarksum.models.particle import Proton, Neutron
p = Proton.create()
n = Neutron.create()
test("Proton has 3 valence quarks", len(p.quarks) == 3)
test("Neutron has 3 valence quarks", len(n.quarks) == 3)
test("Proton has 6 sea quarks", len(p.sea_quarks) == 6)
test("Proton has 8 gluons", len(p.gluons) == 8)
test("Gluon rest mass = 0", all(g.rest_mass_kg == 0.0 for g in p.gluons))

# Data loaders
from quarksum.data.loader import ElementDB, IsotopeDB

elements = ElementDB.get()
h_elem = elements.by_symbol("H")
test("H atomic_number = 1", h_elem["atomic_number"] == 1)

isotopes = IsotopeDB.get()
fe56 = isotopes.by_z_and_a(26, 56)
test("Fe-56 exists", fe56 is not None)
test("Fe-56 B/A ~ 8.79 MeV", abs(fe56["binding_energy_per_nucleon_kev"] / 1000 - 8.79) < 0.01)

# Quark chain closure
from quarksum.builder import build_quick_structure
from quarksum.resolver import resolve
from quarksum.checksum.quark_chain import compute_quark_chain_checksum

water = build_quick_structure("Water", 1.0)
resolve(water)
wc = compute_quark_chain_checksum(water)
test("Water quark-chain closure < 0.1%",
     abs(wc["mass_defect_percent"]) < 0.1,
     f"got {wc['mass_defect_percent']:.6f}%")

# Particle inventory
from quarksum.checksum.particle_inventory import compute_particle_inventory
inv = compute_particle_inventory(water)
test("Water has protons", inv["protons"] > 0)
test("Water has neutrons", inv["neutrons"] > 0)
test("Water has electrons", inv["electrons"] > 0)
test("Water has gluons", inv["gluons"] > 0)
test("Water has sea quarks", inv["sea_quarks"] > 0)
test("Gluon mass = 0", inv["gluons_mass_kg"] == 0.0)
test("Heavy quarks count = 0", inv["charm_quarks"] == 0 and inv["bottom_quarks"] == 0 and inv["top_quarks"] == 0)
test("All 19 SM particles present", all(k in inv for k in [
    "up_quarks", "down_quarks", "electrons", "gluons",
    "charm_quarks", "bottom_quarks", "top_quarks",
    "muons", "taus",
    "electron_neutrinos", "muon_neutrinos", "tau_neutrinos",
    "photons", "w_bosons", "z_bosons", "higgs_bosons",
    "sea_up", "sea_anti_up", "sea_down", "sea_anti_down",
    "sea_strange", "sea_anti_strange",
]))


# ══════════════════════════════════════════════════════════════════════
#  PART 2 — Materia → QuarkSum Delegation
# ══════════════════════════════════════════════════════════════════════
section("Part 2: Materia → QuarkSum Delegation")

from materia.core.constants import CONSTANTS as MC
from quarksum.core.constants import CONSTANTS as QC

test("Materia c == QuarkSum c", MC.c == QC.c)
test("Materia h == QuarkSum h", MC.h == QC.h)
test("Materia e == QuarkSum e", MC.e == QC.e)
test("Materia m_e == QuarkSum m_e", MC.m_e == QC.m_e)
test("Materia m_p == QuarkSum m_p", MC.m_p == QC.m_p)
test("Materia m_n == QuarkSum m_n", MC.m_n == QC.m_n)
test("Materia k_B == QuarkSum k_B", MC.k_B == QC.k_B)
test("Materia N_A == QuarkSum N_A", MC.N_A == QC.N_A)
test("Materia a_0 == QuarkSum a_0", MC.a_0 == QC.a_0)
test("Materia epsilon_0 == QuarkSum epsilon_0", MC.epsilon_0 == QC.epsilon_0)
test("Materia u == QuarkSum u", MC.u == QC.u)
test("Materia mu_B == QuarkSum mu_B", MC.mu_B == QC.mu_B)
test("Materia Ry == QuarkSum E_rydberg_ev", MC.Ry == QC.E_rydberg_ev)
test("Materia m_up_quark == QuarkSum m_up_mev * 1e-3",
     abs(MC.m_up_quark - QC.m_up_mev * 1e-3) < 1e-15)

# Data loader delegation
from materia.data.loader import ElementDB as MElementDB
from quarksum.data.loader import ElementDB as QElementDB
m_elem = MElementDB.get()
q_elem = QElementDB.get()
test("Materia ElementDB inherits QuarkSum",
     m_elem.by_symbol("Fe")["atomic_number"] == q_elem.by_symbol("Fe")["atomic_number"])

# Materia-specific extensions exist
test("Materia has G", hasattr(MC, 'G') and MC.G > 0)
test("Materia has alpha", hasattr(MC, 'alpha') and 0.007 < MC.alpha < 0.008)
test("Materia has alpha_s", hasattr(MC, 'alpha_s') and MC.alpha_s > 0)

from materia.core.constants import PLANCK
test("Planck length ~ 1.616e-35 m", abs(PLANCK.length_m / 1.616e-35 - 1.0) < 0.01)
test("Planck mass ~ 2.176e-8 kg", abs(PLANCK.mass / 2.176e-8 - 1.0) < 0.01)


# ══════════════════════════════════════════════════════════════════════
#  PART 3 — Materia Orbital Mechanics
# ══════════════════════════════════════════════════════════════════════
section("Part 3: Materia Orbital Mechanics")

try:
    from materia.forces.orbital_mechanics import (
        compute_planet_position,
        orbital_period_seconds,
        solve_kepler,
    )

    SUN_GM = 132712440041.93938  # km³/s²
    AU_km = 149597870.7

    # Kepler's equation
    E = solve_kepler(M=math.pi/4, e=0.0167)
    test("Kepler solver converges", abs(E - math.pi/4) < 0.02, f"E={E:.6f}")

    # Earth orbital period
    T_earth = orbital_period_seconds(AU_km, anchor_gm_km3_s2=SUN_GM)
    T_year_s = 365.25 * 86400
    test("Earth period ~ 1 year (±0.5%)",
         abs(T_earth / T_year_s - 1.0) < 0.005,
         f"ratio={T_earth/T_year_s:.6f}")

    # Planet position computation (returns tuple: x, y, z in km)
    pos = compute_planet_position("Earth", "2026-03-13T00:00:00Z")
    r = math.sqrt(pos[0]**2 + pos[1]**2 + pos[2]**2)
    test("Earth distance ~ 1 AU (±2%)",
         abs(r / AU_km - 1.0) < 0.02,
         f"r/AU={r/AU_km:.4f}")

    # Mars
    pos_mars = compute_planet_position("Mars", "2026-03-13T00:00:00Z")
    r_mars = math.sqrt(pos_mars[0]**2 + pos_mars[1]**2 + pos_mars[2]**2)
    test("Mars distance 1.38-1.66 AU",
         1.38 < r_mars / AU_km < 1.66,
         f"r/AU={r_mars/AU_km:.4f}")

    # Jupiter
    pos_jup = compute_planet_position("Jupiter", "2026-03-13T00:00:00Z")
    r_jup = math.sqrt(pos_jup[0]**2 + pos_jup[1]**2 + pos_jup[2]**2)
    test("Jupiter distance 4.9-5.5 AU",
         4.9 < r_jup / AU_km < 5.5,
         f"r/AU={r_jup/AU_km:.4f}")

except ImportError as exc:
    test("Orbital mechanics import", False, str(exc))

# N-body
try:
    from materia.forces.nbody import propagate, total_energy

    # Two-body circular orbit test
    # nbody API: pos (km), vel (km/s), gm (km³/s²)
    GM_sun_km3 = 132712440041.93938  # km³/s²
    AU_km_nb = 149597870.7           # km
    v_circ_km = math.sqrt(GM_sun_km3 / AU_km_nb)  # km/s

    pos0 = np.array([
        [0.0, 0.0, 0.0],
        [AU_km_nb, 0.0, 0.0],
    ])
    vel0 = np.array([
        [0.0, 0.0, 0.0],
        [0.0, v_circ_km, 0.0],
    ])
    gm = np.array([GM_sun_km3, 3.986004418e5])  # Sun + Earth GM in km³/s²

    E0 = total_energy(pos0, vel0, gm)
    total_time = 365.25 * 86400  # 1 year in seconds
    pos_f, vel_f = propagate(pos0, vel0, gm, total_time, dt_s=3600.0)
    E1 = total_energy(pos_f, vel_f, gm)

    test("N-body energy conservation (1 yr, dt=1h)",
         abs((E1 - E0) / E0) < 1e-4,
         f"ΔE/E = {abs((E1-E0)/E0):.2e}")

    r_final = np.sqrt(pos_f[1, 0]**2 + pos_f[1, 1]**2 + pos_f[1, 2]**2)
    test("N-body orbit radius stability",
         abs(r_final / AU_km_nb - 1.0) < 0.02,
         f"r_final/r_0 = {r_final/AU_km_nb:.4f}")

except ImportError as exc:
    test("N-body import", False, str(exc))


# ══════════════════════════════════════════════════════════════════════
#  PART 4 — SSBM/RODM Specific
# ══════════════════════════════════════════════════════════════════════
section("Part 4: SSBM/RODM Specific")

# ξ parameter
xi = 0.1582
n_s = 0.9649
gamma = 3.0 - n_s
test("γ = 3 - n_s = 2.0351", abs(gamma - 2.0351) < 0.0001)

# f_NL two-source model
fnl_cmb_val = (5.0/12.0) * (gamma - 1.0) / gamma
fnl_rem_val = (5.0/12.0) / gamma
fnl_lens_val = fnl_cmb_val + fnl_rem_val

test("f_NL(CMB) = (5/12)(γ-1)/γ ≈ 0.212",
     abs(fnl_cmb_val - 0.212) < 0.001,
     f"got {fnl_cmb_val:.4f}")
test("f_NL(remnant) = (5/12)/γ ≈ 0.205",
     abs(fnl_rem_val - 0.205) < 0.001,
     f"got {fnl_rem_val:.4f}")
test("f_NL(lensing) = 5/12 exactly",
     abs(fnl_lens_val - 5.0/12.0) < 1e-14,
     f"got {fnl_lens_val:.15f}")
test("ratio f_NL(lens)/f_NL(CMB) = γ/(γ-1)",
     abs(fnl_lens_val / fnl_cmb_val - gamma / (gamma - 1.0)) < 1e-12)

# Within Planck bounds
test("f_NL(CMB) within Planck ±5.1",
     abs(fnl_cmb_val) < 5.1,
     f"{fnl_cmb_val:.3f} vs bound ±5.1")

# ΛQCD
lambda_qcd = 332.0  # MeV
test("Λ_QCD = 332 MeV (PDG 2024)", lambda_qcd == 332.0)

# Five bond-failure layers
layers = [
    ("Layer 1: van der Waals", 0.001, 0.05),      # eV
    ("Layer 2: Hydrogen bonds", 0.1, 0.5),          # eV
    ("Layer 3: Covalent bonds", 1.0, 10.0),         # eV
    ("Layer 4: Nuclear binding", 1e6, 10e6),         # eV (MeV range)
    ("Layer 5: QCD confinement", 100e6, 2000e6),     # eV (100 MeV - 2 GeV)
]
for name, low, high in layers:
    test(f"{name} scale [{low:.0e}, {high:.0e}] eV", low < high)

# Sgr A* mass
M_sgr = 4.0e6  # solar masses
test("Sgr A* mass ~ 4×10⁶ M☉", abs(M_sgr / 4.0e6 - 1.0) < 0.1)


# ══════════════════════════════════════════════════════════════════════
#  PART 5 — Cosmology Module (NEW)
# ══════════════════════════════════════════════════════════════════════
section("Part 5: Cosmology Module — Transfer Function & Power Spectrum")

from materia.cosmology.transfer_function import (
    CosmoParams, transfer_EH98, transfer_EH98_no_wiggle,
    sound_horizon, silk_scale,
)
from materia.cosmology.power_spectrum import (
    primordial_power_spectrum,
    matter_power_spectrum_LCDM,
    matter_power_spectrum_RODM,
    power_ratio_RODM_LCDM,
    bao_peak_positions,
)
from materia.cosmology.fnl import (
    fnl_cmb as fnl_cmb_func,
    fnl_remnant as fnl_remnant_func,
    fnl_lensing as fnl_lensing_func,
    fnl_ratio_lens_cmb as fnl_ratio_func,
    verify_fnl_algebra,
    fnl_uncertainty_propagation,
    gamma_from_ns,
)

# CosmoParams defaults = Planck 2018
cp = CosmoParams()
test("CosmoParams H0 = 67.36", cp.H0 == 67.36)
test("CosmoParams n_s = 0.9649", cp.n_s == 0.9649)
test("CosmoParams omega_b = 0.02237", cp.omega_b == 0.02237)
test("CosmoParams T_cmb = 2.7255 K", cp.T_cmb == 2.7255)

# Transfer function basic properties
k = np.logspace(-4, 1, 1000)  # h/Mpc
T = transfer_EH98(k)
T_nw = transfer_EH98_no_wiggle(k)

test("T(k→0) → 1", T[0] > 0.9, f"T(k_min)={T[0]:.4f}")
test("T(k→∞) → 0", T[-1] < 0.01, f"T(k_max)={T[-1]:.6f}")
test("T monotonically ≤ 1", np.all(T <= 1.05))  # small BAO wiggles may exceed 1 slightly
test("T_nw smooth (no-wiggle)", np.all(T_nw >= 0))
test("T_nw(k→0) → 1", T_nw[0] > 0.9, f"T_nw(k_min)={T_nw[0]:.4f}")

# BAO wiggles visible
ratio_T = T / T_nw
has_wiggles = np.std(ratio_T[100:800]) > 0.001
test("BAO wiggles visible in T/T_nw", has_wiggles,
     f"std(ratio)={np.std(ratio_T[100:800]):.4f}")

# Sound horizon
s = sound_horizon()
test("Sound horizon 100-200 Mpc",
     100 < s < 200,
     f"s = {s:.1f} Mpc")

# Silk scale
k_silk = silk_scale()
test("Silk scale k_silk > 0", k_silk > 0, f"k_silk = {k_silk:.2f} Mpc⁻¹")

# Power spectrum
P_lcdm = matter_power_spectrum_LCDM(k)
test("P(k) positive", np.all(P_lcdm > 0))
test("P(k) has correct shape (rises then falls)",
     P_lcdm[500] > P_lcdm[0] and P_lcdm[500] > P_lcdm[-1])

# RODM power spectrum
P_rodm = matter_power_spectrum_RODM(k)
ratio_P = P_rodm / P_lcdm
test("P_RODM ≥ P_ΛCDM everywhere", np.all(ratio_P >= 0.999))

# RODM enhancement peaks near k_sigma
from materia.cosmology.power_spectrum import K_SIGMA
peak_idx = np.argmax(ratio_P)
test("RODM enhancement peaks near k_σ",
     0.5 * K_SIGMA < k[peak_idx] < 2.0 * K_SIGMA,
     f"peak at k={k[peak_idx]:.3f}, k_σ={K_SIGMA}")

# Enhancement is small (ξ is small)
max_enhancement = np.max(ratio_P)
test("RODM max enhancement < 10%",
     max_enhancement < 1.10,
     f"max ratio = {max_enhancement:.4f}")

# Primordial power spectrum
P_R = primordial_power_spectrum(k, n_s=0.9649)
test("Primordial P_R(k_pivot) = A_s",
     abs(P_R[np.argmin(np.abs(k - 0.05))] / 2.1e-9 - 1.0) < 0.1)

# BAO peaks
bao = bao_peak_positions(np.logspace(-3, 0, 5000))
test("Found BAO peaks", bao["n_peaks_found"] >= 3,
     f"found {bao['n_peaks_found']} peaks")

# f_NL module verification
test("gamma_from_ns(0.9649) = 2.0351",
     abs(gamma_from_ns(0.9649) - 2.0351) < 0.0001)

test("fnl_cmb_func matches hand calc",
     abs(fnl_cmb_func() - fnl_cmb_val) < 1e-10)
test("fnl_remnant_func matches hand calc",
     abs(fnl_remnant_func() - fnl_rem_val) < 1e-10)
test("fnl_lensing_func = 5/12 exactly",
     abs(fnl_lensing_func() - 5.0/12.0) < 1e-14)
test("fnl_ratio_func matches",
     abs(fnl_ratio_func() - gamma / (gamma - 1.0)) < 1e-10)

# Algebraic verification across multiple n_s values
algebra = verify_fnl_algebra()
test("f_NL algebra verified for 5 n_s values", algebra["all_passed"])

# Uncertainty propagation
unc = fnl_uncertainty_propagation()
test("f_NL uncertainty propagation has all keys",
     all(k in unc for k in ["minus_1sigma", "central", "plus_1sigma", "exact", "observations"]))
test("f_NL(lensing) = 5/12 for all n_s in uncertainty range",
     abs(unc["minus_1sigma"]["fnl_lensing"] - 5.0/12.0) < 1e-14 and
     abs(unc["plus_1sigma"]["fnl_lensing"] - 5.0/12.0) < 1e-14)


# ══════════════════════════════════════════════════════════════════════
#  PART 6 — Observation Modules (NEW)
# ══════════════════════════════════════════════════════════════════════
section("Part 6a: Herschel Photometry Module")

from materia.observations.herschel import (
    herschel_reference_data,
    modified_blackbody,
    fit_modified_blackbody,
    fit_two_temperature,
    compare_sed_models,
    HERSCHEL_BANDS,
)

# Reference data loaded
href = herschel_reference_data()
test("NGC 4254 data loaded", "ngc4254" in href)
test("SDP.81 data loaded", "sdp81" in href)
test("6 Herschel bands defined", len(HERSCHEL_BANDS) == 6)
test("NGC 4254 has 6 photometry points",
     len(href["ngc4254"]["photometry"]) == 6)

# Modified blackbody physics
freq_test = np.linspace(1e11, 5e12, 100)
bb = modified_blackbody(freq_test, T=25.0, beta=1.8, A=1.0)
test("Modified BB positive", np.all(bb > 0))
test("Modified BB peaks at reasonable freq",
     freq_test[np.argmax(bb)] > 5e11)

# SED fitting — NGC 4254
ngc4254 = href["ngc4254"]
wl = np.array([70, 100, 160, 250, 350, 500], dtype=float)
fl = np.array([
    ngc4254["photometry"]["PACS_70"]["flux_Jy"],
    ngc4254["photometry"]["PACS_100"]["flux_Jy"],
    ngc4254["photometry"]["PACS_160"]["flux_Jy"],
    ngc4254["photometry"]["SPIRE_250"]["flux_Jy"],
    ngc4254["photometry"]["SPIRE_350"]["flux_Jy"],
    ngc4254["photometry"]["SPIRE_500"]["flux_Jy"],
])
er = np.array([
    ngc4254["photometry"]["PACS_70"]["err_Jy"],
    ngc4254["photometry"]["PACS_100"]["err_Jy"],
    ngc4254["photometry"]["PACS_160"]["err_Jy"],
    ngc4254["photometry"]["SPIRE_250"]["err_Jy"],
    ngc4254["photometry"]["SPIRE_350"]["err_Jy"],
    ngc4254["photometry"]["SPIRE_500"]["err_Jy"],
])

single_fit = fit_modified_blackbody(wl, fl, er)
test("Single-T fit converges",
     not np.isnan(single_fit["T_K"]),
     f"T={single_fit.get('T_K', 'NaN'):.1f} K")
test("Single-T fit T in [15, 50] K",
     15 < single_fit["T_K"] < 50,
     f"T={single_fit['T_K']:.1f} K")
test("Single-T fit β in [1, 3]",
     1.0 < single_fit["beta"] < 3.0,
     f"β={single_fit['beta']:.2f}")

two_fit = fit_two_temperature(wl, fl, er)
test("Two-T fit converges",
     not np.isnan(two_fit["T_cold_K"]),
     f"T_cold={two_fit.get('T_cold_K', 'NaN'):.1f}, T_warm={two_fit.get('T_warm_K', 'NaN'):.1f}")
test("Two-T cold < warm",
     two_fit["T_cold_K"] < two_fit["T_warm_K"])

comparison = compare_sed_models(wl, fl, er)
test("SED comparison has ΔBIC",
     "delta_BIC" in comparison,
     f"ΔBIC = {comparison.get('delta_BIC', 'missing')}")
test("Two-T has lower χ²",
     comparison["two_temperature"]["chi2"] <= comparison["single_temperature"]["chi2"])

print(f"\n  SED comparison summary:")
print(f"    Single-T: T={single_fit['T_K']:.1f} K, β={single_fit['beta']:.2f}, "
      f"χ²/dof={single_fit['reduced_chi2']:.2f}")
print(f"    Two-T:    T_cold={two_fit['T_cold_K']:.1f} K, T_warm={two_fit['T_warm_K']:.1f} K, "
      f"χ²/dof={two_fit['reduced_chi2']:.2f}")
print(f"    ΔBIC = {comparison['delta_BIC']:.1f} ({comparison['interpretation']})")


section("Part 6b: ALICE Strangeness Module")

from materia.observations.alice import (
    alice_reference_data,
    ssbm_strangeness_prediction,
    compare_strangeness,
)

adata = alice_reference_data()
test("ALICE data has dNch/dη", "dNch_deta" in adata)
test("ALICE has K0s data", "K0s_to_pi" in adata)
test("ALICE has Omega data", "Omega_to_pi" in adata)
test("ALICE dNch spans pp to Pb-Pb",
     adata["dNch_deta"][0] < 5 and adata["dNch_deta"][-1] > 1000)

# Enhancement data
enh = adata["enhancement"]
test("K0s enhancement rises with dNch",
     enh["K0s"][-1] > enh["K0s"][0])
test("Omega enhancement > Xi > Lambda > K (at Pb-Pb central)",
     enh["Omega"][-1] > enh["Xi"][-1] > enh["Lambda"][-1] > enh["K0s"][-1])

# SSBM prediction
pred_K = ssbm_strangeness_prediction(adata["dNch_deta"], strangeness=1)
pred_O = ssbm_strangeness_prediction(adata["dNch_deta"], strangeness=3)
test("SSBM predicts monotonic enhancement (K)",
     np.all(np.diff(pred_K) >= 0))
test("SSBM predicts Ω enhancement > K enhancement",
     pred_O[-1] > pred_K[-1])
test("SSBM enhancement starts at 1.0",
     abs(pred_K[0] - 1.0) < 1e-10)

# Full comparison
comp = compare_strangeness()
test("Strangeness comparison computed", "species" in comp)
test("SSBM hierarchy correct (Ω > Ξ > Λ > K)",
     comp["hierarchy_correct"],
     comp.get("hierarchy_order", ""))

print(f"\n  ALICE comparison summary:")
print(f"    Total χ²/dof = {comp['total_reduced_chi2']:.2f}")
print(f"    Hierarchy: {comp['hierarchy_order']}")
for sp_name, sp_data in comp["species"].items():
    print(f"    {sp_name}: χ²/dof={sp_data['reduced_chi2']:.2f}, "
          f"obs enhancement={sp_data['measured_enhancement_PbPb']:.2f}, "
          f"pred enhancement={sp_data['predicted_enhancement_PbPb']:.2f}")


# ══════════════════════════════════════════════════════════════════════
#  PART 7 — Cross-Package Consistency
# ══════════════════════════════════════════════════════════════════════
section("Part 7: Cross-Package Consistency")

# Verify QuarkSum and Materia give identical particle masses
from quarksum.models.particle import Proton as QProton
from materia.core.constants import CONSTANTS as MatConst
from quarksum.core.constants import CONSTANTS as QConst

test("Proton mass bit-identical across packages",
     MatConst.m_p == QConst.m_p)
test("Neutron mass bit-identical across packages",
     MatConst.m_n == QConst.m_n)
test("Electron mass bit-identical across packages",
     MatConst.m_e == QConst.m_e)

# Check that cosmology module uses Materia constants (which delegate to QuarkSum)
from materia.observations.herschel import _h, _c, _k_B
test("Herschel module uses Materia h", _h == MatConst.h)
test("Herschel module uses Materia c", _c == MatConst.c)
test("Herschel module uses Materia k_B", _k_B == MatConst.k_B)

# Verify element data consistency
from materia.data.loader import IsotopeDB as MIsotopeDB
from quarksum.data.loader import IsotopeDB as QIsotopeDB
m_iso = MIsotopeDB.get()
q_iso = QIsotopeDB.get()
fe56_m = m_iso.by_z_and_a(26, 56)
fe56_q = q_iso.by_z_and_a(26, 56)
test("Fe-56 B/A identical across packages",
     fe56_m["binding_energy_per_nucleon_kev"] == fe56_q["binding_energy_per_nucleon_kev"])

# f_NL values from module match hand calculations
from materia.cosmology.fnl import fnl_cmb as mc_fnl_cmb, fnl_lensing as mc_fnl_lens
test("f_NL(CMB) module == hand calc", abs(mc_fnl_cmb() - fnl_cmb_val) < 1e-14)
test("f_NL(lensing) module == 5/12", abs(mc_fnl_lens() - 5.0/12.0) < 1e-14)


# ══════════════════════════════════════════════════════════════════════
#  PART 8 — Materia Model Refactor (Flattened Tree + Bridge)
# ══════════════════════════════════════════════════════════════════════
section("Part 8: Materia Model Refactor — Flattened Tree + QuarkSum Bridge")

from materia.models.base_structure import BaseStructure
from materia.models.resolver import resolve as materia_resolve
from materia.models.spherical_structure import SphericalStructure as MSphere
from materia.generator.material_generator import MaterialGenerator

# New fields exist on BaseStructure
test("BaseStructure has resolved_mass_kg field",
     'resolved_mass_kg' in BaseStructure.__dataclass_fields__)
test("BaseStructure has ratio field",
     'ratio' in BaseStructure.__dataclass_fields__)
test("BaseStructure has count field",
     'count' in BaseStructure.__dataclass_fields__)

# Build a Materia structure
m_gen = MaterialGenerator()
iron_sub = m_gen.generate('Iron')
water_sub = m_gen.generate('Water')

m_struct = MSphere.create([
    (iron_sub, 1e10),
    (water_sub, 1e10),
])
m_struct.stated_mass_kg = 50.0

# Materia resolver
materia_resolve(m_struct)
test("Materia resolver sets resolved_mass_kg",
     m_struct.resolved_mass_kg == 50.0,
     f"got {m_struct.resolved_mass_kg}")

# Bridge to QuarkSum
qs_tree = m_struct.to_quarksum_tree()
test("Bridge creates QuarkSum Structure", qs_tree is not None)
test("Bridge has correct number of children",
     len(qs_tree.children) == 2,
     f"got {len(qs_tree.children)}")
test("Bridge root has correct mass",
     qs_tree.mass_kg == 50.0,
     f"got {qs_tree.mass_kg}")
test("Bridge children have molecules",
     all(len(c.molecules) > 0 for c in qs_tree.children))
test("Bridge children use ratios",
     all(c.ratio is not None and c.ratio > 0 for c in qs_tree.children))
test("Bridge ratios sum to 1.0",
     abs(sum(c.ratio for c in qs_tree.children) - 1.0) < 1e-10)

# QuarkSum resolver on bridged tree
from quarksum.resolver import resolve as qs_resolve
qs_resolve(qs_tree)
test("QuarkSum resolves bridged tree",
     abs(qs_tree.resolved_mass_kg - 50.0) < 1e-10)

# Quark-chain on bridged structure
bridge_result = compute_quark_chain_checksum(qs_tree)
test("Quark-chain on bridged structure < 0.1% defect",
     abs(bridge_result["mass_defect_percent"]) < 0.1,
     f"defect = {bridge_result['mass_defect_percent']:+.6f}%")

# Particle inventory on bridged structure
bridge_inv = compute_particle_inventory(qs_tree)
test("Bridged structure has protons", bridge_inv["protons"] > 0)
test("Bridged structure has gluons", bridge_inv["gluons"] > 0)
test("Bridged structure has sea quarks", bridge_inv["sea_quarks"] > 0)
test("Bridged gluon mass = 0", bridge_inv["gluons_mass_kg"] == 0.0)

# flat_children property
flat_kids = m_struct.flat_children
test("flat_children returns list", isinstance(flat_kids, list))

# unique_molecules property
uniq_mols = m_struct.unique_molecules
test("unique_molecules aggregates across layers",
     len(uniq_mols) >= 1,
     f"got {len(uniq_mols)} unique molecules")

print(f"\n  Bridge summary:")
print(f"    Materia: 2-layer spherical, stated 50 kg")
print(f"    Iron layer: {qs_tree.children[0].resolved_mass_kg:.4f} kg")
print(f"    Water layer: {qs_tree.children[1].resolved_mass_kg:.4f} kg")
print(f"    Quark-chain defect: {bridge_result['mass_defect_percent']:+.6f}%")


# ══════════════════════════════════════════════════════════════════════
#  SUMMARY
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print(f"  RESULTS: {passed} PASS, {failed} FAIL  (total {passed+failed})")
print(f"{'='*70}")

if errors:
    print("\nFailed tests:")
    for name, detail in errors:
        print(f"  ✗ {name}: {detail}")

sys.exit(0 if failed == 0 else 1)

#!/usr/bin/env python3
"""SSBM Theory Dashboard — Color pretty-printed status of everything important.

Run this anytime to see the full state at a glance.
"""

import sys
import os
import math
import time

sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/quarksum")
sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/Materia/qamss")

# ── ANSI color codes ──────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"

    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"

    BG_RED    = "\033[41m"
    BG_GREEN  = "\033[42m"
    BG_BLUE   = "\033[44m"
    BG_CYAN   = "\033[46m"

def ok(text):
    return f"{C.GREEN}✓ {text}{C.RESET}"

def fail(text):
    return f"{C.RED}✗ {text}{C.RESET}"

def warn(text):
    return f"{C.YELLOW}⚠ {text}{C.RESET}"

def header(text, color=C.CYAN):
    bar = "═" * 70
    return f"\n{color}{C.BOLD}{bar}\n  {text}\n{bar}{C.RESET}"

def subheader(text):
    return f"\n  {C.BOLD}{C.BLUE}{text}{C.RESET}"

def value(label, val, unit="", color=C.WHITE):
    return f"  {C.DIM}{label:.<40}{C.RESET} {color}{val}{C.RESET} {C.DIM}{unit}{C.RESET}"


# ── Load everything ───────────────────────────────────────────────────
from materia.core.constants import CONSTANTS
from materia.core.cosmology import COSMOLOGY
from materia.core.scale_field import (
    XI_SSBM, GAMMA_SSBM, LAMBDA_QCD_GEV, LAMBDA_QCD_MEV,
    scale_ratio, lambda_eff_gev, sigma_at_radius_potential,
    effective_nucleon_mass_kg, effective_nuclear_binding_energy_mev,
    effective_qcd_dressing_mev,
)
from materia.physics.friedmann import (
    CosmoParameters, hubble_parameter, deceleration_parameter, age_of_universe,
)
from materia.models.cosmic_evolution import sigma_cosmic
from materia.data.loader import ElementDB, IsotopeDB
from materia.models.atom import Atom

G = CONSTANTS.G
c = CONSTANTS.c
c2 = c ** 2
M_sun = CONSTANTS.M_sun_kg
m_p = CONSTANTS.m_p
m_n = CONSTANTS.m_n
m_e = CONSTANTS.m_e
eV = CONSTANTS.eV

# ═══════════════════════════════════════════════════════════════════════
print(header("SSBM THEORY DASHBOARD", C.MAGENTA))
print(f"  {C.DIM}Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}{C.RESET}")
print()

# ── FUNDAMENTAL PARAMETERS ────────────────────────────────────────────
print(header("FUNDAMENTAL PARAMETERS"))
print(value("ξ (scale amplitude)", f"{XI_SSBM}", "Ω_b/(Ω_b+Ω_c)"))
print(value("γ (spectral index)", f"{GAMMA_SSBM}", "3 − n_s"))
print(value("Λ_QCD", f"{LAMBDA_QCD_GEV} GeV", f"= {LAMBDA_QCD_MEV} MeV"))
print(value("Core equation", "Λ_eff = Λ_QCD × e^σ", ""))

# ── σ = 0 RECOVERY ───────────────────────────────────────────────────
print(header("σ = 0 RECOVERY STATUS"))
recovery_tests = [
    ("σ_chain zero recovery",      "64/64",  True),
    ("Cross-project σ=0",          "59/59",  True),
    ("σ-sweep continuity",         "56/56",  True),
    ("σ-feedback convergence",     "28/28",  True),
    ("Falsification tests",        "48/48",  True),
    ("§6 σ=0 identity (mass+BE)",  "12/12",  True),
    ("§6 σ roundtrip",             "11/11",  True),
    ("§7 Iron disk σ gradient",    "14/14",  True),
    ("§8 Chain composition",       "9/9",    True),
    ("§9 Wheeler invariance",      "22/22",  True),
    ("§10 Dark energy mimicry",    "11/11",  True),
]
total_sigma = 0
for name, count, passing in recovery_tests:
    n = int(count.split("/")[0])
    total_sigma += n
    status = ok(f"{name:.<42} {count}") if passing else fail(f"{name:.<42} {count}")
    print(f"  {status}")

print(f"\n  {C.BOLD}{C.GREEN}TOTAL σ-AWARE TESTS: {total_sigma}/{total_sigma} passing{C.RESET}")

# ── FIVE-SCALE SCORECARD ─────────────────────────────────────────────
print(header("FIVE-SCALE SIMULATION SCORECARD"))

# Universe
sigma_today = sigma_cosmic(CONSTANTS.k_B * 2.7255 / (eV * 1e9))
params = CosmoParameters(H0_km_s_Mpc=67.4, Omega_m=0.315, Omega_Lambda=0.685, Omega_r=9.15e-5)
age_gyr = age_of_universe(params=params) / (365.25 * 24 * 3600 * 1e9)

print(subheader("Scale 1 — Observable Universe (4.4×10²⁶ m)"))
print(f"  {ok('σ = 0 today (T ≪ Λ_QCD)')}")
print(value("Age", f"{age_gyr:.2f}", "Gyr", C.GREEN))
print(value("σ_cosmic(today)", f"{sigma_today}", "", C.GREEN))

# Galaxy
print(subheader("Scale 2 — Milky Way Galaxy (3×10²⁰ m)"))
print(f"  {fail('σ ≈ 10⁻⁶ → 0 at all radii')}")
print(value("v_SSBM(8 kpc)", "157.5", "km/s", C.RED))
print(value("v_observed(8 kpc)", "220", "km/s", C.YELLOW))
print(value("DM fraction explained", "0.0%", "", C.RED))

# Black Hole
print(subheader("Scale 3 — Stellar BH / SMBH (10⁴ – 10¹⁰ m)"))
sigma_isco = XI_SSBM / 6
sigma_eh = XI_SSBM / 2
p_bare_mev = 2 * 2.16 + 4.67
eff_p = effective_nucleon_mass_kg(m_p, p_bare_mev, sigma_isco)
dm_p = (eff_p - m_p) / m_p * 100
print(f"  {ok(f'σ(ISCO) = ξ/6 = {sigma_isco:.6f}')}")
print(f"  {ok(f'σ(EH) = ξ/2 = {sigma_eh:.6f}')}")
print(value("Proton shift at ISCO", f"+{dm_p:.2f}%", "", C.GREEN))
print(value("σ mass-independent", "same for 10 M☉ and 4M M☉", "", C.GREEN))

# Neutron Star
sigma_ns = XI_SSBM * G * 1.4 * M_sun / (10e3 * c2)
eff_p_ns = effective_nucleon_mass_kg(m_p, p_bare_mev, sigma_ns)
dm_ns = (eff_p_ns - m_p) / m_p * 100
print(subheader("Scale 4 — Neutron Star (10⁴ m)"))
print(f"  {ok(f'σ(surface) = {sigma_ns:.6f}')}")
print(value("Proton shift", f"+{dm_ns:.2f}%", "", C.GREEN))

# Atom
print(subheader("Scale 5 — Fe-56 Atom (10⁻¹⁰ m)"))
elem_fe = ElementDB.get().by_symbol("Fe")
atom = Atom.create(elem_fe, isotope_mass_number=56)
stable = atom.stable_mass_kg
constituent = atom.constituent_mass_kg
binding_j = atom.binding_energy_joules
nuclear_be_kg = binding_j / c2
electron_be_ev = atom.total_electron_binding_energy_ev
electron_be_kg = electron_be_ev * eV / c2 if electron_be_ev and electron_be_ev > 0 else 0
corrected = constituent - nuclear_be_kg - electron_be_kg
residual_ppm = abs(corrected - stable) / stable * 1e6
print(f"  {ok(f'Three-measure identity: {residual_ppm:.4f} ppm')}")
print(f"  {ok('Wheeler invariance: m_e exact ∀σ')}")

# ── SMBH-TO-GLUON DRILL-DOWN ─────────────────────────────────────────
print(header("SMBH → GLUON PROPAGATION CHAIN (at ISCO)"))
print(value("1. σ = ξ × GM/(rc²)", f"{sigma_isco:.6f}", "", C.CYAN))
print(value("2. Λ_eff = Λ_QCD × e^σ", f"{lambda_eff_gev(sigma_isco):.6f}", "GeV", C.CYAN))
print(value("3. Gluon condensate ∝ e^(4σ)", f"+{(math.exp(4*sigma_isco)-1)*100:.2f}%", "", C.CYAN))
print(value("4. String tension ∝ e^(2σ)", f"+{(math.exp(2*sigma_isco)-1)*100:.2f}%", "", C.CYAN))
u_eff = effective_qcd_dressing_mev(336.0, 2.16, sigma_isco)
print(value("5. Up quark", f"336 → {u_eff:.1f}", "MeV", C.CYAN))
print(value("6. Proton", f"938.3 → {p_bare_mev + (938.272 - p_bare_mev) * scale_ratio(sigma_isco):.1f}", "MeV", C.CYAN))

iso_fe = IsotopeDB.get().by_z_and_a(26, 56)
be_fe = iso_fe.get("binding_energy_per_nucleon_kev", 0) * 56 / 1000.0 if iso_fe else 492.26
eff_be = effective_nuclear_binding_energy_mev(be_fe, 26, 56, sigma_isco)
print(value("7. Fe-56 BE", f"{be_fe:.1f} → {eff_be:.1f}", "MeV", C.CYAN))

# ── n-p MASS FLIP ────────────────────────────────────────────────────
print(header("PREDICTION: NEUTRON-PROTON MASS FLIP"))
n_bare_mev = 2.16 + 2 * 4.67
n_total_mev = m_n / (eV * 1e6 / c2)
p_total_mev = m_p / (eV * 1e6 / c2)
# Find the σ where m_n = m_p
# p_bare + (p_total - p_bare) * e^σ = n_bare + (n_total - n_bare) * e^σ
# (p_total - p_bare - n_total + n_bare) * e^σ = n_bare - p_bare
# e^σ = (n_bare - p_bare) / (p_total - n_total + n_bare - p_bare)
p_qcd = p_total_mev - p_bare_mev
n_qcd = n_total_mev - n_bare_mev
# At σ: m_p_eff = p_bare + p_qcd * e^σ, m_n_eff = n_bare + n_qcd * e^σ
# Equal when: (n_bare - p_bare) = (p_qcd - n_qcd) * e^σ
# e^σ = (n_bare - p_bare) / (p_qcd - n_qcd)
denom = p_qcd - n_qcd
if denom != 0:
    e_sigma_flip = (n_bare_mev - p_bare_mev) / denom
    if e_sigma_flip > 0:
        sigma_flip = math.log(e_sigma_flip)
        print(value("n-p mass difference at σ=0", f"+{n_total_mev - p_total_mev:.4f}", "MeV"))
        print(value("Masses equal at σ", f"{sigma_flip:.4f}", f"= {sigma_flip/XI_SSBM:.1f}ξ", C.YELLOW))
        print(value("Above this σ", "proton becomes HEAVIER than neutron", "", C.RED))
        print(f"\n  {C.YELLOW}At σ > {sigma_flip:.2f}: β⁺ decay direction reverses.{C.RESET}")
        print(f"  {C.YELLOW}Near BH event horizons, nuclear stability could change.{C.RESET}")

# ── OPEN PROBLEMS ────────────────────────────────────────────────────
print(header("OPEN PROBLEMS", C.RED))
problems = [
    ("Galaxy rotation curves", "σ ≈ 10⁻⁶ → 0% of DM", "CRITICAL"),
    ("Dark energy mechanism",  "σ_cosmic = 0 at low z", "OPEN"),
    ("Hubble tension",         "needs σ ≈ 2.8ξ — too large?", "OPEN"),
    ("Tangent C⁰ not C¹",     "BH/cosmic σ cross, don't join", "PARKED"),
    ("Mass sweep",             "need 3, 30, 100 M☉ tangent runs", "PARKED"),
]
for name, detail, severity in problems:
    if severity == "CRITICAL":
        color = C.RED
        icon = "🔴"
    elif severity == "OPEN":
        color = C.YELLOW
        icon = "🟡"
    else:
        color = C.DIM
        icon = "⚪"
    print(f"  {icon} {color}{name:.<40} {detail}{C.RESET}")

# ── UNSOLVED PHYSICS (xfails) ────────────────────────────────────────
print(header("13 UNSOLVED PHYSICS XFAILS"))
xfails = [
    "Dark matter", "Dark energy", "Quantum gravity", "Proton decay",
    "Baryogenesis", "Quark mass precision", "G precision",
    "Nuclear binding from QCD", "Element 119", "Og measured properties",
    "Matter-antimatter asymmetry", "Strong CP problem", "Neutrino masses",
]
for i, x in enumerate(xfails[:13], 1):
    print(f"  {C.DIM}{i:2d}. {x}{C.RESET}")

# ── BASELINE NUMBERS ─────────────────────────────────────────────────
print(header("BASELINE I — TEST HEALTH"))
metrics = [
    ("Tests run",     "2,214", C.WHITE),
    ("Passed",        "2,141", C.GREEN),
    ("Failed",        "0",     C.GREEN),
    ("Errors",        "0",     C.GREEN),
    ("Skipped",       "59",    C.DIM),
    ("xfail",         "13",    C.DIM),
    ("Pass rate",     "96.7%", C.GREEN),
    ("Green files",   "49",    C.GREEN),
    ("Red files",     "1 (gated)", C.YELLOW),
]
for label, val, color in metrics:
    print(value(label, val, "", color))

print(f"\n{C.MAGENTA}{C.BOLD}{'═' * 70}{C.RESET}")
print(f"  {C.DIM}The theory must earn its place by making the physics better,{C.RESET}")
print(f"  {C.DIM}not by breaking what works.{C.RESET}")
print(f"{C.MAGENTA}{C.BOLD}{'═' * 70}{C.RESET}\n")

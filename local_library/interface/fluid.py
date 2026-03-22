"""
Fluid properties for liquids — viscosity, compressibility, surface tension.

This module covers the LIQUID phase. For gas-phase transport see gas.py.
For solid-phase elastic moduli see mechanical.py.

Derivation chains:

  1. Liquid viscosity (Eyring rate theory)
     η = (h_planck × N_A / V_m) × exp(ΔG† / RT)

     FIRST_PRINCIPLES: Eyring (1936), transition state theory.
     A liquid molecule flows by jumping to an adjacent vacancy. The activation
     free energy ΔG† is the energy barrier for that jump.

     Approximation: ΔG† ≈ f_eyring × E_coh for simple liquids.
     f_eyring ≈ 0.408 (fitted to liquid metals at melting; Kincaid & Eyring 1938)

     This works well for metallic melts and simple organic liquids.
     It FAILS for water (hydrogen-bond network dominates) and polymers
     (chain entanglement dominates). For those we use measured values.

     σ-dependence:
       V_m = M / (ρ × N_A) — molecular volume; density shifts with σ
       E_coh shifts with σ (same correction as mechanical.py)
       → η(σ) shifts — heavier nuclei → stiffer bonds → higher activation →
         viscosity of a liquid near a neutron star is higher.

  2. Tait equation of state (liquid compressibility)
     ρ(P) / ρ₀ = 1 / (1 - C × ln(1 + (P - P₀) / B))

     Where C ≈ 0.0894 (universal Tait constant, empirical)
     and B is the Tait pressure parameter (material-specific, MEASURED).

     Simplified for low P: ΔV/V₀ ≈ -ΔP / K
     where K = bulk modulus (Pa). This is the linear (small-strain) limit.

     For the physics stepper we use the linear form: P = K × (ρ/ρ₀ - 1)
     This is exact in the incompressible limit and avoids log instabilities
     in the SPH pressure calculation.

     FIRST_PRINCIPLES at low pressure. MEASURED Tait B at high pressure.

  3. Surface tension (Stefan correlation)
     γ ≈ k_γ × E_coh × n^(2/3) / N_A

     Where n = number density (atoms/m³) and k_γ is a calibration constant.
     The physical basis: γ is an energy per area — the energy cost of
     creating a new surface. Per unit area, you have n^(2/3) surface atoms,
     each contributing E_coh / N_A of broken-bond energy.

     k_γ ≈ 0.17 for simple metals (calibrated to Fe, Cu; Stefan 1886).

     FIRST_PRINCIPLES: broken-bond model, same basis as surface.py.
     σ-dependence: via E_coh shift (same as mechanical.py).

  4. Kinematic viscosity
     ν = η / ρ  (m²/s)
     FIRST_PRINCIPLES: definition.

  5. Reynolds number (dimensionless)
     Re = ρ × v × L / η  (characterizes turbulent vs laminar flow)
     FIRST_PRINCIPLES: Navier-Stokes scaling analysis.

σ-dependence summary:
  EM (σ-invariant): bond force constants, electron structure
  Mass-dependent (σ-shifts): E_coh (via ZPE), V_m, density → η, γ

Origin tags:
  - Eyring viscosity: FIRST_PRINCIPLES (rate theory) + MEASURED (f_eyring)
  - Tait EOS: FIRST_PRINCIPLES (small-strain limit) + MEASURED (B parameter)
  - Surface tension: FIRST_PRINCIPLES (broken-bond) + MEASURED (k_γ)
  - Water viscosity: MEASURED (Kestin et al. 1978, IAPWS standard)
  - Restitution: MEASURED (material-specific, phonon spectrum required)
"""

import math
from .surface import MATERIALS
from .mechanical import bulk_modulus, _number_density
from ..scale import scale_ratio
from ..constants import PROTON_QCD_FRACTION

# ── Physical constants ──────────────────────────────────────────────────────
_H_PLANCK   = 6.62607015e-34    # J·s (exact, 2019 SI)
_K_B        = 1.380649e-23      # J/K (exact)
_R_GAS      = 8.314462618       # J/(mol·K)
_N_AVOGADRO = 6.02214076e23     # /mol (exact)
_AMU_KG     = 1.66053906660e-27 # kg
_EV_TO_J    = 1.602176634e-19   # exact

# ── Eyring activation fraction ──────────────────────────────────────────────
# ΔG† ≈ _F_EYRING × E_coh
# Kincaid & Eyring (1938), calibrated to simple liquid metals near melting.
# Honest: ±30% for metallic melts. Larger errors for polar liquids.
_F_EYRING = 0.408   # MEASURED, dimensionless


# ── Known liquid database ───────────────────────────────────────────────────
# For substances where Eyring theory is inadequate (water, glycerol, polymers),
# we store measured viscosity at reference temperature and an Arrhenius
# activation energy for temperature extrapolation.
#
# Sources:
#   Water: Kestin, Sokolov & Wakeham (1978) J. Phys. Chem. Ref. Data
#           IAPWS Release on Viscosity (2008)
#   Ethanol: CRC Handbook of Chemistry and Physics, 103rd ed.
#   Glycerol: Segur & Oberstar (1951) Ind. Eng. Chem.
#   Mercury: Filled, Bower & Sears (1954) J. Chem. Phys.
#   Seawater: Sharqawy, Lienhard & Zubair (2010) Desalination and Water Treat.

KNOWN_LIQUIDS = {
    'water': {
        'name': 'Liquid Water (H₂O)',
        'density_kg_m3': 998.2,          # at 20°C, 1 atm; MEASURED
        'viscosity_pa_s': 1.002e-3,       # at 20°C; IAPWS 2008
        'reference_temp_K': 293.15,
        'activation_energy_j_mol': 15000, # Arrhenius E_a; MEASURED (Eyring fit)
        'bulk_modulus_pa': 2.20e9,        # at 20°C; Kell (1975) J. Chem. Eng.
        'surface_tension_n_m': 0.0728,   # at 20°C; IAPWS 1994
        'mean_Z': 3.33,                  # H₂O: (2×1 + 8)/3 weighted
        'mean_A': 6.0,                   # (2×1 + 16)/3
        'composition': 'H₂O liquid',
    },
    'seawater': {
        'name': 'Seawater (3.5% NaCl)',
        'density_kg_m3': 1025.0,
        'viscosity_pa_s': 1.08e-3,        # at 20°C; Sharqawy et al. 2010
        'reference_temp_K': 293.15,
        'activation_energy_j_mol': 16000,
        'bulk_modulus_pa': 2.34e9,
        'surface_tension_n_m': 0.0735,
        'mean_Z': 4.0,
        'mean_A': 8.0,
        'composition': 'H₂O + ~3.5% NaCl',
    },
    'ethanol': {
        'name': 'Ethanol (C₂H₅OH)',
        'density_kg_m3': 789.0,
        'viscosity_pa_s': 1.074e-3,       # at 25°C; CRC Handbook
        'reference_temp_K': 298.15,
        'activation_energy_j_mol': 12500,
        'bulk_modulus_pa': 8.9e8,
        'surface_tension_n_m': 0.0221,   # at 25°C; CRC Handbook
        'mean_Z': 4.89,
        'mean_A': 9.56,
        'composition': 'C₂H₅OH',
    },
    'glycerol': {
        'name': 'Glycerol (C₃H₈O₃)',
        'density_kg_m3': 1261.0,
        'viscosity_pa_s': 0.934,          # at 25°C; Segur & Oberstar 1951
        'reference_temp_K': 298.15,
        'activation_energy_j_mol': 55000, # very high E_a — H-bond network
        'bulk_modulus_pa': 4.35e9,
        'surface_tension_n_m': 0.0634,
        'mean_Z': 5.22,
        'mean_A': 10.22,
        'composition': 'C₃H₈O₃',
    },
    'mercury': {
        'name': 'Liquid Mercury (Hg)',
        'density_kg_m3': 13534.0,
        'viscosity_pa_s': 1.526e-3,       # at 25°C; Filled et al. 1954
        'reference_temp_K': 298.15,
        'activation_energy_j_mol': 2790,  # Low E_a — metallic bonding
        'bulk_modulus_pa': 28.5e9,
        'surface_tension_n_m': 0.4865,   # at 25°C; high (metallic bonding)
        'mean_Z': 80,
        'mean_A': 200.59,
        'composition': 'Hg liquid',
    },
}


# ── Eyring liquid viscosity (metallic melts, simple liquids) ────────────────

def _cohesive_energy_j(material_key, sigma=0.0):
    """Cohesive energy per atom in Joules, with σ correction.

    Same as mechanical.py — centralised here to avoid re-import chain.
    """
    mat = MATERIALS[material_key]
    e_coh_ev = mat['cohesive_energy_ev']
    if sigma == 0.0:
        return e_coh_ev * _EV_TO_J
    f_qcd = PROTON_QCD_FRACTION
    mass_ratio = (1.0 - f_qcd) + f_qcd * scale_ratio(sigma)
    f_zpe = 0.01
    zpe_correction = f_zpe * e_coh_ev * (1.0 - 1.0 / math.sqrt(mass_ratio))
    return (e_coh_ev + zpe_correction) * _EV_TO_J


def eyring_viscosity(material_key, T=1000.0, sigma=0.0):
    """Dynamic viscosity of a metallic melt via Eyring rate theory (Pa·s).

    η = (h × N_A / V_m) × exp(ΔG† / RT)
    ΔG† = _F_EYRING × E_coh (activation energy for flow jump)
    V_m  = M / (ρ × N_A) (molar volume at given σ)

    Args:
        material_key: key into MATERIALS (e.g. 'iron', 'copper')
        T: temperature in K (should be above melting point for validity)
        sigma: σ field value

    Returns:
        Dynamic viscosity in Pa·s.

    Accuracy: ±30% for simple metallic melts near T_melt.
    """
    mat = MATERIALS[material_key]
    A_kg = mat['A'] * _AMU_KG

    # σ-corrected density (via scale_ratio on QCD fraction of mass)
    rho_0 = mat['density_kg_m3']
    if sigma != 0.0:
        mass_ratio = ((1.0 - PROTON_QCD_FRACTION) +
                      PROTON_QCD_FRACTION * scale_ratio(sigma))
        rho = rho_0 * mass_ratio
    else:
        rho = rho_0

    # Molar volume in m³/mol
    M_kg_mol = mat['A'] * _AMU_KG * _N_AVOGADRO
    V_m = M_kg_mol / rho                       # m³/mol

    # Activation energy
    e_coh_j = _cohesive_energy_j(material_key, sigma)
    delta_G = _F_EYRING * e_coh_j * _N_AVOGADRO  # J/mol

    # Eyring pre-factor
    prefactor = _H_PLANCK * _N_AVOGADRO / V_m   # Pa·s

    return prefactor * math.exp(delta_G / (_R_GAS * T))


# ── Known liquid viscosity (Arrhenius extrapolation) ────────────────────────

def liquid_viscosity(liquid_key, T=None, sigma=0.0):
    """Dynamic viscosity of a known liquid (Pa·s).

    Uses measured value at reference temperature with Arrhenius extrapolation:
      η(T) = η_ref × exp(E_a/R × (1/T - 1/T_ref))

    For σ ≠ 0: viscosity increases because E_coh increases (heavier nuclei →
    stiffer intermolecular bonds → higher activation barrier). We apply the
    same QCD mass scaling to E_a as to E_coh.

    Args:
        liquid_key: key into KNOWN_LIQUIDS (e.g. 'water', 'ethanol')
        T: temperature in K. None → use reference temperature.
        sigma: σ field value

    Returns:
        Dynamic viscosity in Pa·s.
    """
    liq = KNOWN_LIQUIDS[liquid_key]
    eta_ref = liq['viscosity_pa_s']
    T_ref   = liq['reference_temp_K']
    E_a     = liq['activation_energy_j_mol']   # J/mol at σ=0

    if T is None:
        T = T_ref

    # σ correction to activation energy — same QCD mass scaling
    if sigma != 0.0:
        mass_ratio = ((1.0 - PROTON_QCD_FRACTION) +
                      PROTON_QCD_FRACTION * scale_ratio(sigma))
        # ZPE correction: heavier atoms have lower ZPE → deeper well → higher E_a
        f_zpe = 0.01
        E_a = E_a * (1.0 + f_zpe * (1.0 - 1.0 / math.sqrt(mass_ratio)))

    if T == T_ref and sigma == 0.0:
        return eta_ref

    # Arrhenius
    return eta_ref * math.exp((E_a / _R_GAS) * (1.0 / T - 1.0 / T_ref))


# ── Kinematic viscosity ─────────────────────────────────────────────────────

def kinematic_viscosity(liquid_key, T=None, sigma=0.0):
    """Kinematic viscosity ν = η/ρ (m²/s).

    FIRST_PRINCIPLES: definition. No approximation beyond those in
    liquid_viscosity() and density.
    """
    liq = KNOWN_LIQUIDS[liquid_key]
    eta = liquid_viscosity(liquid_key, T=T, sigma=sigma)
    rho = liq['density_kg_m3']
    if sigma != 0.0:
        mass_ratio = ((1.0 - PROTON_QCD_FRACTION) +
                      PROTON_QCD_FRACTION * scale_ratio(sigma))
        rho *= mass_ratio
    return eta / rho


# ── Surface tension from Stefan correlation ─────────────────────────────────
# k_γ calibrated to liquid metals (Fe at 1550°C: γ≈1.87 N/m; Cu at 1100°C: γ≈1.30 N/m)
_K_STEFAN = 0.17   # dimensionless, MEASURED (Stefan 1886)


def surface_tension_metal(material_key, sigma=0.0):
    """Surface tension of a metallic melt (N/m) via Stefan correlation.

    γ = k_γ × E_coh × n^(2/3) / N_A

    Where n = number density (atoms/m³) at given σ.

    FIRST_PRINCIPLES: broken-bond model — γ is the energy cost per unit area
    of creating a new surface. n^(2/3) atoms/m² × E_coh/N_A J/atom.

    Accuracy: ±25% for simple metals. Not valid for polar liquids.

    Args:
        material_key: key into MATERIALS
        sigma: σ field value

    Returns:
        Surface tension in N/m.
    """
    e_coh_j = _cohesive_energy_j(material_key, sigma)
    n = _number_density(material_key)
    if sigma != 0.0:
        mass_ratio = ((1.0 - PROTON_QCD_FRACTION) +
                      PROTON_QCD_FRACTION * scale_ratio(sigma))
        n *= mass_ratio   # denser → more atoms/m³ → higher γ

    return _K_STEFAN * e_coh_j * (n ** (2.0 / 3.0)) / _N_AVOGADRO


def surface_tension(liquid_key=None, material_key=None, sigma=0.0):
    """Surface tension dispatcher.

    If liquid_key given: return measured value from KNOWN_LIQUIDS.
    If material_key given: compute via Stefan correlation.
    """
    if liquid_key is not None:
        liq = KNOWN_LIQUIDS[liquid_key]
        return liq['surface_tension_n_m']
    if material_key is not None:
        return surface_tension_metal(material_key, sigma)
    raise ValueError("Provide liquid_key (known liquid) or material_key (metal).")


# ── Reynolds number ─────────────────────────────────────────────────────────

def reynolds_number(rho, v, L, eta):
    """Dimensionless Reynolds number Re = ρvL/η.

    FIRST_PRINCIPLES: ratio of inertial to viscous forces in N-S equation.

    Re < ~2300  → laminar
    Re > ~4000  → turbulent
    2300–4000   → transitional

    Args:
        rho: density kg/m³
        v:   characteristic velocity m/s
        L:   characteristic length m
        eta: dynamic viscosity Pa·s

    Returns:
        Dimensionless Reynolds number.
    """
    return rho * v * L / eta


# ── Liquid property summary ─────────────────────────────────────────────────

def liquid_properties(liquid_key, T=None, sigma=0.0):
    """Return a dict of all relevant liquid properties at (T, σ).

    Useful for diagnostics and physics_materials.py lookups.
    """
    liq = KNOWN_LIQUIDS[liquid_key]
    if T is None:
        T = liq['reference_temp_K']
    eta   = liquid_viscosity(liquid_key, T=T, sigma=sigma)
    nu    = kinematic_viscosity(liquid_key, T=T, sigma=sigma)
    rho   = liq['density_kg_m3']
    K     = liq['bulk_modulus_pa']
    gamma = liq['surface_tension_n_m']

    return {
        'liquid_key':        liquid_key,
        'T_K':               T,
        'sigma':             sigma,
        'density_kg_m3':     rho,
        'viscosity_pa_s':    eta,
        'kinematic_nu_m2_s': nu,
        'bulk_modulus_pa':   K,
        'surface_tension_n_m': gamma,
    }

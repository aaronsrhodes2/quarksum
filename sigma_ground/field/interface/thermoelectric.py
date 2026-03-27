"""
Thermoelectric transport from atomic-scale properties.

Derivation chain:
  σ → nuclear mass → electron density → Fermi energy → Seebeck coefficient
  → thermoelectric voltage → current → power

The complete hot-plate → TEG → ice-cube stack:

  1. Free electron density n_e
     n_e = Z_val × n_atoms
     FIRST_PRINCIPLES: each atom contributes Z_val free electrons.
     Z_val is MEASURED (periodic table, valence shell).

  2. Fermi energy E_F
     E_F = (ℏ²/2m_e) × (3π²n_e)^(2/3)
     FIRST_PRINCIPLES: Pauli exclusion fills electron states up to E_F.
     This is the Sommerfeld free-electron model — exact for an ideal
     Fermi gas, good approximation for simple metals (Cu, Al, Au).

  3. Seebeck coefficient S (thermopower)
     S = (π²/3) × (k_B/e) × (k_B T / E_F)
     FIRST_PRINCIPLES: Mott formula from Boltzmann transport theory.
     The physical picture: hot electrons carry more energy than cold ones.
     The entropy per carrier ≈ k_B × (k_BT/E_F), and each carries charge e.

     APPROXIMATION: free-electron Mott formula. Works well for simple
     metals (Cu: predicted ~1.1 μV/K vs measured 1.83 μV/K).
     Transition metals (Fe, Ni) have d-band contributions that make S
     much larger. We use MEASURED values for validation.

  4. Thermoelectric voltage
     V = (S_p - S_n) × (T_hot - T_cold)
     FIRST_PRINCIPLES: Seebeck effect. Two dissimilar conductors in
     a temperature gradient develop a voltage proportional to ΔT.
     This IS the thermocouple principle.

  5. Electrical conductivity
     σ_elec = 1 / ρ_elec
     ρ_elec is MEASURED (from thermal.py).

  6. Figure of merit ZT
     ZT = S² × σ_elec × T / κ
     FIRST_PRINCIPLES: dimensionless ratio that determines maximum
     thermoelectric efficiency. Good thermoelectrics: ZT > 1.
     Metals: ZT ~ 0.01 (Wiedemann-Franz kills them — good electrical
     conductors are also good thermal conductors).

  7. Thermoelectric efficiency
     η = η_Carnot × [√(1+ZT) - 1] / [√(1+ZT) + T_c/T_h]
     FIRST_PRINCIPLES: derived from entropy production in a
     thermoelectric element with Thomson heat.

  8. Power output
     P_max = V² / (4 × R_internal)
     FIRST_PRINCIPLES: maximum power transfer theorem (impedance matching).
     R_internal = ρ × L / A for each thermoelectric leg.

σ-dependence:
  σ → mass → n_atoms → n_e → E_F → S → V → P
  Also: σ → κ (through thermal module) → ZT → η
  The full chain propagates from □σ = −ξR.

  Electronic properties (ρ_elec, Z_val) are EM → σ-INVARIANT.
  But n_atoms shifts with nuclear mass → E_F shifts.
  And κ_phonon shifts with mass → ZT shifts.

Origin tags:
  - Fermi energy: FIRST_PRINCIPLES (Sommerfeld model)
  - Seebeck coefficient: FIRST_PRINCIPLES (Mott formula) +
    APPROXIMATION (free-electron model, misses d-band)
  - Voltage/current/power: FIRST_PRINCIPLES (Seebeck effect + Ohm's law)
  - Figure of merit: FIRST_PRINCIPLES (dimensionless combination)
  - Efficiency: FIRST_PRINCIPLES (thermodynamic optimization)
  - Valence electrons: MEASURED (periodic table)
  - Resistivity: MEASURED (from thermal module)
"""

import math
from .surface import MATERIALS
from .mechanical import _number_density
from .thermal import (
    thermal_conductivity,
    _RESISTIVITY_OHM_M,
    _K_BOLTZMANN,
    _HBAR,
    _ELEMENTARY_CHARGE,
    electronic_thermal_conductivity,
)

# ── Constants ─────────────────────────────────────────────────────
_ELECTRON_MASS = 9.1093837015e-31  # kg (exact, 2019 SI)

# ── Valence Electron Count (MEASURED) ────────────────────────────
# Number of FREE electrons per atom that participate in metallic
# conduction. This is the effective valence for the Sommerfeld model.
#
# Source: Ashcroft & Mermin, "Solid State Physics", Table 1.1
# These are the conventional free-electron counts:
#   - Noble metals (Cu, Au): 1 (s-electron)
#   - Divalent metals (Fe, Ni): ~2 (but d-band complicates this)
#   - Trivalent (Al): 3
#   - Transition metals: use the sp-band contribution
#
# For transition metals, the d-electrons are localized and don't
# contribute to free-electron transport in the simple model.
# We use the sp-electron count. This is why the Mott formula
# underestimates S for Fe and Ni — the d-band density of states
# is the real driver there.

_VALENCE_ELECTRONS = {
    'copper':    1,    # [Ar] 3d¹⁰ 4s¹ — one free s-electron
    'aluminum':  3,    # [Ne] 3s² 3p¹ — three sp-electrons
    'gold':      1,    # [Xe] 4f¹⁴ 5d¹⁰ 6s¹ — one free s-electron
    'iron':      2,    # [Ar] 3d⁶ 4s² — two s-electrons (d-band localized)
    'nickel':    2,    # [Ar] 3d⁸ 4s² — two s-electrons
    'tungsten':  2,    # [Xe] 4f¹⁴ 5d⁴ 6s² — two s-electrons
    'titanium':  2,    # [Ar] 3d² 4s² — two s-electrons
    'silicon':   0,    # Semiconductor — no free electrons at 0K
}

# ── Measured Seebeck Coefficients (for validation) ───────────────
# Absolute Seebeck coefficient at 300K, in μV/K.
# Source: CRC Handbook, Ashcroft & Mermin.
#
# Sign convention: positive means holes dominate (current flows
# from hot to cold in the material). Negative means electrons.
# For our purposes, we use absolute values.
#
# Note: these are NOT used in derivations — only for validation.
# Our derivation uses the Mott formula from E_F.

_SEEBECK_MEASURED_UV_K = {
    'copper':    1.83,    # μV/K (positive)
    'aluminum':  -1.66,   # μV/K (negative — electron-like)
    'gold':      1.94,    # μV/K
    'iron':      15.0,    # μV/K (large — d-band effect!)
    'nickel':    -19.5,   # μV/K (large negative — d-band)
    'tungsten':  0.9,     # μV/K
    'titanium':  9.1,     # μV/K
}


# ── Free Electron Density ────────────────────────────────────────

def free_electron_density(material_key):
    """Free electron density n_e (electrons/m³).

    n_e = Z_val × n_atoms

    FIRST_PRINCIPLES: each atom contributes Z_val conduction electrons.
    Z_val is MEASURED from the periodic table (valence shell occupancy).

    For semiconductors (Si), returns 0 — no free electrons at 0K.
    At finite T, thermal excitation creates carriers, but that's a
    semiconductor physics module we haven't built yet.

    Args:
        material_key: key into MATERIALS dict

    Returns:
        Free electron density in electrons/m³.
    """
    z_val = _VALENCE_ELECTRONS.get(material_key, 0)
    if z_val == 0:
        return 0.0
    n_atoms = _number_density(material_key)
    return z_val * n_atoms


# ── Fermi Energy ─────────────────────────────────────────────────

def fermi_energy(material_key):
    """Fermi energy E_F (Joules) from free electron density.

    E_F = (ℏ²/2m_e) × (3π²n_e)^(2/3)

    FIRST_PRINCIPLES: Sommerfeld free-electron model. Electrons fill
    states from the bottom up (Pauli exclusion). The highest occupied
    state at T=0 has energy E_F. This determines ALL electronic
    transport properties.

    For copper: n_e = 8.5×10²⁸ /m³ → E_F ≈ 7.0 eV (measured: 7.0 eV)
    The free-electron model is remarkably accurate for noble metals.

    σ-dependence: n_atoms shifts with nuclear mass through density.
    But density = mass/volume, and if mass increases the volume
    doesn't change (lattice spacing is set by EM), so n_atoms is
    actually σ-INVARIANT. E_F is therefore σ-invariant too.

    Args:
        material_key: key into MATERIALS dict

    Returns:
        Fermi energy in Joules. Returns 0 for semiconductors.
    """
    n_e = free_electron_density(material_key)
    if n_e <= 0:
        return 0.0

    # E_F = (ℏ²/2m_e) × (3π²n_e)^(2/3)
    prefactor = _HBAR**2 / (2.0 * _ELECTRON_MASS)
    kf_cubed = 3.0 * math.pi**2 * n_e
    E_F = prefactor * kf_cubed**(2.0/3.0)
    return E_F


def fermi_energy_ev(material_key):
    """Fermi energy in electron-volts (convenience)."""
    return fermi_energy(material_key) / _ELEMENTARY_CHARGE


# ── Seebeck Coefficient ──────────────────────────────────────────

def seebeck_coefficient(material_key, T=300.0):
    """Seebeck coefficient S (V/K) from the Mott formula.

    S = (π²/3) × (k_B/e) × (k_B T / E_F)

    FIRST_PRINCIPLES: Boltzmann transport equation in the relaxation
    time approximation. The Mott formula relates thermopower to the
    energy derivative of conductivity at the Fermi level.

    For free electrons, d(ln σ)/d(ln E) = 3/2, giving:
      S = (π²/2) × (k_B²T) / (e × E_F)

    Wait — the standard Mott result for free electrons is:
      S = (π²/3) × (k_B²T) / (e × E_F) × (3/2)
      S = (π²/2) × (k_B²T) / (e × E_F)

    This is the standard free-electron Seebeck coefficient.

    APPROXIMATION: misses d-band density of states effects in
    transition metals. For Cu, Al: within factor of 2.
    For Fe, Ni: underestimates by 10×. We note this honestly.

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin

    Returns:
        Seebeck coefficient in V/K. Always positive (absolute value).
        Returns 0 for semiconductors.
    """
    if T <= 0:
        return 0.0

    E_F = fermi_energy(material_key)
    if E_F <= 0:
        return 0.0

    # Mott formula: S = (π²/2) × (k_B²T) / (e × E_F)
    S = (math.pi**2 / 2.0) * _K_BOLTZMANN**2 * T / (_ELEMENTARY_CHARGE * E_F)

    return abs(S)


def seebeck_coefficient_uv_k(material_key, T=300.0):
    """Seebeck coefficient in μV/K (convenience, for comparison with tables)."""
    return seebeck_coefficient(material_key, T) * 1e6


# ── Electrical Conductivity ──────────────────────────────────────

def electrical_conductivity(material_key):
    """Electrical conductivity σ_elec (S/m = 1/(Ω·m)).

    σ = 1 / ρ_elec

    ρ_elec is MEASURED (from thermal module).

    Args:
        material_key: key into MATERIALS dict

    Returns:
        Electrical conductivity in S/m (Siemens per meter).
    """
    rho = _RESISTIVITY_OHM_M.get(material_key)
    if rho is None or rho <= 0:
        return 0.0
    return 1.0 / rho


def electrical_resistivity(material_key):
    """Electrical resistivity ρ (Ω·m). MEASURED."""
    return _RESISTIVITY_OHM_M.get(material_key, float('inf'))


# ── Figure of Merit ZT ───────────────────────────────────────────

def figure_of_merit_ZT(material_key, T=300.0, sigma=0.0):
    """Dimensionless thermoelectric figure of merit ZT.

    ZT = S² × σ_elec × T / κ

    FIRST_PRINCIPLES: this dimensionless combination determines the
    maximum efficiency of a thermoelectric device. It appears naturally
    when optimizing the power output vs heat loss trade-off.

    Good thermoelectrics: ZT > 1 (Bi₂Te₃ ≈ 1.0, PbTe ≈ 1.5)
    Metals: ZT ~ 0.01 (the Wiedemann-Franz law kills them)

    Why metals are bad thermoelectrics:
      ZT = S² × σ × T / κ
      But κ ≈ L₀ × σ × T (Wiedemann-Franz)
      So ZT ≈ S² / L₀ ≈ (π²k_B²T/2eE_F)² / (π²k_B²/3e²)
           ≈ (3/4) × (π²k_BT / E_F)² × (1/π²)
           ≈ (3/4) × (k_BT/E_F)²

    For copper at 300K: k_BT/E_F ≈ 0.026/7.0 ≈ 0.0037
    ZT ≈ 0.75 × (0.0037)² ≈ 1×10⁻⁵

    That's why real TEGs use semiconductors, not metals.
    But the physics still works — just less efficient.

    σ-dependence: S is σ-invariant (E_F is EM), κ_phonon shifts.

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        ZT (dimensionless).
    """
    S = seebeck_coefficient(material_key, T)
    sigma_elec = electrical_conductivity(material_key)
    kappa = thermal_conductivity(material_key, T, sigma)

    if kappa <= 0 or sigma_elec <= 0:
        return 0.0

    return S**2 * sigma_elec * T / kappa


# ── Thermocouple / TEG Calculations ─────────────────────────────

def thermocouple_voltage(mat_p, mat_n, T_hot, T_cold, T_ref=300.0):
    """Open-circuit voltage from a thermocouple (Seebeck effect).

    V = |S_p(T_avg) - S_n(T_avg)| × (T_hot - T_cold)

    FIRST_PRINCIPLES: two dissimilar conductors in a temperature
    gradient develop a voltage. This is the principle behind every
    thermocouple and every thermoelectric generator.

    The voltage arises because hot electrons in each material have
    different average energies (different Fermi levels), so they
    diffuse at different rates → charge separation → voltage.

    We use the average temperature for evaluating S, which is the
    linear approximation. For large ΔT, we'd need to integrate
    S(T) dT, but this captures the physics.

    Args:
        mat_p: positive leg material key (higher S)
        mat_n: negative leg material key (lower S)
        T_hot: hot junction temperature in K
        T_cold: cold junction temperature in K
        T_ref: reference temperature for S evaluation (default: average)

    Returns:
        Open-circuit voltage in Volts.
    """
    T_avg = (T_hot + T_cold) / 2.0
    S_p = seebeck_coefficient(mat_p, T_avg)
    S_n = seebeck_coefficient(mat_n, T_avg)

    delta_T = T_hot - T_cold
    return abs(S_p - S_n) * delta_T


def leg_resistance(material_key, length_m, cross_section_m2):
    """Electrical resistance of a thermoelectric leg (Ω).

    R = ρ × L / A

    FIRST_PRINCIPLES: Ohm's law in differential form.

    Args:
        material_key: material key
        length_m: leg length in meters
        cross_section_m2: cross-sectional area in m²

    Returns:
        Resistance in Ohms.
    """
    rho = electrical_resistivity(material_key)
    if rho == float('inf'):
        return float('inf')
    return rho * length_m / cross_section_m2


def thermoelectric_power_max(mat_p, mat_n, T_hot, T_cold,
                              leg_length_m=0.01, leg_area_m2=1e-4):
    """Maximum electrical power output from a thermoelectric generator.

    P_max = V_oc² / (4 × R_internal)

    FIRST_PRINCIPLES: maximum power transfer theorem. Output is
    maximized when load resistance equals internal resistance.
    This is a fundamental result from circuit theory.

    The TEG has two legs (p-type and n-type) in series electrically
    but parallel thermally. Internal resistance is the sum of both legs.

    Args:
        mat_p: positive leg material key
        mat_n: negative leg material key
        T_hot: hot side temperature in K
        T_cold: cold side temperature in K
        leg_length_m: length of each leg in meters
        leg_area_m2: cross-sectional area of each leg in m²

    Returns:
        Dict with voltage, current, power, resistance, efficiency.
    """
    V_oc = thermocouple_voltage(mat_p, mat_n, T_hot, T_cold)

    R_p = leg_resistance(mat_p, leg_length_m, leg_area_m2)
    R_n = leg_resistance(mat_n, leg_length_m, leg_area_m2)
    R_internal = R_p + R_n

    if R_internal <= 0 or R_internal == float('inf'):
        return {
            'voltage_oc_V': V_oc,
            'voltage_load_V': 0.0,
            'current_A': 0.0,
            'power_W': 0.0,
            'resistance_internal_ohm': R_internal,
            'resistance_load_ohm': R_internal,
        }

    # At maximum power: R_load = R_internal
    R_load = R_internal
    I = V_oc / (R_internal + R_load)  # = V_oc / (2R)
    V_load = I * R_load               # = V_oc / 2
    P = I * V_load                     # = V_oc² / (4R)

    return {
        'voltage_oc_V': V_oc,
        'voltage_load_V': V_load,
        'current_A': I,
        'power_W': P,
        'resistance_internal_ohm': R_internal,
        'resistance_load_ohm': R_load,
    }


# ── Efficiency ───────────────────────────────────────────────────

def carnot_efficiency(T_hot, T_cold):
    """Carnot efficiency — thermodynamic upper bound.

    η_c = 1 - T_cold / T_hot

    FIRST_PRINCIPLES: second law of thermodynamics. No heat engine
    can exceed this efficiency operating between T_hot and T_cold.

    Args:
        T_hot: hot side temperature in K
        T_cold: cold side temperature in K

    Returns:
        Carnot efficiency (dimensionless, 0 to 1).
    """
    if T_hot <= 0 or T_hot <= T_cold:
        return 0.0
    return 1.0 - T_cold / T_hot


def thermoelectric_efficiency(material_key, T_hot, T_cold, sigma=0.0):
    """Maximum thermoelectric conversion efficiency.

    η = η_Carnot × [√(1+ZT) - 1] / [√(1+ZT) + T_c/T_h]

    FIRST_PRINCIPLES: derived by optimizing current through a
    thermoelectric element subject to Fourier heat conduction,
    Joule heating, and Thomson/Peltier heat transport.

    This is the Ioffe formula (1957). The derivation assumes
    constant material properties over the temperature range
    (APPROXIMATION for large ΔT).

    Args:
        material_key: key into MATERIALS dict
        T_hot: hot side temperature in K
        T_cold: cold side temperature in K
        sigma: σ-field value

    Returns:
        Maximum efficiency (dimensionless, 0 to 1).
    """
    eta_c = carnot_efficiency(T_hot, T_cold)
    if eta_c <= 0:
        return 0.0

    T_avg = (T_hot + T_cold) / 2.0
    ZT = figure_of_merit_ZT(material_key, T_avg, sigma)

    sqrt_1_ZT = math.sqrt(1.0 + ZT)
    numerator = sqrt_1_ZT - 1.0
    denominator = sqrt_1_ZT + T_cold / T_hot

    if denominator <= 0:
        return 0.0

    return eta_c * numerator / denominator


# ── Heat Flow ────────────────────────────────────────────────────

def heat_flow_through_leg(material_key, T_hot, T_cold,
                           length_m=0.01, area_m2=1e-4, sigma=0.0):
    """Heat flow through a thermoelectric leg (Watts).

    Q = κ × A × (T_hot - T_cold) / L

    FIRST_PRINCIPLES: Fourier's law of heat conduction.

    This is the heat that flows from hot to cold through the TEG
    material. The TEG converts a fraction of this to electricity;
    the rest is waste heat.

    Args:
        material_key: material key
        T_hot, T_cold: temperatures in K
        length_m: leg length
        area_m2: cross-sectional area
        sigma: σ-field value

    Returns:
        Heat flow in Watts.
    """
    T_avg = (T_hot + T_cold) / 2.0
    kappa = thermal_conductivity(material_key, T_avg, sigma)
    return kappa * area_m2 * (T_hot - T_cold) / length_m


# ── Full TEG System Simulation ───────────────────────────────────

def simulate_teg_system(mat_hot_plate, mat_p, mat_n,
                         T_hot, T_cold=273.15,
                         leg_length_m=0.01, leg_area_m2=1e-4,
                         n_couples=1, sigma=0.0):
    """Simulate a complete thermoelectric generator system.

    Hot plate (T_hot) → TEG (n thermocouples) → Cold side (T_cold)

    This is the full stack: heat flow, voltage, current, power,
    efficiency — all derived from atomic properties.

    The derivation chain from σ:
      σ → mass → n_atoms → E_F → S → V
      σ → mass → K, ρ → v_s → κ → heat flow → efficiency
      σ → ρ_elec (MEASURED, EM) → R → current → power

    Args:
        mat_hot_plate: material of the hot plate (for thermal properties)
        mat_p: positive thermoelectric leg material
        mat_n: negative thermoelectric leg material
        T_hot: hot plate temperature in K
        T_cold: cold side temperature in K (default: ice, 273.15K)
        leg_length_m: length of each TEG leg
        leg_area_m2: cross-section of each TEG leg
        n_couples: number of thermocouple pairs
        sigma: σ-field value

    Returns:
        Dict with complete system characterization.
    """
    # Seebeck coefficients at average temperature
    T_avg = (T_hot + T_cold) / 2.0
    S_p = seebeck_coefficient(mat_p, T_avg)
    S_n = seebeck_coefficient(mat_n, T_avg)
    delta_S = abs(S_p - S_n)

    # Single couple voltage
    delta_T = T_hot - T_cold
    V_couple = delta_S * delta_T
    V_total = V_couple * n_couples

    # Resistance per couple
    R_p = leg_resistance(mat_p, leg_length_m, leg_area_m2)
    R_n = leg_resistance(mat_n, leg_length_m, leg_area_m2)
    R_couple = R_p + R_n
    R_total = R_couple * n_couples

    # Maximum power (matched load)
    if R_total > 0 and R_total != float('inf'):
        I_max_power = V_total / (2.0 * R_total)
        P_max = V_total**2 / (4.0 * R_total)
        V_load = V_total / 2.0
    else:
        I_max_power = 0.0
        P_max = 0.0
        V_load = 0.0

    # Heat flow through TEG (both legs, all couples)
    Q_p = heat_flow_through_leg(mat_p, T_hot, T_cold,
                                 leg_length_m, leg_area_m2, sigma)
    Q_n = heat_flow_through_leg(mat_n, T_hot, T_cold,
                                 leg_length_m, leg_area_m2, sigma)
    Q_total = (Q_p + Q_n) * n_couples

    # Actual efficiency
    eta = P_max / Q_total if Q_total > 0 else 0.0
    eta_carnot = carnot_efficiency(T_hot, T_cold)

    # Figure of merit for each leg
    ZT_p = figure_of_merit_ZT(mat_p, T_avg, sigma)
    ZT_n = figure_of_merit_ZT(mat_n, T_avg, sigma)

    # Fermi energies
    E_F_p = fermi_energy_ev(mat_p)
    E_F_n = fermi_energy_ev(mat_n)

    return {
        # Temperature
        'T_hot_K': T_hot,
        'T_cold_K': T_cold,
        'delta_T_K': delta_T,

        # Seebeck
        'seebeck_p_uV_K': S_p * 1e6,
        'seebeck_n_uV_K': S_n * 1e6,
        'delta_seebeck_uV_K': delta_S * 1e6,

        # Fermi energy
        'fermi_energy_p_eV': E_F_p,
        'fermi_energy_n_eV': E_F_n,

        # Electrical
        'voltage_oc_V': V_total,
        'voltage_load_V': V_load,
        'current_A': I_max_power,
        'power_max_W': P_max,
        'resistance_internal_ohm': R_total,

        # Thermal
        'heat_flow_W': Q_total,
        'kappa_p_W_mK': thermal_conductivity(mat_p, T_avg, sigma),
        'kappa_n_W_mK': thermal_conductivity(mat_n, T_avg, sigma),

        # Efficiency
        'efficiency': eta,
        'carnot_efficiency': eta_carnot,
        'efficiency_fraction_of_carnot': eta / eta_carnot if eta_carnot > 0 else 0,

        # Figure of merit
        'ZT_p': ZT_p,
        'ZT_n': ZT_n,

        # System
        'n_couples': n_couples,
        'leg_length_m': leg_length_m,
        'leg_area_m2': leg_area_m2,
        'mat_p': mat_p,
        'mat_n': mat_n,

        # Origin
        'origin': (
            "Fermi energy: FIRST_PRINCIPLES (Sommerfeld free-electron model). "
            "Seebeck coefficient: FIRST_PRINCIPLES (Mott formula) + "
            "APPROXIMATION (free-electron, misses d-band for transition metals). "
            "Voltage: FIRST_PRINCIPLES (Seebeck effect, V = ΔS × ΔT). "
            "Power: FIRST_PRINCIPLES (max power transfer, P = V²/4R). "
            "Heat flow: FIRST_PRINCIPLES (Fourier's law). "
            "Efficiency: FIRST_PRINCIPLES (Ioffe formula, 1957). "
            "Resistivity: MEASURED. Valence electrons: MEASURED."
        ),
    }


# ── Nagatha Export ────────────────────────────────────────────────

def material_thermoelectric_properties(material_key, T=300.0, sigma=0.0):
    """Export thermoelectric properties in Nagatha-compatible format.

    Returns a dict that can be merged into Nagatha's material database.
    Includes all thermoelectric quantities and honest origin tags.

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Dict with all thermoelectric properties.
    """
    n_e = free_electron_density(material_key)
    E_F = fermi_energy_ev(material_key)
    S = seebeck_coefficient_uv_k(material_key, T)
    sigma_elec = electrical_conductivity(material_key)
    ZT = figure_of_merit_ZT(material_key, T, sigma)

    # Validation against measured Seebeck
    S_measured = _SEEBECK_MEASURED_UV_K.get(material_key)
    if S_measured is not None and S > 0:
        mott_accuracy = S / abs(S_measured)
    else:
        mott_accuracy = None

    return {
        'material': material_key,
        'temperature_K': T,
        'sigma': sigma,
        'free_electron_density_m3': n_e,
        'fermi_energy_eV': E_F,
        'seebeck_coefficient_uV_K': S,
        'seebeck_measured_uV_K': S_measured,
        'mott_formula_accuracy': mott_accuracy,
        'electrical_conductivity_S_m': sigma_elec,
        'figure_of_merit_ZT': ZT,
        'origin': (
            "Free electron density: FIRST_PRINCIPLES (Z_val × n_atoms). "
            "Fermi energy: FIRST_PRINCIPLES (Sommerfeld model). "
            "Seebeck: FIRST_PRINCIPLES (Mott formula) + "
            "APPROXIMATION (free-electron model). "
            "ZT: FIRST_PRINCIPLES (S²σT/κ). "
            "Valence electrons: MEASURED. "
            "Resistivity: MEASURED."
        ),
    }

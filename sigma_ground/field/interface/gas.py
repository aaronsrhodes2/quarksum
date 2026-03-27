"""
Gas-phase physics from molecular properties.

Derivation chain:
  σ → nuclear mass → reduced mass → vibrational frequency
  σ → molecular mass → ideal gas density → viscosity → thermal conductivity
  σ → vibrational modes → heat capacity of gas

This is the first non-solid module. Gases are fundamentally different:
  - No lattice, no coordination, no broken bonds
  - Properties come from MOLECULAR structure, not crystal structure
  - Transport is kinetic (molecules flying around), not phonon/electron

The key σ-insight for gases:
  Vibrational frequencies ω = √(k/μ) where k is the bond force constant
  (EM, σ-INVARIANT) and μ is the reduced mass (shifts with σ).

  If you measured CO₂'s infrared spectrum on a neutron star,
  the absorption bands would be SHIFTED. The bond stiffness is
  the same (EM), but the atoms are heavier → lower ω → longer λ.

  "You're not from around here, are you?"

Derivation stack:

  1. Reduced mass μ
     For diatomic A-B: μ = m_A × m_B / (m_A + m_B)
     FIRST_PRINCIPLES: classical mechanics of two-body problem.
     σ-dependence: m_A(σ) = A × m_u × (1 + σ×ξ×f_zpe)

  2. Vibrational frequency ω
     ω = √(k / μ)
     FIRST_PRINCIPLES: quantum harmonic oscillator.
     k = bond force constant (MEASURED, EM property).
     σ shifts μ → shifts ω → shifts infrared spectrum.

  3. Ideal gas density
     ρ = P × M / (R × T)
     FIRST_PRINCIPLES: ideal gas law (exact for dilute gases).
     M = molecular mass, shifts with σ.

  4. Heat capacity of gas
     C_v = C_trans + C_rot + C_vib
     C_trans = (3/2)R (FIRST_PRINCIPLES: equipartition, translation)
     C_rot = R (linear) or (3/2)R (nonlinear) (FIRST_PRINCIPLES)
     C_vib = Σ R × (θ_v/T)² × exp(θ_v/T) / (exp(θ_v/T)-1)²
       where θ_v = ℏω / k_B (vibrational temperature)
     FIRST_PRINCIPLES: quantum statistical mechanics.

  5. Viscosity (Chapman-Enskog)
     η = (5/16) × √(π m k_B T) / (π d² Ω)
     FIRST_PRINCIPLES: kinetic theory of gases.
     d = collision diameter (MEASURED).
     Ω = collision integral (~1 for hard spheres, APPROXIMATION).
     m shifts with σ → η shifts.

  6. Thermal conductivity of gas
     κ = η × c_v × f_eucken / M
     f_eucken = (9γ - 5) / 4  (Eucken correction)
     FIRST_PRINCIPLES: kinetic theory + internal degrees of freedom.

  7. Buoyancy velocity (free convection)
     v ~ √(g × L × ΔT / T_ambient)
     FIRST_PRINCIPLES: Archimedes + energy balance.

σ-dependence summary:
  EM (σ-invariant): bond force constants k, collision integral Ω
  Mass-dependent (σ-shifts): μ, ω, ρ, η, κ, C_vib, buoyancy

Origin tags:
  - Vibrational frequencies: FIRST_PRINCIPLES (QHO) + MEASURED (force constants)
  - Gas transport: FIRST_PRINCIPLES (Chapman-Enskog kinetic theory)
  - Heat capacity: FIRST_PRINCIPLES (quantum statistical mechanics)
  - Collision diameters: MEASURED
  - Bond force constants: MEASURED
"""

import math
from ..scale import scale_ratio
from ..constants import PROTON_QCD_FRACTION

# ── Constants ─────────────────────────────────────────────────────
_K_BOLTZMANN = 1.380649e-23       # J/K (exact, 2019 SI)
_HBAR = 1.054571817e-34           # J·s
_AMU_KG = 1.66053906660e-27       # atomic mass unit
_R_GAS = 8.314462618              # J/(mol·K) (exact, 2019 SI)
_AVOGADRO = 6.02214076e23         # /mol (exact, 2019 SI)
_C_LIGHT = 2.99792458e8           # m/s (exact)
_EV_TO_JOULE = 1.602176634e-19   # exact
_GRAVITY = 9.80665                # m/s² (standard)

# ── Molecular Database ───────────────────────────────────────────
# Each molecule is defined by its constituent atoms, geometry,
# bond force constants, and collision diameter.
#
# Bond force constants k: MEASURED from infrared spectroscopy.
# Source: NIST Chemistry WebBook, Herzberg "Spectra of Diatomic Molecules"
#
# Force constant units: N/m (spring constant of the bond).
# These are EM properties — they depend on the electron cloud,
# not the nuclear mass. σ-INVARIANT.
#
# Collision diameter d: MEASURED from gas viscosity data.
# Source: Hirschfelder, Curtiss & Bird "Molecular Theory of Gases and Liquids"
#
# Geometry: 'linear' or 'nonlinear' — determines rotational DOF.

MOLECULES = {
    'N2': {
        'name': 'Molecular Nitrogen',
        'atoms': {'N': 2},
        'molecular_mass_amu': 28.014,
        'geometry': 'linear',
        'collision_diameter_angstrom': 3.681,
        'bonds': [
            {'type': 'N≡N', 'force_constant_N_m': 2294.0,
             'atom_A_amu': 14.007, 'atom_B_amu': 14.007},
        ],
        'bond_dissociation_ev': 9.79,  # MEASURED: triple bond, very strong
    },
    'O2': {
        'name': 'Molecular Oxygen',
        'atoms': {'O': 2},
        'molecular_mass_amu': 31.998,
        'geometry': 'linear',
        'collision_diameter_angstrom': 3.433,
        'bonds': [
            {'type': 'O=O', 'force_constant_N_m': 1177.0,
             'atom_A_amu': 15.999, 'atom_B_amu': 15.999},
        ],
        'bond_dissociation_ev': 5.12,  # MEASURED
    },
    'CO2': {
        'name': 'Carbon Dioxide',
        'atoms': {'C': 1, 'O': 2},
        'molecular_mass_amu': 44.009,
        'geometry': 'linear',
        'collision_diameter_angstrom': 3.996,
        'bonds': [
            # Two C=O double bonds — normal mode analysis
            # For polyatomic molecules, the "force constant" is the
            # effective normal-mode force constant, not the individual
            # bond force constant. Normal mode coupling shifts the
            # effective k relative to the bare bond k.
            # MEASURED from IR spectroscopy (effective values).
            #
            # Asymmetric stretch: 2349 cm⁻¹
            # With C-O reduced mass (6.86 amu): k_eff = μ(2πcν̃)² = 2234 N/m
            # Symmetric stretch: 1333 cm⁻¹ → k_eff = 719 N/m
            # Bending mode: 667 cm⁻¹ → different effective mass
            {'type': 'C=O_asym', 'force_constant_N_m': 2234.0,
             'atom_A_amu': 12.011, 'atom_B_amu': 15.999},
            {'type': 'C=O_sym', 'force_constant_N_m': 719.0,
             'atom_A_amu': 12.011, 'atom_B_amu': 15.999},
            # Bending mode: effective mass is different (whole molecule bends)
            # For the bending mode, effective reduced mass ≈ m_O
            {'type': 'bend', 'force_constant_N_m': 57.0,
             'atom_A_amu': 15.999, 'atom_B_amu': 15.999},
        ],
        'vibrational_modes': 4,  # 3N-5 = 4 for linear triatomic (bend is degenerate)
    },
    'H2O': {
        'name': 'Water',
        'atoms': {'H': 2, 'O': 1},
        'molecular_mass_amu': 18.015,
        'geometry': 'nonlinear',
        'collision_diameter_angstrom': 2.641,
        'bonds': [
            # O-H symmetric stretch: 3657 cm⁻¹
            {'type': 'O-H_sym', 'force_constant_N_m': 773.0,
             'atom_A_amu': 15.999, 'atom_B_amu': 1.008},
            # O-H asymmetric stretch: 3756 cm⁻¹
            {'type': 'O-H_asym', 'force_constant_N_m': 815.0,
             'atom_A_amu': 15.999, 'atom_B_amu': 1.008},
            # H-O-H bend: 1595 cm⁻¹
            # Effective reduced mass for bend ≈ 2 × m_H (both H atoms move)
            {'type': 'bend', 'force_constant_N_m': 70.0,
             'atom_A_amu': 1.008, 'atom_B_amu': 1.008},
        ],
        'vibrational_modes': 3,  # 3N-6 = 3 for nonlinear triatomic
    },
    'CH4': {
        'name': 'Methane',
        'atoms': {'C': 1, 'H': 4},
        'molecular_mass_amu': 16.043,
        'geometry': 'nonlinear',
        'collision_diameter_angstrom': 3.758,
        'bonds': [
            # C-H stretch (symmetric): 2917 cm⁻¹
            {'type': 'C-H_stretch', 'force_constant_N_m': 516.0,
             'atom_A_amu': 12.011, 'atom_B_amu': 1.008},
            # C-H bend: 1534 cm⁻¹
            {'type': 'C-H_bend', 'force_constant_N_m': 46.0,
             'atom_A_amu': 12.011, 'atom_B_amu': 1.008},
        ],
        'bond_dissociation_ev': 4.51,  # C-H bond energy, MEASURED
        'vibrational_modes': 9,  # 3×5 - 6 = 9
    },
    'CO': {
        'name': 'Carbon Monoxide',
        'atoms': {'C': 1, 'O': 1},
        'molecular_mass_amu': 28.010,
        'geometry': 'linear',
        'collision_diameter_angstrom': 3.590,
        'bonds': [
            {'type': 'C≡O', 'force_constant_N_m': 1902.0,
             'atom_A_amu': 12.011, 'atom_B_amu': 15.999},
        ],
        'bond_dissociation_ev': 11.09,  # MEASURED: strongest diatomic bond
    },
}

# ── Bond Dissociation Energies (MEASURED) ────────────────────────
# Energy to break a specific bond type, in eV.
# Source: CRC Handbook, NIST JANAF Tables.
# These are EM properties → σ-INVARIANT to first order.
#
# Used for combustion enthalpy via Hess's law.

BOND_ENERGIES_EV = {
    'C-H':  4.30,   # alkane C-H
    'C-C':  3.61,   # single bond
    'C=C':  6.36,   # double bond
    'C=O':  8.33,   # as in CO₂ (average of two C=O in CO₂)
    'O=O':  5.12,   # molecular oxygen
    'O-H':  4.80,   # as in H₂O
    'N≡N':  9.79,   # molecular nitrogen (very strong)
    'C≡O': 11.09,   # carbon monoxide
    'C-O':  3.71,   # single bond (ether/alcohol)
}


# ── Reduced Mass ─────────────────────────────────────────────────

def reduced_mass(m_A_amu, m_B_amu, sigma=0.0):
    """Reduced mass μ of a two-body system (kg).

    μ = m_A × m_B / (m_A + m_B)

    FIRST_PRINCIPLES: classical mechanics. The two-body problem
    reduces to a single body with mass μ orbiting the center of mass.

    σ-dependence: nuclear masses shift.
      m(σ) = m(0) × [(1 - f_QCD) + f_QCD × e^σ]

    Args:
        m_A_amu, m_B_amu: atomic masses in AMU
        sigma: σ-field value

    Returns:
        Reduced mass in kg.
    """
    # σ-correction to nuclear mass
    f_qcd = PROTON_QCD_FRACTION
    mass_factor = (1.0 - f_qcd) + f_qcd * scale_ratio(sigma)

    m_A = m_A_amu * _AMU_KG * mass_factor
    m_B = m_B_amu * _AMU_KG * mass_factor

    return m_A * m_B / (m_A + m_B)


def molecular_mass_kg(mol_key, sigma=0.0):
    """Molecular mass in kg, with σ-correction.

    Args:
        mol_key: key into MOLECULES dict
        sigma: σ-field value

    Returns:
        Molecular mass in kg.
    """
    mol = MOLECULES[mol_key]
    f_qcd = PROTON_QCD_FRACTION
    mass_factor = (1.0 - f_qcd) + f_qcd * scale_ratio(sigma)
    return mol['molecular_mass_amu'] * _AMU_KG * mass_factor


# ── Vibrational Frequencies ──────────────────────────────────────

def vibrational_frequency_hz(force_constant_N_m, m_A_amu, m_B_amu, sigma=0.0):
    """Vibrational frequency of a bond (Hz).

    ω = √(k / μ)  →  f = ω / (2π)

    FIRST_PRINCIPLES: quantum harmonic oscillator. The bond is a
    spring with force constant k. The two atoms vibrate with
    frequency determined by k and the reduced mass μ.

    k is MEASURED (from infrared spectroscopy). It's an EM property
    of the electron cloud → σ-INVARIANT.

    μ shifts with σ through nuclear mass → frequency shifts.

    This is the "you're not from around here" test: measure the
    vibrational spectrum, and you can tell what σ is.

    Args:
        force_constant_N_m: bond force constant in N/m (MEASURED)
        m_A_amu, m_B_amu: atomic masses in AMU
        sigma: σ-field value

    Returns:
        Frequency in Hz.
    """
    mu = reduced_mass(m_A_amu, m_B_amu, sigma)
    omega = math.sqrt(force_constant_N_m / mu)
    return omega / (2.0 * math.pi)


def vibrational_wavenumber(force_constant_N_m, m_A_amu, m_B_amu, sigma=0.0):
    """Vibrational frequency in wavenumber (cm⁻¹).

    ν̃ = f / c  (in cm⁻¹, the standard IR spectroscopy unit)

    Spectroscopists use wavenumbers because they're proportional
    to energy: E = hcν̃.

    Args:
        force_constant_N_m: bond force constant in N/m
        m_A_amu, m_B_amu: atomic masses in AMU
        sigma: σ-field value

    Returns:
        Wavenumber in cm⁻¹.
    """
    f = vibrational_frequency_hz(force_constant_N_m, m_A_amu, m_B_amu, sigma)
    return f / (_C_LIGHT * 100.0)  # convert Hz to cm⁻¹


def vibrational_wavelength_um(force_constant_N_m, m_A_amu, m_B_amu, sigma=0.0):
    """Vibrational wavelength in micrometers.

    λ = c / f

    Args:
        force_constant_N_m: bond force constant
        m_A_amu, m_B_amu: atomic masses
        sigma: σ-field value

    Returns:
        Wavelength in μm.
    """
    f = vibrational_frequency_hz(force_constant_N_m, m_A_amu, m_B_amu, sigma)
    if f <= 0:
        return float('inf')
    return _C_LIGHT / f * 1e6  # meters to μm


def vibrational_temperature(force_constant_N_m, m_A_amu, m_B_amu, sigma=0.0):
    """Characteristic vibrational temperature θ_v (Kelvin).

    θ_v = ℏω / k_B = hf / k_B

    FIRST_PRINCIPLES: the temperature at which this vibrational mode
    becomes significantly excited. Below θ_v, the mode is "frozen out"
    and doesn't contribute to heat capacity.

    This is quantum statistics in action: classical physics says
    every mode gets k_BT/2 of energy. Quantum says modes with
    ℏω >> k_BT are barely populated. The transition happens at T ≈ θ_v.

    Args:
        force_constant_N_m: bond force constant
        m_A_amu, m_B_amu: atomic masses
        sigma: σ-field value

    Returns:
        Vibrational temperature in Kelvin.
    """
    f = vibrational_frequency_hz(force_constant_N_m, m_A_amu, m_B_amu, sigma)
    return _HBAR * 2.0 * math.pi * f / _K_BOLTZMANN


def molecule_vibrational_spectrum(mol_key, sigma=0.0):
    """Complete vibrational spectrum of a molecule.

    Returns list of dicts with frequency, wavenumber, wavelength,
    and vibrational temperature for each mode.

    This IS the infrared fingerprint. Change σ, and every line shifts.

    Args:
        mol_key: key into MOLECULES dict
        sigma: σ-field value

    Returns:
        List of mode dicts.
    """
    mol = MOLECULES[mol_key]
    spectrum = []
    for bond in mol['bonds']:
        k = bond['force_constant_N_m']
        m_A = bond['atom_A_amu']
        m_B = bond['atom_B_amu']

        f_hz = vibrational_frequency_hz(k, m_A, m_B, sigma)
        wn = vibrational_wavenumber(k, m_A, m_B, sigma)
        lam = vibrational_wavelength_um(k, m_A, m_B, sigma)
        theta = vibrational_temperature(k, m_A, m_B, sigma)

        spectrum.append({
            'mode': bond['type'],
            'frequency_hz': f_hz,
            'wavenumber_cm_inv': wn,
            'wavelength_um': lam,
            'vibrational_temperature_K': theta,
            'force_constant_N_m': k,
            'origin': 'FIRST_PRINCIPLES (ω=√(k/μ)) + MEASURED (k)',
        })

    return spectrum


# ── Ideal Gas Properties ─────────────────────────────────────────

def ideal_gas_density(mol_key, T=300.0, P=101325.0, sigma=0.0):
    """Density of an ideal gas (kg/m³).

    ρ = P × M / (R × T)

    FIRST_PRINCIPLES: ideal gas law PV = nRT.
    Exact for dilute gases. Good approximation for atmospheric
    pressure and T > 200K.

    σ-dependence: M (molecular mass) shifts with nuclear mass.

    Args:
        mol_key: key into MOLECULES dict
        T: temperature in Kelvin
        P: pressure in Pascals (default: 1 atm)
        sigma: σ-field value

    Returns:
        Density in kg/m³.
    """
    if T <= 0:
        return float('inf')
    M = molecular_mass_kg(mol_key, sigma) * _AVOGADRO  # kg/mol
    return P * M / (_R_GAS * T)


def number_density_gas(T=300.0, P=101325.0):
    """Number density of an ideal gas (molecules/m³).

    n = P / (k_B × T)

    FIRST_PRINCIPLES: ideal gas law. Independent of molecular species.

    Args:
        T: temperature in Kelvin
        P: pressure in Pascals

    Returns:
        Number density in molecules/m³.
    """
    if T <= 0:
        return float('inf')
    return P / (_K_BOLTZMANN * T)


# ── Gas Heat Capacity ────────────────────────────────────────────

def _einstein_cv_contribution(theta_v, T):
    """Einstein heat capacity contribution from one vibrational mode.

    C_v = R × (θ_v/T)² × exp(θ_v/T) / (exp(θ_v/T) - 1)²

    FIRST_PRINCIPLES: quantum harmonic oscillator partition function.
    This is exact for a single mode.

    At T >> θ_v: C_v → R (classical limit, equipartition)
    At T << θ_v: C_v → 0 (mode frozen out)
    """
    if T <= 0 or theta_v <= 0:
        return 0.0
    x = theta_v / T
    if x > 500:  # prevent overflow
        return 0.0
    exp_x = math.exp(x)
    return _R_GAS * x**2 * exp_x / (exp_x - 1.0)**2


def gas_cv_molar(mol_key, T=300.0, sigma=0.0):
    """Molar heat capacity C_v (J/(mol·K)) of a gas.

    C_v = C_trans + C_rot + C_vib

    FIRST_PRINCIPLES: quantum statistical mechanics.

    Translation: (3/2)R for all gases (3 translational DOF)
    Rotation: R for linear molecules (2 rotational DOF)
              (3/2)R for nonlinear molecules (3 rotational DOF)
    Vibration: Einstein model for each vibrational mode

    At room temperature (300K), most vibrational modes are frozen out
    (θ_v >> T), so gases behave nearly classically with C_v ≈ (5/2)R
    for diatomics and (3)R for nonlinear triatomics.

    At flame temperatures (1500-2000K), vibrational modes activate,
    increasing the heat capacity significantly.

    Args:
        mol_key: key into MOLECULES dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        C_v in J/(mol·K).
    """
    mol = MOLECULES[mol_key]

    # Translation: always (3/2)R
    cv = 1.5 * _R_GAS

    # Rotation
    if mol['geometry'] == 'linear':
        cv += _R_GAS          # 2 rotational DOF
    else:
        cv += 1.5 * _R_GAS   # 3 rotational DOF

    # Vibration: Einstein model for each mode
    for bond in mol['bonds']:
        k = bond['force_constant_N_m']
        m_A = bond['atom_A_amu']
        m_B = bond['atom_B_amu']
        theta_v = vibrational_temperature(k, m_A, m_B, sigma)
        cv += _einstein_cv_contribution(theta_v, T)

    return cv


def gas_cp_molar(mol_key, T=300.0, sigma=0.0):
    """Molar heat capacity C_p (J/(mol·K)) of an ideal gas.

    C_p = C_v + R

    FIRST_PRINCIPLES: for an ideal gas, C_p - C_v = R.
    This is exact (Mayer's relation).

    Args:
        mol_key: key into MOLECULES dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        C_p in J/(mol·K).
    """
    return gas_cv_molar(mol_key, T, sigma) + _R_GAS


def heat_capacity_ratio(mol_key, T=300.0, sigma=0.0):
    """Ratio of heat capacities γ = C_p / C_v.

    FIRST_PRINCIPLES: γ determines sound speed in gas.

    Monatomic: γ = 5/3 ≈ 1.667
    Diatomic (room T): γ = 7/5 = 1.400
    Polyatomic: γ < 1.400, decreases as vibrational modes activate.

    Args:
        mol_key: key into MOLECULES dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        γ (dimensionless).
    """
    cv = gas_cv_molar(mol_key, T, sigma)
    if cv <= 0:
        return 1.0
    return (cv + _R_GAS) / cv


# ── Gas Transport Properties ────────────────────────────────────

def gas_viscosity(mol_key, T=300.0, sigma=0.0):
    """Dynamic viscosity of a gas (Pa·s) from Chapman-Enskog theory.

    η = (5/16) × √(π m k_B T) / (π d² Ω)

    FIRST_PRINCIPLES: kinetic theory of gases (Chapman-Enskog
    solution to the Boltzmann equation). Molecules carry momentum
    between layers of gas, creating viscous drag.

    d = collision diameter (MEASURED from viscosity data).
    Ω = collision integral (≈ 1.0 for hard sphere model).
    APPROXIMATION: hard sphere model neglects attractive forces.

    σ-dependence: m (molecular mass) shifts → η shifts.
    d is an EM property (electron cloud size) → σ-INVARIANT.

    Proportional to √(mT), independent of pressure (for ideal gases).
    This non-intuitive result (viscosity doesn't depend on density!)
    was predicted by Maxwell and confirmed experimentally.

    Args:
        mol_key: key into MOLECULES dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Dynamic viscosity in Pa·s.
    """
    if T <= 0:
        return 0.0

    mol = MOLECULES[mol_key]
    m = molecular_mass_kg(mol_key, sigma)
    d = mol['collision_diameter_angstrom'] * 1e-10  # meters

    # Hard sphere collision integral
    omega_collision = 1.0  # APPROXIMATION

    # Chapman-Enskog formula
    numerator = (5.0 / 16.0) * math.sqrt(math.pi * m * _K_BOLTZMANN * T)
    denominator = math.pi * d**2 * omega_collision

    return numerator / denominator


def gas_thermal_conductivity(mol_key, T=300.0, sigma=0.0):
    """Thermal conductivity of a gas (W/(m·K)) from Eucken correction.

    κ = η × c_v × f_eucken / M

    Where f_eucken = (9γ - 5) / 4 (Eucken correction factor).

    FIRST_PRINCIPLES: kinetic theory predicts κ = η × c_v / M for
    monatomic gases. For polyatomic gases, internal energy transport
    (rotation, vibration) adds a correction factor. Eucken (1913)
    derived the correction from the assumption that translational
    and internal degrees of freedom transport energy with different
    efficiencies.

    APPROXIMATION: Eucken factor assumes translational Prandtl number
    is exactly 2/3. More accurate models (Mason-Monchick) exist but
    require more parameters.

    Args:
        mol_key: key into MOLECULES dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Thermal conductivity in W/(m·K).
    """
    eta = gas_viscosity(mol_key, T, sigma)
    cv = gas_cv_molar(mol_key, T, sigma)  # J/(mol·K)
    gamma = heat_capacity_ratio(mol_key, T, sigma)
    M = molecular_mass_kg(mol_key, sigma) * _AVOGADRO  # kg/mol

    # Eucken correction
    f_eucken = (9.0 * gamma - 5.0) / 4.0

    if M <= 0:
        return 0.0

    return eta * cv * f_eucken / M


def gas_diffusivity(mol_A, mol_B, T=300.0, P=101325.0, sigma=0.0):
    """Binary gas diffusion coefficient D_AB (m²/s).

    D = (3/16) × √(2πk_BT/μ) / (n × π × d_AB² × Ω)

    FIRST_PRINCIPLES: Chapman-Enskog theory for binary diffusion.
    Molecules of species A and B exchange positions through
    random thermal motion.

    d_AB = (d_A + d_B) / 2  (arithmetic mean, APPROXIMATION)
    Ω ≈ 1.0 (hard sphere)

    This is important for flames: oxygen must diffuse INTO the
    reaction zone, fuel vapor must diffuse OUT.

    Args:
        mol_A, mol_B: molecule keys
        T: temperature in Kelvin
        P: pressure in Pascals
        sigma: σ-field value

    Returns:
        D_AB in m²/s.
    """
    if T <= 0:
        return 0.0

    m_A = molecular_mass_kg(mol_A, sigma)
    m_B = molecular_mass_kg(mol_B, sigma)

    # Reduced mass for the pair
    mu_pair = m_A * m_B / (m_A + m_B)

    d_A = MOLECULES[mol_A]['collision_diameter_angstrom'] * 1e-10
    d_B = MOLECULES[mol_B]['collision_diameter_angstrom'] * 1e-10
    d_AB = (d_A + d_B) / 2.0

    n = number_density_gas(T, P)  # molecules/m³
    omega = 1.0  # hard sphere

    # Chapman-Enskog binary diffusion
    D = (3.0 / 16.0) * math.sqrt(2.0 * math.pi * _K_BOLTZMANN * T / mu_pair)
    D /= (n * math.pi * d_AB**2 * omega)

    return D


# ── Buoyancy ─────────────────────────────────────────────────────

def buoyancy_velocity(T_hot, T_ambient=300.0, L=0.01, g=_GRAVITY):
    """Characteristic buoyancy velocity for natural convection (m/s).

    v ~ √(g × L × (T_hot - T_ambient) / T_ambient)

    FIRST_PRINCIPLES: balance of buoyancy force (Archimedes) against
    inertial drag. Hot gas is less dense → rises.

    For a candle flame: T_hot ≈ 1400K, T_ambient ≈ 300K, L ≈ 3cm
    gives v ≈ 0.3 m/s (measured: 0.2-0.5 m/s).

    The Boussinesq approximation: density variations are small enough
    to affect only the buoyancy term, not the inertia or continuity.
    Valid when ΔT/T << 1. For flames (ΔT/T ~ 4), it's stretched
    but still gives the right order of magnitude.
    APPROXIMATION: Boussinesq estimate.

    Args:
        T_hot: temperature of hot gas in K
        T_ambient: ambient temperature in K
        L: characteristic length in meters (flame height)
        g: gravitational acceleration

    Returns:
        Velocity in m/s.
    """
    if T_ambient <= 0 or T_hot <= T_ambient:
        return 0.0

    delta_T = T_hot - T_ambient
    return math.sqrt(g * L * delta_T / T_ambient)


def grashof_number(T_hot, T_ambient=300.0, L=0.01, mol_key='N2', sigma=0.0):
    """Grashof number Gr — ratio of buoyancy to viscous forces.

    Gr = g × β × ΔT × L³ / ν²

    Where:
      β = 1/T (ideal gas thermal expansion coefficient)
      ν = η/ρ (kinematic viscosity)

    FIRST_PRINCIPLES: dimensionless number from Navier-Stokes.
    Gr > 10⁹: turbulent natural convection.
    Gr < 10⁹: laminar (candle flames are laminar!).

    Args:
        T_hot, T_ambient: temperatures in K
        L: characteristic length
        mol_key: gas species (for viscosity)
        sigma: σ-field value

    Returns:
        Grashof number (dimensionless).
    """
    if T_ambient <= 0 or T_hot <= T_ambient:
        return 0.0

    T_avg = (T_hot + T_ambient) / 2.0
    beta = 1.0 / T_avg  # ideal gas: β = 1/T

    eta = gas_viscosity(mol_key, T_avg, sigma)
    rho = ideal_gas_density(mol_key, T_avg, sigma=sigma)

    if eta <= 0 or rho <= 0:
        return 0.0

    nu = eta / rho  # kinematic viscosity

    delta_T = T_hot - T_ambient
    return _GRAVITY * beta * delta_T * L**3 / nu**2


# ── σ-Spectroscopy ───────────────────────────────────────────────

def sigma_from_frequency_shift(f_observed, f_expected, m_A_amu, m_B_amu):
    """Estimate σ from an observed frequency shift.

    If ω = √(k/μ) and k is σ-invariant, then:
      ω(σ) / ω(0) = √(μ(0) / μ(σ))

    Inverting: μ(σ) = μ(0) × (ω(0)/ω(σ))²

    And since μ ∝ mass_factor:
      mass_factor = (f_expected / f_observed)²
      mass_factor = (1 - f_QCD) + f_QCD × e^σ
      e^σ = (mass_factor - (1 - f_QCD)) / f_QCD
      σ = ln(e^σ)

    This is the "you're not from around here" detector:
    measure an infrared spectrum, compare to Earth values,
    and you can read off σ.

    FIRST_PRINCIPLES: pure algebra from ω = √(k/μ).

    Args:
        f_observed: observed frequency (any units)
        f_expected: expected frequency at σ=0 (same units)
        m_A_amu, m_B_amu: not used directly (for reference)

    Returns:
        Estimated σ value. Returns 0 if frequencies match.
    """
    if f_observed <= 0 or f_expected <= 0:
        return 0.0

    # ω ∝ 1/√μ ∝ 1/√(mass_factor)
    # So mass_factor = (f_expected / f_observed)²
    mass_factor = (f_expected / f_observed) ** 2

    f_qcd = PROTON_QCD_FRACTION

    # mass_factor = (1 - f_qcd) + f_qcd × e^σ
    exp_sigma = (mass_factor - (1.0 - f_qcd)) / f_qcd

    if exp_sigma <= 0:
        return 0.0  # unphysical — can't have negative mass factor

    return math.log(exp_sigma)


# ── Nagatha Export ────────────────────────────────────────────────

def molecule_gas_properties(mol_key, T=300.0, P=101325.0, sigma=0.0):
    """Export gas properties in Nagatha-compatible format.

    Args:
        mol_key: key into MOLECULES dict
        T: temperature in Kelvin
        P: pressure in Pascals
        sigma: σ-field value

    Returns:
        Dict with all gas-phase properties.
    """
    mol = MOLECULES[mol_key]
    rho = ideal_gas_density(mol_key, T, P, sigma)
    eta = gas_viscosity(mol_key, T, sigma)
    kappa = gas_thermal_conductivity(mol_key, T, sigma)
    cv = gas_cv_molar(mol_key, T, sigma)
    cp = gas_cp_molar(mol_key, T, sigma)
    gamma = heat_capacity_ratio(mol_key, T, sigma)
    spectrum = molecule_vibrational_spectrum(mol_key, sigma)

    return {
        'molecule': mol_key,
        'name': mol['name'],
        'temperature_K': T,
        'pressure_Pa': P,
        'sigma': sigma,
        'density_kg_m3': rho,
        'viscosity_Pa_s': eta,
        'thermal_conductivity_W_mK': kappa,
        'cv_molar_J_molK': cv,
        'cp_molar_J_molK': cp,
        'gamma': gamma,
        'vibrational_spectrum': spectrum,
        'origin': (
            "Density: FIRST_PRINCIPLES (ideal gas law). "
            "Viscosity: FIRST_PRINCIPLES (Chapman-Enskog) + "
            "APPROXIMATION (hard sphere collision integral). "
            "Thermal conductivity: FIRST_PRINCIPLES (kinetic theory) + "
            "APPROXIMATION (Eucken correction). "
            "Heat capacity: FIRST_PRINCIPLES (quantum statistical mechanics). "
            "Vibrational frequencies: FIRST_PRINCIPLES (ω=√(k/μ)) + "
            "MEASURED (force constants from IR spectroscopy). "
            "Collision diameters: MEASURED."
        ),
    }

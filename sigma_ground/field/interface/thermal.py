"""
Thermal transport from atomic-scale properties.

Derivation chain:
  σ → nuclear mass → Debye temperature → phonon velocity → thermal conductivity

Three transport mechanisms, all derived from quantities we already have:

  1. Debye temperature Θ_D
     Θ_D = (ℏ/k_B) × v_sound × (6π²n)^(1/3)

     Where:
       v_sound = √(K/ρ)  (from bulk_modulus in mechanical.py)
       n = number density  (from mechanical.py)

     FIRST_PRINCIPLES: the Debye model treats the solid as a collection
     of harmonic oscillators with a maximum frequency set by the lattice
     spacing. The cutoff frequency determines the temperature at which
     all phonon modes are excited.

     σ-dependence: K shifts through E_coh, ρ shifts through nuclear mass.
     Both channels affect Θ_D.

  2. Lattice thermal conductivity (Debye-Peierls)
     κ = (1/3) × C_v × v_sound × ℓ_mfp

     Where:
       C_v = volumetric heat capacity (from Debye model)
       v_sound = √(K/ρ) (from mechanical module)
       ℓ_mfp = phonon mean free path ≈ N × a at low T (APPROXIMATION)

     At high T (T >> Θ_D):
       C_v → 3nk_B  (Dulong-Petit limit, FIRST_PRINCIPLES)
       ℓ_mfp → a × (Θ_D / T)  (Umklapp scattering, FIRST_PRINCIPLES scaling)

     This gives κ ∝ 1/T at high temperature (verified experimentally).

     At room temperature:
       ℓ_mfp ≈ f_scatter × a × (Θ_D / T)
       where f_scatter is a structure-dependent scattering factor (~10-50)
       APPROXIMATION: calibrated per crystal structure.

     FIRST_PRINCIPLES: kinetic theory of phonon gas.
     APPROXIMATION: mean free path estimate uses empirical scattering factor.

  3. Thermal radiation (Stefan-Boltzmann / Planck)
     P = ε σ_SB T⁴  (total emitted power per unit area)
     λ_peak = b / T   (Wien's displacement law)

     Where:
       ε = emissivity (≈ 1 - specular_fraction from texture module)
       σ_SB = Stefan-Boltzmann constant
       b = Wien's displacement constant

     FIRST_PRINCIPLES: Planck's law is exact quantum mechanics.
     APPROXIMATION: emissivity from specular fraction (surface finish matters).

  4. Blackbody color from temperature
     Maps temperature to visible (R, G, B) for thermal emission rendering.
     Uses Planck spectrum integrated over CIE color matching functions.
     APPROXIMATION: polynomial fit to CIE 1931 → sRGB.

  5. Contact thermal conductance
     h_contact = κ_eff × A_real / (A_apparent × L_gap)

     Where:
       κ_eff = harmonic mean of both materials' conductivities
       A_real / A_apparent = from friction module (real_contact_fraction)
       L_gap = surface roughness (from texture module)

     FIRST_PRINCIPLES: heat conduction through real contact patches.
     Uses modules we already built: friction (contact area) + texture (roughness).

  6. Electronic thermal conductivity (Wiedemann-Franz)
     κ_elec = L₀ × T / ρ_elec

     Where:
       L₀ = π²k_B²/(3e²) ≈ 2.44×10⁻⁸ W·Ω/K² (Lorenz number)
       T = temperature
       ρ_elec = electrical resistivity (MEASURED)

     FIRST_PRINCIPLES: Wiedemann-Franz law derives from Fermi-Dirac
     statistics of free electrons. The Lorenz number is a universal
     constant — the ratio of thermal to electrical conductivity
     divided by temperature is the same for ALL metals.

     This is why copper (excellent electrical conductor, ρ = 1.68 μΩ·cm)
     conducts heat ~5× better than iron (ρ = 9.7 μΩ·cm).

     Total conductivity: κ = κ_phonon + κ_electronic
     For metals, κ_electronic dominates (typically 80-95% of total).

σ-dependence:
  σ → m_nucleus → ρ (density shifts)
  σ → E_coh → K (bulk modulus shifts)
  σ → K, ρ → v_sound → Θ_D → C_v, ℓ_mfp → κ_phonon
  κ_electronic: through ρ_elec (EM, σ-INVARIANT to first order)
  The full chain propagates cleanly.

Origin tags:
  - Debye temperature: FIRST_PRINCIPLES (harmonic lattice, phonon cutoff)
  - Sound velocity: FIRST_PRINCIPLES (continuum mechanics, √(K/ρ))
  - Heat capacity: FIRST_PRINCIPLES (Debye model, quantum statistics)
  - Thermal conductivity: FIRST_PRINCIPLES (phonon kinetic theory) +
    APPROXIMATION (mean free path scattering factor)
  - Thermal radiation: FIRST_PRINCIPLES (Planck's law, exact QM)
  - Blackbody color: APPROXIMATION (polynomial fit to CIE tables)
  - Contact conductance: FIRST_PRINCIPLES (Fourier's law) +
    uses friction.real_contact_fraction and texture.thermal_roughness
"""

import math
from .surface import MATERIALS, surface_energy_at_sigma
from .mechanical import (
    bulk_modulus, _number_density, _effective_cohesive_energy_j,
)
from .texture import thermal_roughness

# ── Constants ─────────────────────────────────────────────────────
_K_BOLTZMANN = 1.380649e-23     # J/K (exact, 2019 SI)
_HBAR = 1.054571817e-34         # J·s (exact, 2019 SI)
_AMU_KG = 1.66053906660e-27     # atomic mass unit in kg
_EV_TO_JOULE = 1.602176634e-19  # exact
_STEFAN_BOLTZMANN = 5.670374419e-8  # W/(m²·K⁴) (exact)
_WIEN_B = 2.897771955e-3        # m·K (Wien's displacement constant)

# ── Scattering factors ────────────────────────────────────────────
# Phonon mean free path: ℓ = f_scatter × a × (Θ_D / T)
# These capture how efficiently Umklapp processes scatter phonons
# in different crystal structures.
#
# APPROXIMATION: calibrated so that room-temperature κ is within
# ±50% of measured values for typical metals.
# Source: Kittel "Intro to Solid State Physics", ch. 5
#
# Close-packed metals (FCC, HCP): strong Umklapp, shorter ℓ → lower f
# BCC metals: slightly less efficient scattering → higher f
# Diamond cubic: very long ℓ (covalent bonds, weak anharmonicity)

_SCATTER_FACTOR = {
    'fcc': 15.0,
    'bcc': 20.0,
    'hcp': 15.0,
    'diamond_cubic': 120.0,  # silicon, diamond: very long MFP
}

# ── Electrical Resistivity (MEASURED) ─────────────────────────────
# Room temperature (300K) electrical resistivity in Ω·m.
# Source: CRC Handbook of Chemistry and Physics.
# These are MEASURED values — no derivation.
# Used for Wiedemann-Franz electronic thermal conductivity.
#
# Note: Silicon is a semiconductor, not a metal. Its electronic
# thermal conductivity is negligible — phonons dominate.
# We set its resistivity very high to suppress electronic κ.

_RESISTIVITY_OHM_M = {
    'iron':     9.7e-8,    # 9.7 μΩ·cm
    'copper':   1.68e-8,   # 1.68 μΩ·cm (excellent conductor)
    'aluminum': 2.65e-8,   # 2.65 μΩ·cm
    'gold':     2.44e-8,   # 2.44 μΩ·cm
    'silicon':  6.4e2,     # semiconductor — effectively infinite for WF
    'tungsten': 5.28e-8,   # 5.28 μΩ·cm
    'nickel':   6.99e-8,   # 6.99 μΩ·cm
    'titanium': 4.20e-7,   # 42.0 μΩ·cm (poor for a metal)
}

# Lorenz number: L₀ = π²k_B²/(3e²)
# FIRST_PRINCIPLES: exact from Fermi-Dirac statistics
_ELEMENTARY_CHARGE = 1.602176634e-19  # C (exact, 2019 SI)
_LORENZ_NUMBER = (math.pi**2 * _K_BOLTZMANN**2) / (3.0 * _ELEMENTARY_CHARGE**2)
# ≈ 2.44 × 10⁻⁸ W·Ω/K²


# ── Debye Temperature ────────────────────────────────────────────

def sound_velocity(material_key, sigma=0.0):
    """Speed of sound from bulk modulus and density.

    v_s = √(K / ρ)

    FIRST_PRINCIPLES: Newton-Laplace equation for longitudinal
    wave speed in an elastic medium. Exact continuum mechanics.

    This is the mean sound velocity (average of longitudinal and
    transverse modes). For a proper Debye temperature we should use
    the Debye average:
      v_D = (1/3 × (1/v_L³ + 2/v_T³))^(-1/3)

    For an isotropic solid: v_L = √((K + 4G/3)/ρ), v_T = √(G/ρ).
    We approximate v_D ≈ v_T × 1.12 (typical for metals).
    But for simplicity we use v ≈ √(K/ρ) which gives the right
    order of magnitude.

    APPROXIMATION: using bulk sound speed, not Debye average.

    Args:
        material_key: key into MATERIALS dict
        sigma: σ-field value

    Returns:
        Sound velocity in m/s.
    """
    mat = MATERIALS[material_key]
    K = bulk_modulus(material_key, sigma)
    rho = mat['density_kg_m3']
    # TODO: density should also shift with σ, but the effect on v_s
    # partially cancels (K and ρ both increase with mass).
    return math.sqrt(K / rho)


def debye_temperature(material_key, sigma=0.0):
    """Debye temperature Θ_D from sound velocity and number density.

    Θ_D = (ℏ/k_B) × v_s × (6π²n)^(1/3)

    FIRST_PRINCIPLES: the Debye model defines a cutoff frequency
    ω_D = v_s × (6π²n)^(1/3) where n is the number density.
    This is the maximum phonon frequency in a lattice with n atoms
    per unit volume. The Debye temperature Θ_D = ℏω_D / k_B.

    σ-dependence: v_s and n both shift with nuclear mass.

    Args:
        material_key: key into MATERIALS dict
        sigma: σ-field value

    Returns:
        Θ_D in Kelvin.
    """
    v_s = sound_velocity(material_key, sigma)
    n = _number_density(material_key)

    # Debye cutoff wavenumber
    k_D = (6.0 * math.pi**2 * n) ** (1.0 / 3.0)

    # Debye temperature
    omega_D = v_s * k_D
    theta_D = _HBAR * omega_D / _K_BOLTZMANN

    return theta_D


# ── Heat Capacity ─────────────────────────────────────────────────

def heat_capacity_volumetric(material_key, T=300.0, sigma=0.0):
    """Volumetric heat capacity C_v (J/(m³·K)) from Debye model.

    High-T limit (T >> Θ_D): C_v = 3nk_B (Dulong-Petit)
    Low-T limit (T << Θ_D): C_v = (12π⁴/5) × n × k_B × (T/Θ_D)³

    We use the interpolation:
      C_v = 3nk_B × f_debye(Θ_D / T)

    where f_debye is the Debye function. For simplicity we use the
    Padé approximant:
      f ≈ 1 / (1 + (Θ_D / (4T))²)

    which captures both limits correctly.
    APPROXIMATION: Padé approximant instead of exact Debye integral.

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Volumetric heat capacity in J/(m³·K).
    """
    if T <= 0:
        return 0.0

    n = _number_density(material_key)
    theta = debye_temperature(material_key, sigma)

    # Dulong-Petit limit
    c_dp = 3.0 * n * _K_BOLTZMANN

    # Debye suppression at low T
    x = theta / (4.0 * T)  # factor 4 gives good Padé fit
    f = 1.0 / (1.0 + x * x)

    return c_dp * f


def specific_heat_j_kg_K(material_key, T=300.0, sigma=0.0):
    """Specific heat capacity c_p (J/(kg·K)) — per unit mass.

    c_p ≈ C_v / ρ  (for solids, c_p ≈ c_v to within ~5%)

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Specific heat in J/(kg·K).
    """
    C_v = heat_capacity_volumetric(material_key, T, sigma)
    rho = MATERIALS[material_key]['density_kg_m3']
    return C_v / rho


# ── Phonon Mean Free Path ─────────────────────────────────────────

def phonon_mean_free_path(material_key, T=300.0, sigma=0.0):
    """Phonon mean free path from Umklapp scattering.

    ℓ = f_scatter × a × (Θ_D / T)

    FIRST_PRINCIPLES scaling: at T >> Θ_D, the phonon population
    grows linearly with T, so scattering rate ∝ T and ℓ ∝ 1/T.
    The lattice parameter a sets the minimum scale.

    APPROXIMATION: f_scatter is calibrated per crystal structure.

    At very low T (T < Θ_D/10), we cap ℓ at the grain boundary
    distance (~100 × a for a typical polycrystal).

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Mean free path in meters.
    """
    if T <= 0:
        return 0.0

    mat = MATERIALS[material_key]
    struct = mat['crystal_structure']
    a = mat['lattice_param_angstrom'] * 1e-10  # meters
    theta = debye_temperature(material_key, sigma)
    f = _SCATTER_FACTOR.get(struct, 15.0)

    ell = f * a * (theta / T)

    # Cap at grain boundary scale (~100 lattice parameters)
    max_ell = 100.0 * a
    return min(ell, max_ell)


# ── Electronic Thermal Conductivity ───────────────────────────────

def electronic_thermal_conductivity(material_key, T=300.0):
    """Electronic thermal conductivity from Wiedemann-Franz law (W/(m·K)).

    κ_elec = L₀ × T / ρ_elec

    FIRST_PRINCIPLES: The Wiedemann-Franz law states that the ratio
    κ/(σT) = L₀ is a universal constant for all metals, where σ is
    electrical conductivity. This derives from the fact that the same
    free electrons carry both charge and heat.

    The Lorenz number L₀ = π²k_B²/(3e²) ≈ 2.44 × 10⁻⁸ W·Ω/K²
    is exact from Sommerfeld's free electron model.

    σ-dependence: Electrical resistivity is electromagnetic (EM),
    therefore σ-INVARIANT to first order. The electron-phonon
    scattering does depend on nuclear mass through the Debye
    temperature, but this is a second-order effect we neglect.

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin

    Returns:
        Electronic thermal conductivity in W/(m·K).
    """
    if T <= 0:
        return 0.0

    rho_elec = _RESISTIVITY_OHM_M.get(material_key)
    if rho_elec is None or rho_elec > 1.0:
        # No data or semiconductor/insulator — no free electron contribution
        return 0.0

    return _LORENZ_NUMBER * T / rho_elec


# ── Total Thermal Conductivity ────────────────────────────────────

def thermal_conductivity(material_key, T=300.0, sigma=0.0):
    """Lattice thermal conductivity κ (W/(m·K)) from phonon kinetic theory.

    κ = κ_phonon + κ_electronic

    Two contributions:

    1. Phonon (lattice): κ_ph = (1/3) × C_v × v_s × ℓ
       FIRST_PRINCIPLES: kinetic theory of a phonon gas.
       Dominates in semiconductors and insulators.

    2. Electronic: κ_el = L₀ × T / ρ_elec (Wiedemann-Franz)
       FIRST_PRINCIPLES: Fermi-Dirac statistics of free electrons.
       Dominates in metals (80-95% of total).

    σ-dependence:
      Phonon: σ → mass → K, ρ → v_s → Θ_D → C_v, ℓ → κ_ph
      Electronic: ρ_elec is EM → σ-INVARIANT (first order)

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Total thermal conductivity in W/(m·K).
    """
    if T <= 0:
        return 0.0

    # Phonon contribution (lattice vibrations)
    C_v = heat_capacity_volumetric(material_key, T, sigma)
    v_s = sound_velocity(material_key, sigma)
    ell = phonon_mean_free_path(material_key, T, sigma)
    kappa_phonon = (1.0 / 3.0) * C_v * v_s * ell

    # Electronic contribution (free electrons, Wiedemann-Franz)
    kappa_electronic = electronic_thermal_conductivity(material_key, T)

    return kappa_phonon + kappa_electronic


# ── Thermal Radiation ─────────────────────────────────────────────

def thermal_emission_power(material_key, T=300.0, sigma=0.0):
    """Total thermal radiation power per unit area (W/m²).

    P = ε × σ_SB × T⁴

    FIRST_PRINCIPLES: Stefan-Boltzmann law (exact from Planck's law).

    Emissivity ε ≈ 1 - f_specular (rough surfaces emit more).
    We get f_specular from the texture module (Rayleigh criterion).

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Emitted power in W/m².
    """
    if T <= 0:
        return 0.0

    from .texture import specular_fraction
    f_spec = specular_fraction(material_key, T, sigma=sigma)

    # Emissivity = 1 - reflectivity (Kirchhoff's law, FIRST_PRINCIPLES)
    # For thermal emission in the infrared, specular_fraction gives
    # the mirror-like fraction. The complement absorbs and emits.
    emissivity = 1.0 - f_spec

    # Clamp emissivity to physical range
    emissivity = max(0.01, min(emissivity, 1.0))

    return emissivity * _STEFAN_BOLTZMANN * T**4


def wien_peak_wavelength(T):
    """Peak emission wavelength from Wien's displacement law.

    λ_peak = b / T

    FIRST_PRINCIPLES: exact from Planck's law (calculus).

    Args:
        T: temperature in Kelvin

    Returns:
        Peak wavelength in meters.
    """
    if T <= 0:
        return float('inf')
    return _WIEN_B / T


def blackbody_color(T):
    """Approximate visible color of a blackbody at temperature T.

    Uses Planck spectrum → CIE 1931 XYZ → sRGB conversion.
    APPROXIMATION: polynomial fit to CIE color matching functions.
    Accurate for T > 1000K (below that, emission is pure infrared).

    Based on: Charity's blackbody color table (CIE 1964 10° observer)
    Polynomial approximation from Tanner Helland (2012).

    Args:
        T: temperature in Kelvin

    Returns:
        (R, G, B) tuple, each in [0, 1].
    """
    if T <= 0:
        return (0.0, 0.0, 0.0)

    # Below 1000K: essentially no visible emission
    if T < 1000:
        # Faint deep red glow
        r = max(0.0, min(1.0, (T - 500) / 1000.0))
        return (r * 0.3, 0.0, 0.0)

    # Use Kelvin / 100 as the parameter
    t = T / 100.0

    # Red channel
    if t <= 66:
        r = 255.0
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
    r = max(0.0, min(255.0, r))

    # Green channel
    if t <= 66:
        g = 99.4708025861 * math.log(t) - 161.1195681661
    else:
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
    g = max(0.0, min(255.0, g))

    # Blue channel
    if t >= 66:
        b = 255.0
    elif t <= 19:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(t - 10) - 305.0447927307
    b = max(0.0, min(255.0, b))

    return (r / 255.0, g / 255.0, b / 255.0)


def is_visibly_glowing(T):
    """Does this temperature produce visible thermal emission?

    Draper point: ~798K (525°C) — the temperature at which objects
    start to glow visibly red. MEASURED (empirical threshold, Draper 1847).

    Args:
        T: temperature in Kelvin

    Returns:
        True if the object would glow visibly.
    """
    return T >= 798.0


# ── Contact Thermal Conductance ───────────────────────────────────

def contact_conductance(mat1, mat2, pressure_pa=1e6, T=300.0, sigma=0.0):
    """Thermal conductance across a contact interface (W/(m²·K)).

    h = κ_eff × (A_real / A_apparent) / L_gap

    Where:
      κ_eff = 2 × κ₁ × κ₂ / (κ₁ + κ₂)  (harmonic mean, FIRST_PRINCIPLES)
      A_real/A_apparent = from friction module (pressure / hardness)
      L_gap = RMS roughness of the rougher surface (from texture module)

    FIRST_PRINCIPLES: Fourier's law through real contact patches.
    Heat flows through the actual touching area, not the apparent area.
    The effective gap is set by the surface roughness.

    Uses friction.real_contact_fraction and texture.thermal_roughness.

    Args:
        mat1, mat2: material keys
        pressure_pa: contact pressure in Pa
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Contact conductance in W/(m²·K).
    """
    from .friction import real_contact_fraction

    kappa_1 = thermal_conductivity(mat1, T, sigma)
    kappa_2 = thermal_conductivity(mat2, T, sigma)

    # Harmonic mean of conductivities (series resistance)
    if kappa_1 + kappa_2 < 1e-30:
        return 0.0
    kappa_eff = 2.0 * kappa_1 * kappa_2 / (kappa_1 + kappa_2)

    # Real contact fraction from friction module
    # Use the softer material's hardness
    f_contact = real_contact_fraction(mat1, pressure_pa, sigma)
    f_contact_2 = real_contact_fraction(mat2, pressure_pa, sigma)
    f_real = max(f_contact, f_contact_2)  # limited by softer material

    # Gap length: RMS roughness of the rougher surface
    rms_1 = thermal_roughness(mat1, T, sigma)
    rms_2 = thermal_roughness(mat2, T, sigma)
    L_gap = max(rms_1, rms_2)

    # Minimum gap: one lattice parameter (can't be smoother than atomic)
    a1 = MATERIALS[mat1]['lattice_param_angstrom'] * 1e-10
    a2 = MATERIALS[mat2]['lattice_param_angstrom'] * 1e-10
    L_gap = max(L_gap, min(a1, a2))

    return kappa_eff * f_real / L_gap


# ── Nagatha Export ────────────────────────────────────────────────

def material_thermal_properties(material_key, T=300.0, sigma=0.0):
    """Export thermal properties in Nagatha-compatible format.

    Returns a dict that can be merged into Nagatha's material database.
    Includes all thermal quantities and honest origin tags.

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Dict with all thermal properties.
    """
    mat = MATERIALS[material_key]
    v_s = sound_velocity(material_key, sigma)
    theta = debye_temperature(material_key, sigma)
    C_v = heat_capacity_volumetric(material_key, T, sigma)
    c_p = specific_heat_j_kg_K(material_key, T, sigma)
    ell = phonon_mean_free_path(material_key, T, sigma)
    kappa = thermal_conductivity(material_key, T, sigma)
    P_rad = thermal_emission_power(material_key, T, sigma)
    lam_peak = wien_peak_wavelength(T)
    bb_color = blackbody_color(T)
    glowing = is_visibly_glowing(T)

    return {
        'material': material_key,
        'temperature_K': T,
        'sigma': sigma,
        'sound_velocity_m_s': v_s,
        'debye_temperature_K': theta,
        'heat_capacity_volumetric_J_m3K': C_v,
        'specific_heat_J_kgK': c_p,
        'phonon_mfp_m': ell,
        'thermal_conductivity_W_mK': kappa,
        'thermal_emission_W_m2': P_rad,
        'wien_peak_m': lam_peak,
        'blackbody_color_rgb': bb_color,
        'visibly_glowing': glowing,
        'origin': (
            "Sound velocity: FIRST_PRINCIPLES (Newton-Laplace √(K/ρ)). "
            "Debye temperature: FIRST_PRINCIPLES (phonon cutoff from v_s and n). "
            "Heat capacity: FIRST_PRINCIPLES (Debye model) + "
            "APPROXIMATION (Padé approximant for Debye integral). "
            "Phonon MFP: FIRST_PRINCIPLES (Umklapp scaling ℓ ∝ Θ_D/T) + "
            "APPROXIMATION (scattering factor calibrated per structure). "
            "Thermal conductivity: FIRST_PRINCIPLES (phonon kinetic theory κ = CvℓL/3). "
            "Thermal radiation: FIRST_PRINCIPLES (Stefan-Boltzmann, Planck's law). "
            "Blackbody color: APPROXIMATION (polynomial fit to CIE 1931 tables). "
            "Contact conductance: FIRST_PRINCIPLES (Fourier's law) + "
            "friction.real_contact_fraction + texture.thermal_roughness."
        ),
    }

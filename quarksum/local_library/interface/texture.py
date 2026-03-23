"""
Surface texture physics from atomic-scale properties.

Derivation chain:
  σ → nuclear mass → cohesive energy → step formation energy → roughness → BRDF

All texture properties are derived from quantities already in the surface module:
  - Lattice parameter (MEASURED)
  - Surface energy γ (FIRST_PRINCIPLES: broken-bond model)
  - Crystal structure (MEASURED)

Texture quantities:

  1. Atomic step height
     h = a / √(h²+k²+l²)  for cubic lattices
     FIRST_PRINCIPLES: interplanar spacing is pure geometry of the lattice.

  2. Step formation energy
     E_step = γ × h  (J/m = energy per unit length of step edge)
     FIRST_PRINCIPLES: creating a step exposes new surface of height h.
     Each meter of step edge creates h m² of new surface per meter of length.

  3. Thermal roughness (equilibrium)
     σ_RMS = h × √(k_B T / E_step_per_atom)
     where E_step_per_atom = E_step × (lattice spacing along step)
     FIRST_PRINCIPLES: Boltzmann statistics on step excitations.
     At equilibrium, step density follows exp(-E/kT).

  4. Grain boundary energy (Read-Shockley model)
     For θ < θ_max:
       γ_gb = γ_gb_max × (θ/θ_max) × (1 - ln(θ/θ_max))
     For θ ≥ θ_max:
       γ_gb = γ_gb_max
     where γ_gb_max ≈ γ_surface / 3  (APPROXIMATION: empirical ratio)
     and θ_max ≈ 15° (APPROXIMATION: transition to high-angle boundary)
     FIRST_PRINCIPLES: dislocation array energy from elastic theory.
     APPROXIMATION: γ_gb_max/γ_surface ratio is empirical.

  5. Microfacet roughness (Beckmann α)
     α = σ_RMS / l_corr
     where l_corr = lattice parameter (correlation length for atomic surfaces)
     Maps thermal roughness to the Beckmann microfacet distribution.
     FIRST_PRINCIPLES: surface slope statistics from roughness/correlation.

  6. Specular fraction (Rayleigh criterion)
     f_spec = exp(-(4π σ_RMS / λ)²)
     Fraction of surface smooth enough for coherent reflection.
     FIRST_PRINCIPLES: wave optics, phase variance from surface height.

σ-dependence:
  σ enters through surface_energy_at_sigma(), which shifts cohesive energy
  via the ZPE pathway. This shifts step formation energy, which shifts
  roughness, which shifts everything downstream.

  The chain: σ → E_coh → γ → E_step → σ_RMS → α, f_spec

Origin tags:
  - Step height: FIRST_PRINCIPLES (lattice geometry)
  - Step energy: FIRST_PRINCIPLES (surface area argument)
  - Thermal roughness: FIRST_PRINCIPLES (Boltzmann statistics on step excitations)
  - Grain boundary: FIRST_PRINCIPLES (Read-Shockley) + APPROXIMATION (γ_gb_max ratio)
  - Microfacet α: FIRST_PRINCIPLES (surface statistics)
  - Specular fraction: FIRST_PRINCIPLES (Rayleigh wave optics)
"""

import math
from .surface import MATERIALS, surface_energy_at_sigma

# ── Constants ─────────────────────────────────────────────────────
_K_BOLTZMANN = 1.380649e-23   # J/K (exact, 2019 SI)
_EV_TO_JOULE = 1.602176634e-19


# ── Miller index sum of squares ───────────────────────────────────
# For interplanar spacing: d = a / √(h² + k² + l²)
# Each preferred face maps to a sum of squared Miller indices.

def _miller_sum_sq(crystal_structure, face):
    """Sum of squared Miller indices for interplanar spacing calculation.

    FIRST_PRINCIPLES: pure geometry of the crystal lattice.
    d_{hkl} = a / √(h² + k² + l²) for cubic lattices.
    For HCP basal plane (0001), d = c ≈ 1.633a for ideal c/a ratio,
    but we use a simpler approximation: d ≈ a × (c/a ratio factor).
    """
    table = {
        ('fcc', '111'): 3,      # 1² + 1² + 1² = 3
        ('fcc', '100'): 1,      # 1² + 0² + 0² = 1
        ('fcc', '110'): 2,      # 1² + 1² + 0² = 2
        ('bcc', '110'): 2,      # 1² + 1² + 0² = 2
        ('bcc', '100'): 1,      # 1² + 0² + 0² = 1
        ('diamond_cubic', '111'): 3,
        ('diamond_cubic', '110'): 2,
        ('hcp', '0001'): None,  # Special case: basal plane
    }
    key = (crystal_structure, face)
    if key not in table:
        raise ValueError(f"Unknown face {face} for {crystal_structure}")
    return table[key]


# ── Atomic step height ────────────────────────────────────────────

def atomic_step_height(material_key):
    """Interplanar spacing for the preferred face (meters).

    FIRST_PRINCIPLES: d_{hkl} = a / √(h² + k² + l²) for cubic lattices.
    For HCP basal plane: d = c ≈ a × √(8/3) / 2 for ideal c/a = √(8/3).

    This is the minimum height of an atomic step on the surface.

    Args:
        material_key: key into MATERIALS dict

    Returns:
        Step height in meters.
    """
    mat = MATERIALS[material_key]
    struct = mat['crystal_structure']
    face = mat['preferred_face']
    a_m = mat['lattice_param_angstrom'] * 1e-10  # Å → m

    msq = _miller_sum_sq(struct, face)

    if msq is None:
        # HCP basal plane: d = c/2, ideal c/a = √(8/3) ≈ 1.633
        # d_0001 = a × √(8/3) / 2 ≈ 0.816 × a
        c_over_a = math.sqrt(8.0 / 3.0)  # ideal HCP
        return a_m * c_over_a / 2.0
    else:
        return a_m / math.sqrt(msq)


# ── Step formation energy ─────────────────────────────────────────

def step_formation_energy(material_key, sigma=0.0):
    """Energy per unit length of step edge (J/m).

    FIRST_PRINCIPLES: A step of height h exposes h m² of new surface
    per meter of step length. Energy cost = γ × h.

    This is exact for an ideal straight step. Real steps have
    reconstruction and relaxation, but this gives the right order.

    Args:
        material_key: key into MATERIALS dict
        sigma: σ-field value

    Returns:
        Step formation energy in J/m (energy per meter of step edge).
    """
    gamma = surface_energy_at_sigma(material_key, sigma)
    h = atomic_step_height(material_key)
    return gamma * h


# ── Thermal roughness ─────────────────────────────────────────────

def thermal_roughness(material_key, T=300.0, sigma=0.0):
    """RMS surface roughness from thermal equilibrium (meters).

    FIRST_PRINCIPLES: Boltzmann statistics on step excitations.

    At temperature T, steps are thermally excited. The probability of
    a step existing at any site is ~ exp(-E_step_atom / kT), where
    E_step_atom is the energy to create one step-atom.

    For a 2D surface, the RMS height fluctuation is:
      σ_RMS = h × √(kT / E_step_atom)

    where E_step_atom = E_step_line × a_step (energy per step atom,
    a_step = lattice spacing along the step direction).

    This gives the EQUILIBRIUM roughness for a clean surface in vacuum.
    Real surfaces may be rougher (growth kinetics, defects) or smoother
    (polishing). This is the thermodynamic lower bound.

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin (must be ≥ 0)
        sigma: σ-field value

    Returns:
        RMS roughness in meters.
    """
    if T <= 0:
        return 0.0

    h = atomic_step_height(material_key)
    E_line = step_formation_energy(material_key, sigma)

    # Step atom spacing: approximately the lattice parameter
    mat = MATERIALS[material_key]
    a_m = mat['lattice_param_angstrom'] * 1e-10

    # Energy to create one step atom: E_line × a
    # (one atom-width of step edge costs E_line × a)
    E_step_atom = E_line * a_m

    # RMS roughness: Boltzmann fluctuations
    # σ_RMS = h × √(kT / E_step_atom)
    ratio = _K_BOLTZMANN * T / E_step_atom
    rms = h * math.sqrt(ratio)

    return rms


# ── Grain boundary energy ─────────────────────────────────────────

def grain_boundary_energy(material_key, theta_deg=15.0, sigma=0.0):
    """Grain boundary energy from Read-Shockley model (J/m²).

    FIRST_PRINCIPLES: A low-angle grain boundary is an array of edge
    dislocations spaced D = b/θ apart, where b is the Burgers vector.
    The energy per dislocation is ~ Gb²/(4π(1-ν)) × ln(D/b).
    Summing over the array gives the Read-Shockley formula:

      γ_gb = γ_max × (θ/θ_max) × (1 - ln(θ/θ_max))   for θ < θ_max
      γ_gb = γ_max                                       for θ ≥ θ_max

    where:
      θ_max ≈ 15° (APPROXIMATION: transition angle, empirical)
      γ_max ≈ γ_surface / 3 (APPROXIMATION: empirical ratio for metals)

    The Read-Shockley derivation is from elastic theory (FIRST_PRINCIPLES).
    The γ_max/γ_surface ratio and θ_max are empirical calibrations.

    Args:
        material_key: key into MATERIALS dict
        theta_deg: misorientation angle in degrees
        sigma: σ-field value

    Returns:
        Grain boundary energy in J/m².
    """
    if theta_deg <= 0:
        return 0.0

    gamma_surface = surface_energy_at_sigma(material_key, sigma)

    # Maximum GB energy: empirical fraction of surface energy
    # Typical metals: γ_gb_max ≈ γ/3 (APPROXIMATION)
    gamma_gb_max = gamma_surface / 3.0

    # Transition angle (APPROXIMATION: ~15° for most metals)
    theta_max = 15.0

    theta = min(theta_deg, 90.0)  # cap at physical maximum

    if theta >= theta_max:
        return gamma_gb_max

    # Read-Shockley formula for low-angle boundaries
    x = theta / theta_max
    # Note: x × (1 - ln(x)) is well-behaved as x→0 (goes to 0)
    if x < 1e-15:
        return 0.0

    return gamma_gb_max * x * (1.0 - math.log(x))


# ── Microfacet roughness ──────────────────────────────────────────

def microfacet_roughness(material_key, T=300.0, sigma=0.0):
    """Beckmann roughness parameter α from surface statistics.

    FIRST_PRINCIPLES: The Beckmann microfacet distribution describes
    the probability distribution of surface normal orientations.
    The roughness parameter α = σ_RMS / l_corr, where:
      σ_RMS: RMS height fluctuation
      l_corr: lateral correlation length

    For an atomically clean surface, the correlation length is set by
    the lattice parameter (atomic-scale correlations). This gives the
    intrinsic roughness — real surfaces may be rougher due to defects,
    grain boundaries, oxide layers, etc.

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Beckmann roughness parameter α (dimensionless, 0 < α < 1 for smooth).
    """
    rms = thermal_roughness(material_key, T, sigma)

    # Correlation length: lattice parameter (atomic-scale)
    mat = MATERIALS[material_key]
    l_corr = mat['lattice_param_angstrom'] * 1e-10

    alpha = rms / l_corr

    # Cap at physical bounds
    return max(0.0, min(alpha, 1.0))


# ── Specular fraction ─────────────────────────────────────────────

def specular_fraction(material_key, T=300.0, wavelength_m=550e-9, sigma=0.0):
    """Fraction of surface area that reflects specularly (Rayleigh criterion).

    FIRST_PRINCIPLES: Wave optics. The phase variance introduced by
    surface roughness destroys coherent (specular) reflection.

    The Debye-Waller factor for surface scattering:
      f_spec = exp(-(4π σ_RMS / λ)²)

    where σ_RMS is the RMS height fluctuation and λ is the wavelength.

    When σ_RMS << λ/(4π), the surface is optically smooth (f → 1).
    When σ_RMS >> λ/(4π), the surface is fully diffuse (f → 0).

    For metals at room temperature:
      σ_RMS ~ 0.1-0.5 Å, λ_visible ~ 5000 Å → f_spec > 0.999
      (atomically clean metal surfaces are excellent mirrors)

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        wavelength_m: wavelength of light in meters
        sigma: σ-field value

    Returns:
        Specular fraction (0 to 1).
    """
    rms = thermal_roughness(material_key, T, sigma)

    # Phase variance parameter
    phase_var = (4.0 * math.pi * rms / wavelength_m) ** 2

    # Debye-Waller factor
    return math.exp(-phase_var)


# ── Nagatha export ────────────────────────────────────────────────

def material_texture_properties(material_key, T=300.0, sigma=0.0):
    """Export texture properties in Nagatha-compatible format.

    Returns a dict that can be merged into Nagatha's material database.

    Args:
        material_key: key into MATERIALS dict
        T: temperature in Kelvin
        sigma: σ-field value

    Returns:
        Dict with all texture properties and origin tags.
    """
    mat = MATERIALS[material_key]
    h = atomic_step_height(material_key)
    E_step = step_formation_energy(material_key, sigma)
    rms = thermal_roughness(material_key, T, sigma)
    gb = grain_boundary_energy(material_key, theta_deg=30.0, sigma=sigma)
    alpha = microfacet_roughness(material_key, T, sigma)
    f_spec = specular_fraction(material_key, T, sigma=sigma)

    return {
        'material': material_key,
        'temperature_K': T,
        'sigma': sigma,
        'crystal_structure': mat['crystal_structure'],
        'step_height_m': h,
        'step_energy_j_m': E_step,
        'thermal_roughness_rms_m': rms,
        'grain_boundary_energy_j_m2': gb,
        'microfacet_alpha': alpha,
        'specular_fraction_visible': f_spec,
        'origin': (
            "Step height: FIRST_PRINCIPLES (interplanar spacing geometry). "
            "Step energy: FIRST_PRINCIPLES (surface area × γ). "
            "Thermal roughness: FIRST_PRINCIPLES (Boltzmann statistics on step excitations). "
            "Grain boundary: FIRST_PRINCIPLES (Read-Shockley dislocation array) + "
            "APPROXIMATION (γ_gb_max/γ_surface ≈ 1/3, θ_max ≈ 15°). "
            "Microfacet α: FIRST_PRINCIPLES (roughness/correlation surface statistics). "
            "Specular fraction: FIRST_PRINCIPLES (Rayleigh wave optics, Debye-Waller factor)."
        ),
    }

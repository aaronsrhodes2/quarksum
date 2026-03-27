"""
Mechanical properties from bond physics.

Derivation chain:
  Cohesive energy (MEASURED) + atomic volume (MEASURED)
  → Bulk modulus K (FIRST_PRINCIPLES: harmonic approximation)
  + Poisson's ratio ν (MEASURED)
  → Young's modulus E = 3K(1−2ν) (FIRST_PRINCIPLES: elasticity identity)
  → Shear modulus G = E/(2(1+ν)) (FIRST_PRINCIPLES: elasticity identity)
  → Theoretical shear strength τ_th = G/(2π) (FIRST_PRINCIPLES: Frenkel 1926)

The bulk modulus estimate:
  K ≈ E_coh × n_atoms × f(structure)

  Where:
    E_coh = cohesive energy per atom (depth of potential well)
    n_atoms = number density (atoms/m³, from density and atomic mass)
    f = geometric factor depending on crystal structure

  This is the harmonic approximation: the curvature of the interatomic
  potential at equilibrium determines bulk stiffness. The geometric
  factor accounts for packing efficiency and coordination.

  Accuracy: ±50% for metals. The approximation captures the right
  physics (stiffer bonds = stiffer material) but misses details of
  the potential shape beyond the well depth. Marked honestly.

Poisson's ratio:
  MEASURED. No first-principles derivation available from our inputs.
  It depends on the directionality of bonding, which requires the
  full electronic structure to compute. We use tabulated values.

Theoretical shear strength (Frenkel):
  τ_th = G/(2π)

  FIRST_PRINCIPLES: energy barrier for one atomic plane sliding over
  the next in a perfect crystal. Real yield strength is 100-1000×
  lower because dislocations provide low-energy pathways. We compute
  theoretical and note the gap.

σ-dependence:
  Flows through cohesive energy, same as surface.py and adhesion.py.
  Nuclear mass correction shifts lattice dynamics → shifts stiffness.

Origin tags:
  - Bulk modulus: FIRST_PRINCIPLES (harmonic approximation, ±50%)
  - Elastic identities: FIRST_PRINCIPLES (exact continuum mechanics)
  - Frenkel strength: FIRST_PRINCIPLES (perfect crystal, upper bound)
  - Poisson's ratio: MEASURED
  - σ-dependence: CORE (through □σ = −ξR)
"""

import math
from .surface import MATERIALS, surface_energy_at_sigma
from ..scale import scale_ratio
from ..constants import PROTON_QCD_FRACTION

# ── Conversion ─────────────────────────────────────────────────────
_EV_TO_JOULE = 1.602176634e-19  # exact (2019 SI)
_AMU_KG = 1.66053906660e-27     # atomic mass unit in kg


# ── Mechanical Data ───────────────────────────────────────────────
# Poisson's ratio: MEASURED from experiment.
# Source: ASM Handbook, CRC Handbook.
#
# Structure factor f: geometric correction for bulk modulus estimate.
# Calibrated to give K within ±50% for each crystal structure.
# FCC close-packed: f ≈ 1.0 (efficient packing, bonds align well)
# BCC: f ≈ 0.85 (less efficient packing)
# Diamond cubic: f ≈ 0.5 (very open structure, 4 bonds)
# HCP: f ≈ 1.0 (close-packed like FCC)

# Structure factor: the ratio K_real / (E_coh × n) for each crystal family.
#
# Why ~3? The bulk modulus depends on the CURVATURE of the interatomic
# potential (d²φ/dr²), not just the DEPTH (E_coh). For metallic bonds,
# the potential is steep and narrow — the curvature is ~3× what the
# depth alone implies. This is a known result from pair-potential theory
# (e.g., Morse potential gives K = 2Dα²/V where α ≈ 1.5/r₀).
#
# We calibrate f per crystal structure, not per material. This captures
# the packing geometry without fitting individual materials.
# Gold is an outlier (relativistic 6s contraction stiffens its bonds
# beyond what non-relativistic E_coh predicts). We accept this.

MECHANICAL_DATA = {
    'iron': {
        'poisson_ratio': 0.29,           # MEASURED
        'structure_factor': 2.9,          # BCC: calibrated to K_Fe ≈ 170 GPa
    },
    'copper': {
        'poisson_ratio': 0.34,           # MEASURED
        'structure_factor': 3.0,          # FCC: calibrated to K_Cu ≈ 140 GPa
    },
    'aluminum': {
        'poisson_ratio': 0.35,           # MEASURED
        'structure_factor': 3.0,          # FCC (same family as Cu)
    },
    'gold': {
        'poisson_ratio': 0.44,           # MEASURED
        'structure_factor': 3.0,          # FCC — underestimates K for gold
                                          # (relativistic effect, documented)
    },
    'silicon': {
        'poisson_ratio': 0.22,           # MEASURED
        'structure_factor': 1.5,          # Diamond cubic: open structure
    },
    'tungsten': {
        'poisson_ratio': 0.28,           # MEASURED
        'structure_factor': 2.9,          # BCC (same family as Fe)
    },
    'nickel': {
        'poisson_ratio': 0.31,           # MEASURED
        'structure_factor': 3.0,          # FCC
    },
    'titanium': {
        'poisson_ratio': 0.32,           # MEASURED
        'structure_factor': 3.0,          # HCP (close-packed, similar to FCC)
    },
}


# ── Atomic Volume ────────────────────────────────────────────────

def _atomic_volume(material_key):
    """Atomic volume V_atom = A × m_u / ρ.

    FIRST_PRINCIPLES: mass per atom / mass per volume.

    Returns volume in m³.
    """
    mat = MATERIALS[material_key]
    return mat['A'] * _AMU_KG / mat['density_kg_m3']


def _number_density(material_key):
    """Number density n = ρ / (A × m_u).

    FIRST_PRINCIPLES: inverse of atomic volume.

    Returns atoms/m³.
    """
    return 1.0 / _atomic_volume(material_key)


# ── Effective Cohesive Energy ────────────────────────────────────

def _effective_cohesive_energy_j(material_key, sigma=0.0):
    """Cohesive energy per atom at given σ, in Joules.

    Same σ-correction as surface.py: QCD mass shift → phonon
    stiffening → tighter binding.
    """
    mat = MATERIALS[material_key]
    e_coh_ev = mat['cohesive_energy_ev']

    if sigma == 0.0:
        return e_coh_ev * _EV_TO_JOULE

    f_qcd_mass = PROTON_QCD_FRACTION
    mass_ratio = (1.0 - f_qcd_mass) + f_qcd_mass * scale_ratio(sigma)

    f_zpe = 0.01
    zpe_correction = f_zpe * e_coh_ev * (1.0 - 1.0 / math.sqrt(mass_ratio))
    e_coh_effective = e_coh_ev + zpe_correction

    return e_coh_effective * _EV_TO_JOULE


# ── Bulk Modulus ─────────────────────────────────────────────────

def bulk_modulus(material_key, sigma=0.0):
    """Bulk modulus K (Pa) from cohesive energy and atomic volume.

    K = E_coh × n_atoms × f(structure)

    FIRST_PRINCIPLES: harmonic approximation of interatomic potential.
    The cohesive energy (well depth) × number density gives an energy
    density. The structure factor corrects for packing geometry.

    Accuracy: ±50% for metals. Honest about this.

    Args:
        material_key: key into MATERIALS dict
        sigma: σ-field value

    Returns:
        K in Pascals
    """
    E_coh_j = _effective_cohesive_energy_j(material_key, sigma)
    n = _number_density(material_key)
    f = MECHANICAL_DATA[material_key]['structure_factor']

    return E_coh_j * n * f


def bulk_modulus_at_sigma(material_key, sigma=0.0):
    """Bulk modulus at arbitrary σ. Explicit sigma signature."""
    return bulk_modulus(material_key, sigma=sigma)


# ── Young's Modulus ──────────────────────────────────────────────

def youngs_modulus(material_key, sigma=0.0):
    """Young's modulus E (Pa) from bulk modulus and Poisson's ratio.

    E = 3K(1 − 2ν)

    FIRST_PRINCIPLES: isotropic elasticity identity. Exact.
    ν is MEASURED.

    Args:
        material_key: key into MATERIALS dict
        sigma: σ-field value

    Returns:
        E in Pascals
    """
    K = bulk_modulus(material_key, sigma)
    nu = MECHANICAL_DATA[material_key]['poisson_ratio']
    return 3.0 * K * (1.0 - 2.0 * nu)


# ── Shear Modulus ────────────────────────────────────────────────

def shear_modulus(material_key, sigma=0.0):
    """Shear modulus G (Pa) from Young's modulus and Poisson's ratio.

    G = E / (2(1 + ν))

    FIRST_PRINCIPLES: isotropic elasticity identity. Exact.

    Args:
        material_key: key into MATERIALS dict
        sigma: σ-field value

    Returns:
        G in Pascals
    """
    E = youngs_modulus(material_key, sigma)
    nu = MECHANICAL_DATA[material_key]['poisson_ratio']
    return E / (2.0 * (1.0 + nu))


# ── Theoretical Shear Strength ───────────────────────────────────

def theoretical_shear_strength(material_key, sigma=0.0):
    """Frenkel theoretical shear strength τ_th (Pa).

    τ_th = G / (2π)

    FIRST_PRINCIPLES: energy barrier for one atomic plane sliding
    over the next in a perfect crystal. Assumes sinusoidal potential
    landscape between atomic rows.

    Real yield is 100-1000× lower due to dislocation motion.
    This is an UPPER BOUND on strength, not a prediction of real yield.

    Args:
        material_key: key into MATERIALS dict
        sigma: σ-field value

    Returns:
        τ_th in Pascals
    """
    G = shear_modulus(material_key, sigma)
    return G / (2.0 * math.pi)


# ── Nagatha Integration ──────────────────────────────────────────

def material_mechanical_properties(material_key, sigma=0.0):
    """Export mechanical properties in Nagatha-compatible format.

    Returns a dict that can be merged into Nagatha's color.json materials.
    """
    K = bulk_modulus(material_key, sigma)
    E = youngs_modulus(material_key, sigma)
    G = shear_modulus(material_key, sigma)
    nu = MECHANICAL_DATA[material_key]['poisson_ratio']
    tau = theoretical_shear_strength(material_key, sigma)

    return {
        'bulk_modulus_pa': K,
        'youngs_modulus_pa': E,
        'shear_modulus_pa': G,
        'poisson_ratio': nu,
        'theoretical_shear_strength_pa': tau,
        'sigma': sigma,
        'origin_tag': (
            "FIRST_PRINCIPLES: bulk modulus from harmonic approximation "
            "of interatomic potential (±50% accuracy). "
            "FIRST_PRINCIPLES: E, G from isotropic elasticity identities (exact). "
            "FIRST_PRINCIPLES: Frenkel theoretical strength G/(2π) (upper bound). "
            "MEASURED: Poisson's ratio (tabulated per material). "
            "CORE: σ-dependence through nuclear mass correction."
        ),
    }

"""
Adhesion — interface binding between two materials.

When surface A touches surface B, three energies matter:
  γ_A: surface energy of A (energy to create a free A surface)
  γ_B: surface energy of B (energy to create a free B surface)
  γ_AB: interface energy (energy cost of the A-B boundary)

Work of adhesion (Dupré, 1869):
  W_AB = γ_A + γ_B − γ_AB

  FIRST_PRINCIPLES: thermodynamic energy balance.
  You had two free surfaces (cost γ_A + γ_B to create).
  Now they're in contact, forming an interface (cost γ_AB).
  Energy released = what you had − what you're left with.

Interface energy (Berthelot combining rule):
  γ_AB = γ_A + γ_B − 2√(γ_A × γ_B)

  APPROXIMATION: assumes cross-material bond energy is the
  geometric mean of same-material bond energies. This works
  well for similar metals, poorly for metal-ceramic or
  metal-polymer interfaces. We mark this honestly.

  Why geometric mean? If atom A has bond strength ε_A and atom B
  has ε_B, the cross-bond is ε_AB ≈ √(ε_A × ε_B). This is the
  Berthelot hypothesis — it says mixing follows a geometric mean
  rather than arithmetic or harmonic. It's not derived from
  first principles, but it has the right limiting behavior:
    - When A = B: γ_AB = 0 (correct: no interface)
    - When A ≠ B: γ_AB > 0 (correct: mismatched bonds cost energy)
    - More dissimilar → higher γ_AB (correct)

Contact angle (Young, 1805):
  cos θ = (γ_SV − γ_SL) / γ_LV

  FIRST_PRINCIPLES: force balance at the triple line where solid,
  liquid, and vapor meet. Three surface tension vectors pull on the
  contact line; equilibrium gives Young's equation.

  Combined with Dupré: cos θ = W_SL / γ_LV − 1
  (Young-Dupré equation)

σ-dependence:
  Inherited from surface.py. Both γ_A(σ) and γ_B(σ) carry QCD
  mass corrections, so W_AB(σ) and γ_AB(σ) shift accordingly.
  At Earth: negligible. At neutron stars: measurable.

Origin tags:
  - Dupré equation: FIRST_PRINCIPLES (energy balance)
  - Berthelot rule: APPROXIMATION (geometric mean combining)
  - Young's equation: FIRST_PRINCIPLES (force balance)
  - σ-dependence: CORE (through surface.py)
"""

import math
from .surface import (
    surface_energy, surface_energy_at_sigma,
    surface_energy_decomposition, MATERIALS,
)


# ── Interface Energy ──────────────────────────────────────────────

def interface_energy(material_1, material_2, sigma=0.0):
    """Interface energy γ₁₂ (J/m²) using Berthelot combining rule.

    γ₁₂ = γ₁ + γ₂ − 2√(γ₁ × γ₂)

    APPROXIMATION: geometric mean of cross-bond energies.

    Args:
        material_1: key into MATERIALS dict
        material_2: key into MATERIALS dict
        sigma: σ-field value (default 0)

    Returns:
        γ₁₂ in J/m²
    """
    g1 = surface_energy_at_sigma(material_1, sigma)
    g2 = surface_energy_at_sigma(material_2, sigma)

    # Berthelot: γ₁₂ = (√γ₁ − √γ₂)²
    # Equivalent to γ₁ + γ₂ − 2√(γ₁γ₂), but this form
    # makes it obvious that γ₁₂ ≥ 0 always.
    gamma_12 = (math.sqrt(g1) - math.sqrt(g2)) ** 2

    return gamma_12


# ── Work of Adhesion ──────────────────────────────────────────────

def work_of_adhesion(material_1, material_2, sigma=0.0):
    """Work of adhesion W₁₂ (J/m²) from Dupré equation.

    W₁₂ = γ₁ + γ₂ − γ₁₂

    FIRST_PRINCIPLES: thermodynamic energy balance.

    With Berthelot interface energy:
      W₁₂ = 2√(γ₁ × γ₂)

    For self-adhesion (material_1 = material_2):
      W_AA = 2γ_A (work of cohesion)

    Args:
        material_1: key into MATERIALS dict
        material_2: key into MATERIALS dict
        sigma: σ-field value (default 0)

    Returns:
        W₁₂ in J/m²
    """
    g1 = surface_energy_at_sigma(material_1, sigma)
    g2 = surface_energy_at_sigma(material_2, sigma)

    # Dupré with Berthelot: W = γ₁ + γ₂ − (√γ₁ − √γ₂)²
    #                        = 2√(γ₁γ₂)
    return 2.0 * math.sqrt(g1 * g2)


def work_of_adhesion_at_sigma(material_1, material_2, sigma=0.0):
    """Work of adhesion at arbitrary σ. Explicit sigma signature."""
    return work_of_adhesion(material_1, material_2, sigma=sigma)


# ── Decomposition ────────────────────────────────────────────────

def adhesion_decomposition(material_1, material_2, sigma=0.0):
    """Decompose work of adhesion into EM and QCD components.

    The decomposition inherits from surface energy decomposition:
      W₁₂ = 2√(γ₁ × γ₂)
      γ_i = γ_i_EM + γ_i_QCD

    We compute W at σ and at σ=0, and decompose:
      W_EM = contribution from EM-invariant parts of both γ
      W_QCD = total − W_EM

    Returns dict with em_component_j_m2, qcd_component_j_m2, total_j_m2.
    """
    # Total at this sigma
    W_total = work_of_adhesion(material_1, material_2, sigma=sigma)

    # EM-only: use surface energies with only EM component
    d1 = surface_energy_decomposition(material_1, sigma)
    d2 = surface_energy_decomposition(material_2, sigma)

    g1_em = d1['em_component_j_m2']
    g2_em = d2['em_component_j_m2']

    # W_EM = 2√(γ₁_EM × γ₂_EM)
    W_em = 2.0 * math.sqrt(g1_em * g2_em)

    return {
        'em_component_j_m2': W_em,
        'qcd_component_j_m2': W_total - W_em,
        'total_j_m2': W_total,
        'sigma': sigma,
    }


# ── Contact Angle ────────────────────────────────────────────────

def contact_angle(solid_material, liquid_material, gamma_lv,
                  sigma=0.0):
    """Contact angle θ (degrees) from Young-Dupré equation.

    cos θ = W_SL / γ_LV − 1

    FIRST_PRINCIPLES: force balance at triple line.

    Args:
        solid_material: key into MATERIALS dict (the substrate)
        liquid_material: key into MATERIALS dict (the liquid)
        gamma_lv: liquid-vapor surface tension (J/m²) — MEASURED
        sigma: σ-field value

    Returns:
        θ in degrees (0 = complete wetting, 180 = complete non-wetting)
        Returns 0 if cos θ ≥ 1 (complete wetting/spreading)
        Returns 180 if cos θ ≤ −1 (complete non-wetting)
        Returns None if gamma_lv ≤ 0 (undefined)
    """
    if gamma_lv <= 0:
        return None

    W = work_of_adhesion(solid_material, liquid_material, sigma=sigma)
    cos_theta = W / gamma_lv - 1.0

    # Clamp to physical range
    if cos_theta >= 1.0:
        return 0    # complete wetting (spreading)
    elif cos_theta <= -1.0:
        return 180  # complete non-wetting (beading)
    else:
        return math.degrees(math.acos(cos_theta))


# ── Nagatha Integration ──────────────────────────────────────────

def material_adhesion_properties(material_1, material_2, sigma=0.0):
    """Export adhesion properties in Nagatha-compatible format.

    Returns a dict that can be merged into Nagatha's color.json.
    """
    W = work_of_adhesion(material_1, material_2, sigma=sigma)
    gamma_12 = interface_energy(material_1, material_2, sigma=sigma)
    dec = adhesion_decomposition(material_1, material_2, sigma=sigma)

    return {
        'work_of_adhesion_j_m2': W,
        'interface_energy_j_m2': gamma_12,
        'material_1': material_1,
        'material_2': material_2,
        'sigma': sigma,
        'em_fraction': dec['em_component_j_m2'] / dec['total_j_m2']
                       if dec['total_j_m2'] > 0 else 0,
        'origin_tag': (
            "FIRST_PRINCIPLES: Dupré equation (energy balance). "
            "APPROXIMATION: Berthelot combining rule (geometric mean "
            "of cross-bond energies — works well for similar metals, "
            "underestimates for dissimilar pairs). "
            "CORE: σ-dependence through nuclear mass correction."
        ),
    }

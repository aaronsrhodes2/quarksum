"""
The Scale Field σ — the single new ingredient.

σ is a dimensionless scalar field. Where spacetime is flat, σ = 0
and all physics is standard. Where spacetime curves, σ grows and
the strong force shifts.

The field equation (hypothesis): □σ = −ξR
"""

import math
from .constants import XI, LAMBDA_QCD_MEV, G, C


def scale_ratio(sigma):
    """e^σ — the fundamental scaling factor.

    At σ = 0: returns 1.0 (standard physics).
    At σ > 0: QCD gets stronger, nucleons get heavier.
    """
    return math.exp(sigma)


def lambda_eff(sigma):
    """Effective QCD scale at a given σ value.

    Λ_eff = Λ_QCD × e^σ

    Returns MeV.
    """
    return LAMBDA_QCD_MEV * scale_ratio(sigma)


def sigma_from_potential(r_m, M_kg):
    """Compute σ from Newtonian gravitational potential.

    σ = ξ × GM/(rc²)

    This is the macroscopic, smooth prescription.
    At Earth's surface: σ ≈ 7×10⁻¹⁰ (negligible).
    At Schwarzschild radius: σ ≈ ξ/2 ≈ 0.079.

    Args:
        r_m: radius in meters
        M_kg: mass in kg

    Returns:
        σ (dimensionless)
    """
    if r_m <= 0:
        return float('inf')
    return XI * G * M_kg / (r_m * C**2)


def schwarzschild_radius(M_kg):
    """Schwarzschild radius: r_s = 2GM/c²

    Args:
        M_kg: mass in kg

    Returns:
        radius in meters
    """
    return 2 * G * M_kg / C**2


def sigma_at_event_horizon(M_kg):
    """σ at the Schwarzschild radius of a black hole.

    Always returns ξ/2 ≈ 0.079 — independent of mass!
    (This is a consequence of σ = ξGM/rc² with r = 2GM/c².)
    """
    return XI / 2


def sigma_of_R(R_curvature):
    """σ(R) = −ξ R — the canonical field equation.

    This is the single source of truth. The σ field at any point
    is determined by the Ricci scalar curvature R at that point,
    coupled through ξ.

    The box equation □σ = −ξR gives the static solution σ = −ξR
    in the weak-field / slowly-varying limit. Everything else in
    the framework — binding energies, entanglement coupling,
    rendering — derives from this.

    Args:
        R_curvature: Ricci scalar curvature (1/m²)
                     Positive for matter-dominated regions.
                     For a Schwarzschild exterior: R = 0 (vacuum).
                     For interior/cosmological: R = 8πG/c⁴ × (ρc² − 3P).

    Returns:
        σ (dimensionless)
    """
    return -XI * R_curvature


def sigma_conversion():
    """The critical σ where nuclear bonds fail.

    σ_conv = −ln(ξ) ≈ 1.849

    At this point, Λ_eff has grown enough that the QCD binding
    overwhelms nuclear structure and matter disassembles.
    """
    return -math.log(XI)

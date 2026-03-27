"""
Nuclear binding energy at arbitrary σ.

Binding energy decomposes into two channels:
  - Strong contributions (QCD-dependent): SCALE with e^σ
  - Coulomb contribution (electromagnetic): INVARIANT

The Coulomb energy is derived from first-principles electrostatics:
  E_C = (3/5) × e²/(4πε₀r₀) × Z(Z-1) / A^(1/3)

This is the self-energy of Z protons uniformly distributed in a sphere
of radius R = r₀ × A^(1/3). Pure Coulomb's law, no empirical fits.

Inputs: e (elementary charge), ε₀ (vacuum permittivity), r₀ (nuclear
charge radius from electron scattering). All measured.
"""

from .constants import A_C_MEV
from .scale import scale_ratio


def coulomb_energy_mev(Z, A):
    """Coulomb (EM) contribution to binding energy.

    First-principles electrostatics:
      E_C = (3/5) × ke_e² / (r₀ × A^(1/3)) × Z(Z-1)
          = a_C × Z(Z-1) / A^(1/3)

    where a_C = (3/5) × e²/(4πε₀ r₀) is derived from
    Coulomb's law and the measured nuclear charge radius.

    This is σ-INVARIANT because electromagnetism doesn't care about Λ_QCD.
    """
    if A <= 0 or Z <= 1:
        return 0.0
    return A_C_MEV * Z * (Z - 1) / (A ** (1.0 / 3.0))


def binding_energy_mev(be_total_mev, Z, A, sigma=0.0):
    """Binding energy at arbitrary σ.

    Decomposes: BE(σ) = BE_strong × e^σ − BE_Coulomb
    Where: BE_strong = BE_total(σ=0) + BE_Coulomb (at σ=0)

    Args:
        be_total_mev: total binding energy at σ=0 (from AME tables)
        Z: proton number
        A: mass number (Z + N)
        sigma: scale field value

    Returns:
        binding energy in MeV at given σ
    """
    e_coul = coulomb_energy_mev(Z, A)
    be_strong = be_total_mev + e_coul  # strong part at σ=0
    return be_strong * scale_ratio(sigma) - e_coul


def binding_decomposition(be_total_mev, Z, A, sigma=0.0):
    """Show strong vs EM decomposition at given σ."""
    e_sig = scale_ratio(sigma)
    e_coul = coulomb_energy_mev(Z, A)
    be_strong_0 = be_total_mev + e_coul

    return {
        'Z': Z, 'A': A, 'sigma': sigma,
        'coulomb_mev': e_coul,
        'strong_at_0_mev': be_strong_0,
        'strong_at_sigma_mev': be_strong_0 * e_sig,
        'total_at_sigma_mev': be_strong_0 * e_sig - e_coul,
    }

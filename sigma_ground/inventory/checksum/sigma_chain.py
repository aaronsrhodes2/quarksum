"""σ-aware mass decomposition chain.

Reweights QuarkSum's existing mass decomposition at arbitrary σ,
then verifies three-measure closure:

    stable_mass ≈ constituent_mass − binding_energy / c²

Every QCD-dependent mass term scales with e^σ.
Every Higgs/EM term is σ-invariant.

This module provides the bridge between QuarkSum's static mass
accounting and the SSBM variable-σ physics.

No Materia dependency.  Pure physics, pure math.
"""

from __future__ import annotations

from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.core.sigma import (
    scale_ratio,
    proton_mass_kg,
    proton_mass_mev,
    neutron_mass_kg,
    neutron_mass_mev,
    nuclear_binding_mev,
    three_measures_nucleus,
    three_measures_atom,
)


# ── Single-nucleus σ checksum ──────────────────────────────────────────

def sigma_checksum_nucleus(
    Z: int,
    N: int,
    be_mev: float,
    sigma: float,
) -> dict:
    """Full σ-aware mass checksum for a bare nucleus.

    Decomposes nuclear mass into:
      - Higgs mass (bare quarks, σ-invariant)
      - QCD mass (binding dressing, scales with e^σ)
      - Nuclear binding energy (strong part scales, Coulomb invariant)

    Verifies three-measure identity at the given σ.

    Args:
        Z: Proton count.
        N: Neutron count.
        be_mev: Nuclear binding energy at σ=0 (MeV).
        sigma: Scale field value.

    Returns:
        Dict with full decomposition, three measures, and identity check.
    """
    A = Z + N
    c2 = CONSTANTS.c_squared

    # ── Three independent measures at σ ──
    measures = three_measures_nucleus(Z, N, be_mev, sigma)

    # ── Higgs mass: bare quark masses, σ-invariant ──
    # Proton bare = 2×m_u + m_d, Neutron bare = m_u + 2×m_d
    proton_bare_mev = 2 * CONSTANTS.m_up_mev + CONSTANTS.m_down_mev
    neutron_bare_mev = CONSTANTS.m_up_mev + 2 * CONSTANTS.m_down_mev
    higgs_mass_mev = Z * proton_bare_mev + N * neutron_bare_mev
    mev_to_kg = CONSTANTS.e * 1e6 / c2
    higgs_mass_kg = higgs_mass_mev * mev_to_kg

    # ── QCD mass: everything that scales with e^σ ──
    # QCD per proton = m_p(σ) − bare_p, QCD per neutron = m_n(σ) − bare_n
    proton_qcd_mev = proton_mass_mev(sigma) - proton_bare_mev
    neutron_qcd_mev = neutron_mass_mev(sigma) - neutron_bare_mev
    qcd_mass_mev = Z * proton_qcd_mev + N * neutron_qcd_mev
    qcd_mass_kg = qcd_mass_mev * mev_to_kg

    # ── Mass fractions ──
    total_constituent_mev = Z * proton_mass_mev(sigma) + N * neutron_mass_mev(sigma)
    qcd_fraction = qcd_mass_mev / total_constituent_mev if total_constituent_mev > 0 else 0.0
    higgs_fraction = higgs_mass_mev / total_constituent_mev if total_constituent_mev > 0 else 0.0

    return {
        **measures,
        # Decomposition
        "higgs_mass_kg": higgs_mass_kg,
        "higgs_mass_mev": higgs_mass_mev,
        "qcd_mass_kg": qcd_mass_kg,
        "qcd_mass_mev": qcd_mass_mev,
        "qcd_mass_fraction": qcd_fraction,
        "higgs_mass_fraction": higgs_fraction,
    }


def sigma_checksum_atom(
    Z: int,
    N: int,
    be_mev: float,
    sigma: float,
) -> dict:
    """Full σ-aware mass checksum for an atom (nucleus + electrons).

    Electrons are σ-invariant (Higgs/EM mass).
    """
    nuc = sigma_checksum_nucleus(Z, N, be_mev, sigma)
    atom = three_measures_atom(Z, N, be_mev, sigma)

    return {
        **nuc,
        "electron_mass_kg": atom["electron_mass_kg"],
        "atom_stable_mass_kg": atom["atom_stable_mass_kg"],
        "atom_constituent_mass_kg": atom["atom_constituent_mass_kg"],
    }


# ── σ-sweep ────────────────────────────────────────────────────────────

def sigma_sweep(
    Z: int,
    N: int,
    be_mev: float,
    sigma_values: list[float],
) -> list[dict]:
    """Run sigma_checksum_nucleus across a range of σ values.

    Returns a list of checksum dicts, one per σ.
    """
    return [
        sigma_checksum_nucleus(Z, N, be_mev, sigma)
        for sigma in sigma_values
    ]

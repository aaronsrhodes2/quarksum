"""
Nucleon mass at arbitrary σ.

The key insight: 99% of nucleon mass is QCD energy, not Higgs mass.
Shifting Λ_QCD shifts that 99%.

    m_p(σ) = 8.99 MeV (bare, Higgs) + 929.28 MeV (QCD) × e^σ
    m_n(σ) = 11.50 MeV (bare, Higgs) + 928.07 MeV (QCD) × e^σ
"""

from .constants import (
    PROTON_BARE_MEV, PROTON_QCD_MEV,
    NEUTRON_BARE_MEV, NEUTRON_QCD_MEV,
    M_ELECTRON_MEV,
)
from .scale import scale_ratio


def proton_mass_mev(sigma=0.0):
    """Proton mass in MeV at given σ.

    Bare quark mass (Higgs): invariant.
    QCD binding: scales by e^σ.
    """
    return PROTON_BARE_MEV + PROTON_QCD_MEV * scale_ratio(sigma)


def neutron_mass_mev(sigma=0.0):
    """Neutron mass in MeV at given σ.

    Bare quark mass (Higgs): invariant.
    QCD binding: scales by e^σ.
    """
    return NEUTRON_BARE_MEV + NEUTRON_QCD_MEV * scale_ratio(sigma)


def nucleon_decomposition(sigma=0.0):
    """Show the Higgs vs QCD decomposition at a given σ.

    Returns dict with proton and neutron breakdowns.
    """
    e_sig = scale_ratio(sigma)
    return {
        'sigma': sigma,
        'e_sigma': e_sig,
        'proton': {
            'bare_mev': PROTON_BARE_MEV,
            'qcd_mev': PROTON_QCD_MEV * e_sig,
            'total_mev': proton_mass_mev(sigma),
            'qcd_fraction': (PROTON_QCD_MEV * e_sig) / proton_mass_mev(sigma),
        },
        'neutron': {
            'bare_mev': NEUTRON_BARE_MEV,
            'qcd_mev': NEUTRON_QCD_MEV * e_sig,
            'total_mev': neutron_mass_mev(sigma),
            'qcd_fraction': (NEUTRON_QCD_MEV * e_sig) / neutron_mass_mev(sigma),
        },
        'electron_mev': M_ELECTRON_MEV,  # Always invariant
    }

"""
local_library — Scale-Shifted Baryonic Matter core physics.

    □σ = −ξR
    "Box sigma equals minus xi R"

Fast path: constants, scale, nucleon masses, binding energies.
Heavy modules (Universe, verify, audit, Sandbox, entanglement, bounds)
are available but must be imported explicitly — they are NOT loaded here.

    from sigma_ground.field.constants import HBAR, C, E_CHARGE
    from sigma_ground.field.nucleon import neutron_mass_mev
    from sigma_ground.field.universe import Universe          # explicit, on demand
    from sigma_ground.field.entanglement import eta_scan     # explicit, on demand
"""

from .constants import (
    XI, LAMBDA_QCD_MEV, GAMMA, ETA,
    HBAR, C, G, E_CHARGE,
    L_PLANCK, M_PLANCK_KG,
    PROTON_TOTAL_MEV, NEUTRON_TOTAL_MEV,
    M_ELECTRON_MEV,
)
from .scale import scale_ratio, lambda_eff, sigma_from_potential, sigma_conversion
from .nucleon import proton_mass_mev, neutron_mass_mev, nucleon_decomposition
from .binding import binding_energy_mev, binding_decomposition

__version__ = "0.4.0"
__all__ = [
    # SSBM parameters
    'XI', 'LAMBDA_QCD_MEV', 'GAMMA', 'ETA',
    # Physical constants
    'HBAR', 'C', 'G', 'E_CHARGE', 'L_PLANCK', 'M_PLANCK_KG',
    'PROTON_TOTAL_MEV', 'NEUTRON_TOTAL_MEV', 'M_ELECTRON_MEV',
    # Scale
    'scale_ratio', 'lambda_eff', 'sigma_from_potential', 'sigma_conversion',
    # Nucleon
    'proton_mass_mev', 'neutron_mass_mev', 'nucleon_decomposition',
    # Binding
    'binding_energy_mev', 'binding_decomposition',
]

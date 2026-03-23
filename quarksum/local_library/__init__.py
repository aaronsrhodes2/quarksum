"""
local_library — A lightweight proof-of-concept for Scale-Shifted Baryonic Matter.

    □σ = −ξR
    "Box sigma equals minus xi R"

Load a universe. Navigate to any scale. Check any prediction.

    from local_library import Universe
    u = Universe()
    u.at_scale('vacuum')              # our lab: σ = 0, standard physics
    u.at_scale('neutron_star')        # slight QCD shift
    u.at_scale('conversion')          # bonds fail, matter converts
    u.atom(26, 56, sigma=0.5)         # iron-56 at σ = 0.5
    u.black_hole('M87*')              # M87* with SSBM properties
    u.nesting_level(0)                # our universe (Hubble mass)
    u.nesting_level(77)               # Planck scale

Zero dependencies. ~300 lines. 2,020 operations. Under 1 ms.
"""

from .constants import XI, LAMBDA_QCD_MEV, GAMMA, ETA
from .scale import scale_ratio, lambda_eff, sigma_from_potential, sigma_conversion
from .nucleon import proton_mass_mev, neutron_mass_mev, nucleon_decomposition
from .binding import binding_energy_mev, binding_decomposition
from .nesting import level_properties, full_hierarchy, funnel_invariance
from .verify import three_measures, verify_all, verify_summary
from .universe import Universe, ENVIRONMENTS, KNOWN_BLACK_HOLES
from .entanglement import (
    entanglement_bounds, dark_energy_with_eta, sigma_coherence,
    decoherence_at_horizon, eta_scan, find_eta_from_dark_energy,
    rendering_connectivity, local_eta, disturbance_propagation,
    rendering_cost, cosmic_rendering_budget, rendering_environments,
    print_rendering_report,
    photon_rendering_event, photon_rendering_spectrum, print_photon_rendering,
    decoherence_time, decoherence_environments,
)
from .bounds import (
    Safety, check_sigma, check_eta, check_nucleon_mass,
    check_nesting_level, check_binding_energy, check_radius,
    safe_sigma, safe_proton_mass, safe_neutron_mass, safe_binding,
    clamp_sigma, clamp_eta, domain_map, run_boundary_tests,
)
from .audit import build_audit, print_audit, eject_candidates
from .shape_budget import shape_budget, shape_budget_for_body, print_budget_table
from .sandbox import Sandbox

__version__ = "0.4.0"
__all__ = [
    'Universe',
    'XI', 'LAMBDA_QCD_MEV', 'GAMMA',
    'scale_ratio', 'lambda_eff', 'sigma_from_potential', 'sigma_conversion',
    'proton_mass_mev', 'neutron_mass_mev', 'nucleon_decomposition',
    'binding_energy_mev', 'binding_decomposition',
    'level_properties', 'full_hierarchy', 'funnel_invariance',
    'three_measures', 'verify_all', 'verify_summary',
    'ENVIRONMENTS', 'KNOWN_BLACK_HOLES',
    'ETA',
    'entanglement_bounds', 'dark_energy_with_eta', 'sigma_coherence',
    'decoherence_at_horizon', 'eta_scan', 'find_eta_from_dark_energy',
    'rendering_connectivity', 'local_eta', 'disturbance_propagation',
    'rendering_cost', 'cosmic_rendering_budget', 'rendering_environments',
    'print_rendering_report',
    'photon_rendering_event', 'photon_rendering_spectrum', 'print_photon_rendering',
    'decoherence_time', 'decoherence_environments',
    # bounds & safety
    'Safety', 'check_sigma', 'check_eta', 'check_nucleon_mass',
    'check_nesting_level', 'check_binding_energy', 'check_radius',
    'safe_sigma', 'safe_proton_mass', 'safe_neutron_mass', 'safe_binding',
    'clamp_sigma', 'clamp_eta', 'domain_map', 'run_boundary_tests',
    # audit
    'build_audit', 'print_audit', 'eject_candidates',
    # shape budget
    'shape_budget', 'shape_budget_for_body', 'print_budget_table',
    # sandbox
    'Sandbox',
]

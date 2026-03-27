"""
Universe — Load our universe and navigate to any scale.

This is the "standard load": start with observed cosmological parameters,
and query any scale from Hubble mass down to individual atoms.

    from local_library import Universe
    u = Universe()                    # loads our universe
    u.at_scale('earth_surface')       # σ ≈ 7e-10, standard physics
    u.at_scale('neutron_star')        # σ ≈ 0.01, slight QCD shift
    u.at_scale('black_hole_horizon')  # σ ≈ 0.079
    u.at_radius(r_meters, M_kg)      # arbitrary point in spacetime
    u.atom('Fe', 56, sigma=0.5)      # iron-56 at σ=0.5
    u.nesting_level(0)               # Hubble-scale (our universe)
    u.nesting_level(77)              # Planck-scale
"""

import math
from .constants import (
    XI, LAMBDA_QCD_MEV, G, C, M_SUN_KG,
    M_HUBBLE_KG, M_PLANCK_KG,
    PROTON_TOTAL_MEV, NEUTRON_TOTAL_MEV,
    PROTON_QCD_FRACTION, NEUTRON_QCD_FRACTION,
)
from .scale import (
    scale_ratio, lambda_eff, sigma_from_potential,
    schwarzschild_radius, sigma_conversion,
)
from .nucleon import proton_mass_mev, neutron_mass_mev, nucleon_decomposition
from .binding import binding_energy_mev, binding_decomposition, coulomb_energy_mev
from .nesting import level_properties, level_count, full_hierarchy, funnel_invariance
from .verify import three_measures, KNOWN_NUCLEI, verify_summary


# ── Known environments ────────────────────────────────────────────────
ENVIRONMENTS = {
    'vacuum':              {'sigma': 0.0,    'desc': 'Flat spacetime (our lab)'},
    'earth_surface':       {'sigma': 6.95e-10, 'desc': 'Earth surface (negligible)'},
    'sun_surface':         {'sigma': 2.12e-6, 'desc': 'Solar surface'},
    'white_dwarf':         {'sigma': 2.3e-4,  'desc': 'White dwarf surface'},
    'neutron_star':        {'sigma': 0.011,   'desc': 'Neutron star surface'},
    'neutron_star_core':   {'sigma': 0.05,    'desc': 'Neutron star core'},
    'black_hole_horizon':  {'sigma': XI / 2,  'desc': 'Schwarzschild event horizon'},
    'conversion':          {'sigma': -math.log(XI), 'desc': 'Bond failure / matter conversion'},
}

# ── Known astrophysical black holes ───────────────────────────────────
KNOWN_BLACK_HOLES = {
    'V404_Cygni':    {'mass_solar': 9,      'type': 'stellar'},
    'Cygnus_X1':     {'mass_solar': 21,     'type': 'stellar'},
    'GW150914':      {'mass_solar': 62,     'type': 'merger remnant'},
    'M87*':          {'mass_solar': 6.5e9,  'type': 'supermassive'},
    'Sgr_A*':        {'mass_solar': 4e6,    'type': 'supermassive'},
    'NGC_4889':      {'mass_solar': 2.1e10, 'type': 'supermassive'},
    'TON_618':       {'mass_solar': 6.6e10, 'type': 'supermassive'},
    'Phoenix_A':     {'mass_solar': 1e11,   'type': 'supermassive'},
}


class Universe:
    """A navigable model of our universe under SSBM.

    Load it, pick a scale, get predictions.
    """

    def __init__(self):
        self.xi = XI
        self.lambda_qcd = LAMBDA_QCD_MEV
        self.n_levels = level_count()
        self.m_hubble = M_HUBBLE_KG
        self.m_planck = M_PLANCK_KG
        self.sigma_conv = sigma_conversion()

    def __repr__(self):
        return (
            f"Universe(ξ={self.xi:.4f}, Λ_QCD={self.lambda_qcd} MeV, "
            f"levels={self.n_levels}, σ_conv={self.sigma_conv:.4f})"
        )

    # ── Navigate by environment name ──────────────────────────────────

    def at_scale(self, env_name):
        """Get physics at a named environment.

        Available: vacuum, earth_surface, sun_surface, white_dwarf,
                   neutron_star, neutron_star_core, black_hole_horizon,
                   conversion
        """
        if env_name not in ENVIRONMENTS:
            available = ', '.join(ENVIRONMENTS.keys())
            raise ValueError(f"Unknown environment '{env_name}'. Available: {available}")

        env = ENVIRONMENTS[env_name]
        sigma = env['sigma']
        return self._physics_at(sigma, label=f"{env_name}: {env['desc']}")

    # ── Navigate by radius and mass ───────────────────────────────────

    def at_radius(self, r_m, M_kg):
        """Get physics at radius r from mass M.

        Args:
            r_m: distance from center in meters
            M_kg: central mass in kg
        """
        sigma = sigma_from_potential(r_m, M_kg)
        label = f"r={r_m:.2e} m, M={M_kg:.2e} kg"
        return self._physics_at(sigma, label=label)

    # ── Navigate by sigma directly ────────────────────────────────────

    def at_sigma(self, sigma):
        """Get physics at an arbitrary σ value."""
        return self._physics_at(sigma, label=f"σ={sigma}")

    # ── Query a specific atom ─────────────────────────────────────────

    def atom(self, Z, A, be_mev=None, sigma=0.0):
        """Get atomic properties at given σ.

        Args:
            Z: proton number (or element name from known list)
            A: mass number
            be_mev: binding energy in MeV at σ=0 (optional, looked up if known)
            sigma: scale field value
        """
        N = A - Z
        if be_mev is None:
            # Try to look up from known nuclei
            for kz, kn, name, kbe in KNOWN_NUCLEI:
                if kz == Z and kn == N:
                    be_mev = kbe
                    break
            if be_mev is None:
                raise ValueError(f"Binding energy not found for Z={Z}, A={A}. "
                                 "Provide be_mev manually.")

        return three_measures(Z, N, be_mev, sigma)

    # ── Query a black hole ────────────────────────────────────────────

    def black_hole(self, name=None, mass_solar=None):
        """Get SSBM properties of a black hole.

        Args:
            name: one of the known BH names (e.g. 'M87*', 'Sgr_A*')
            mass_solar: mass in solar masses (if not using a named BH)
        """
        if name and name in KNOWN_BLACK_HOLES:
            mass_solar = KNOWN_BLACK_HOLES[name]['mass_solar']
        elif mass_solar is None:
            available = ', '.join(KNOWN_BLACK_HOLES.keys())
            raise ValueError(f"Provide mass_solar or a known BH name: {available}")

        M_kg = mass_solar * M_SUN_KG
        r_s = schwarzschild_radius(M_kg)
        sigma_horizon = XI / 2
        tau = math.pi * G * M_kg / C**3
        S_BH = 4 * math.pi * G * M_kg**2 / (1.054571817e-34 * C)

        return {
            'mass_solar': mass_solar,
            'mass_kg': M_kg,
            'r_s_m': r_s,
            'sigma_horizon': sigma_horizon,
            'lambda_eff_at_horizon': lambda_eff(sigma_horizon),
            'tau_s': tau,
            'S_BH': S_BH,
            'recycling_ratio': XI**2,
            'child_mass_kg': XI * M_kg,
            'child_mass_solar': XI * mass_solar,
        }

    # ── Query a nesting level ─────────────────────────────────────────

    def nesting_level(self, n):
        """Get properties at nesting level N.

        Level 0 = our observable universe (Hubble mass).
        Level 77 ≈ Planck mass.
        """
        if n < 0 or n > self.n_levels:
            raise ValueError(f"Level must be 0-{self.n_levels}, got {n}")
        return level_properties(n)

    # ── Bulk queries ──────────────────────────────────────────────────

    def all_environments(self):
        """Physics at every named environment."""
        return {name: self.at_scale(name) for name in ENVIRONMENTS}

    def all_nesting_levels(self):
        """Full 77-level hierarchy."""
        return full_hierarchy()

    def verification(self, sigma_values=None):
        """Run Wheeler invariance verification."""
        return verify_summary(sigma_values)

    # ── Internal ──────────────────────────────────────────────────────

    def _physics_at(self, sigma, label=""):
        """Core: compute all physics at a given σ."""
        e_sig = scale_ratio(sigma)
        return {
            'label': label,
            'sigma': sigma,
            'e_sigma': e_sig,
            'lambda_eff_mev': lambda_eff(sigma),
            'proton_mev': proton_mass_mev(sigma),
            'neutron_mev': neutron_mass_mev(sigma),
            'proton_shift': proton_mass_mev(sigma) / PROTON_TOTAL_MEV,
            'neutron_shift': neutron_mass_mev(sigma) / NEUTRON_TOTAL_MEV,
            'bonds_intact': sigma < self.sigma_conv,
            'sigma_fraction_of_conv': sigma / self.sigma_conv if self.sigma_conv > 0 else 0,
        }

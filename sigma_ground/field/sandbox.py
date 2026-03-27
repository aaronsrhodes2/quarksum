"""
σ-Scaling Sandbox — drop matter into different environments.

Take any nucleus. Place it at any σ. Watch what happens.

This is the engine that SSBM was built for: you don't need a
particle accelerator to probe high-energy QCD. You just need
a deep enough gravitational well. Nature already has them.

    sandbox = Sandbox()
    sandbox.drop('Fe-56', 'vacuum')            # σ=0, normal iron
    sandbox.drop('Fe-56', 'neutron_star')       # σ~0.05, enhanced iron
    sandbox.drop('Fe-56', 'conversion')         # σ=σ_conv, bonds break

    # Or specify σ directly:
    sandbox.at_sigma('Fe-56', 0.1)
    sandbox.at_sigma('Fe-56', 0.5)
    sandbox.at_sigma('Fe-56', 1.8)  # just before the wall

    # Or drop it at a specific radius from a mass:
    sandbox.at_location('Fe-56', r_m=10000, M_kg=2.8e30)  # NS surface

    # Sweep σ from vacuum to conversion:
    sandbox.sweep('Fe-56', n_points=50)

□σ = −ξR tells us what happens. We just compute it.
"""

import math
from .constants import (
    XI, SIGMA_CONV, G, C, HBAR,
    PROTON_BARE_MEV, PROTON_TOTAL_MEV, PROTON_QCD_MEV,
    NEUTRON_BARE_MEV, NEUTRON_TOTAL_MEV, NEUTRON_QCD_MEV,
    M_SUN_KG,
)
from .scale import scale_ratio, sigma_from_potential, lambda_eff
from .nucleon import proton_mass_mev, neutron_mass_mev
from .binding import binding_energy_mev, coulomb_energy_mev
from .bounds import check_sigma, Safety


# ═══════════════════════════════════════════════════════════════════════
#  NUCLEUS REGISTRY
# ═══════════════════════════════════════════════════════════════════════

# Known nuclei with measured binding energies at σ=0
NUCLEI = {
    'H-1':   {'Z': 1,  'N': 0,  'A': 1,   'BE': 0.0,      'name': 'Hydrogen'},
    'H-2':   {'Z': 1,  'N': 1,  'A': 2,   'BE': 2.2246,   'name': 'Deuterium'},
    'He-3':  {'Z': 2,  'N': 1,  'A': 3,   'BE': 7.718,    'name': 'Helium-3'},
    'He-4':  {'Z': 2,  'N': 2,  'A': 4,   'BE': 28.296,   'name': 'Helium-4'},
    'Li-6':  {'Z': 3,  'N': 3,  'A': 6,   'BE': 31.994,   'name': 'Lithium-6'},
    'Li-7':  {'Z': 3,  'N': 4,  'A': 7,   'BE': 39.244,   'name': 'Lithium-7'},
    'C-12':  {'Z': 6,  'N': 6,  'A': 12,  'BE': 92.162,   'name': 'Carbon-12'},
    'N-14':  {'Z': 7,  'N': 7,  'A': 14,  'BE': 104.659,  'name': 'Nitrogen-14'},
    'O-16':  {'Z': 8,  'N': 8,  'A': 16,  'BE': 127.619,  'name': 'Oxygen-16'},
    'Si-28': {'Z': 14, 'N': 14, 'A': 28,  'BE': 236.537,  'name': 'Silicon-28'},
    'Fe-56': {'Z': 26, 'N': 30, 'A': 56,  'BE': 492.254,  'name': 'Iron-56'},
    'Ni-62': {'Z': 28, 'N': 34, 'A': 62,  'BE': 545.259,  'name': 'Nickel-62'},
    'Au-197':{'Z': 79, 'N': 118,'A': 197, 'BE': 1559.40,  'name': 'Gold-197'},
    'Pb-208':{'Z': 82, 'N': 126,'A': 208, 'BE': 1636.43,  'name': 'Lead-208'},
    'U-238': {'Z': 92, 'N': 146,'A': 238, 'BE': 1801.69,  'name': 'Uranium-238'},
}

# Named environments with known σ values
ENVIRONMENTS = {
    'vacuum':           {'sigma': 0.0,        'label': 'Flat spacetime (lab)'},
    'earth_surface':    {'sigma': 1.1e-10,    'label': 'Earth surface'},
    'sun_surface':      {'sigma': 3.4e-7,     'label': 'Sun surface (photosphere)'},
    'white_dwarf':      {'sigma': 2.0e-5,     'label': 'White dwarf surface'},
    'neutron_star':     {'sigma': 0.05,       'label': 'Neutron star surface'},
    'neutron_star_core':{'sigma': 0.15,       'label': 'Neutron star core'},
    'magnetar':         {'sigma': 0.20,       'label': 'Magnetar interior'},
    'pre_conversion':   {'sigma': 1.5,        'label': '81% of σ_conv (edge zone)'},
    'near_wall':        {'sigma': 1.8,        'label': '97.6% of σ_conv (danger)'},
    'conversion':       {'sigma': SIGMA_CONV, 'label': 'σ_conv — matter converts'},
}


# ═══════════════════════════════════════════════════════════════════════
#  SANDBOX ENGINE
# ═══════════════════════════════════════════════════════════════════════

class Sandbox:
    """Drop any nucleus into any gravitational environment."""

    def _nucleus_at_sigma(self, nuc_key, sigma):
        """Core computation: what happens to this nucleus at this σ.

        Returns a dict with all computed properties.
        """
        nuc = NUCLEI[nuc_key]
        Z, N, A = nuc['Z'], nuc['N'], nuc['A']
        BE_0 = nuc['BE']
        name = nuc['name']

        # Safety check
        safety = check_sigma(sigma)

        # Scale factor
        e_sigma = scale_ratio(sigma)
        lambda_eff_mev = lambda_eff(sigma)

        # Nucleon masses
        mp = proton_mass_mev(sigma)
        mn = neutron_mass_mev(sigma)

        # Constituent mass (all nucleons)
        m_constituent = Z * mp + N * mn

        # Binding energy at this σ
        if A > 1:
            BE = binding_energy_mev(BE_0, Z, A, sigma)
            BE_strong = (BE_0 + coulomb_energy_mev(Z, A)) * e_sigma
            BE_coulomb = coulomb_energy_mev(Z, A)
        else:
            BE = 0.0
            BE_strong = 0.0
            BE_coulomb = 0.0

        # Stable (bound) mass
        m_stable = m_constituent - BE if A > 1 else mp

        # Enhancement ratios
        mp_enh = mp / PROTON_TOTAL_MEV
        mn_enh = mn / NEUTRON_TOTAL_MEV if N > 0 else 0
        be_enh = BE / BE_0 if BE_0 > 0 else 0

        # Is this nucleus still bound?
        bound = BE > 0 if A > 1 else True

        # Distance to conversion wall
        sigma_fraction = sigma / SIGMA_CONV
        margin = SIGMA_CONV - sigma

        # QCD fraction of nucleon mass at this σ
        qcd_frac = (mp - PROTON_BARE_MEV) / mp if mp > PROTON_BARE_MEV else 0

        return {
            'nucleus': nuc_key,
            'name': name,
            'Z': Z, 'N': N, 'A': A,
            'sigma': sigma,
            'safety': safety['status'],
            'safety_note': safety.get('note', ''),
            # Scale
            'e_sigma': e_sigma,
            'lambda_eff_mev': lambda_eff_mev,
            # Masses
            'proton_mass_mev': mp,
            'neutron_mass_mev': mn,
            'constituent_mass_mev': m_constituent,
            'stable_mass_mev': m_stable,
            # Enhancement
            'proton_enhancement': mp_enh,
            'neutron_enhancement': mn_enh,
            # Binding
            'BE_total_mev': BE,
            'BE_strong_mev': BE_strong,
            'BE_coulomb_mev': BE_coulomb,
            'BE_enhancement': be_enh,
            'bound': bound,
            # Structure
            'qcd_fraction': qcd_frac,
            'sigma_fraction': sigma_fraction,
            'margin_to_wall': margin,
        }

    def drop(self, nuc_key, env_name):
        """Drop a nucleus into a named environment.

        Args:
            nuc_key: e.g. 'Fe-56', 'He-4', 'U-238'
            env_name: e.g. 'vacuum', 'neutron_star', 'conversion'

        Returns: dict with all computed properties
        """
        if nuc_key not in NUCLEI:
            raise ValueError(f"Unknown nucleus: {nuc_key}. Known: {list(NUCLEI.keys())}")
        if env_name not in ENVIRONMENTS:
            raise ValueError(f"Unknown environment: {env_name}. Known: {list(ENVIRONMENTS.keys())}")

        env = ENVIRONMENTS[env_name]
        result = self._nucleus_at_sigma(nuc_key, env['sigma'])
        result['environment'] = env_name
        result['environment_label'] = env['label']
        return result

    def at_sigma(self, nuc_key, sigma):
        """Drop a nucleus at a specific σ value.

        Args:
            nuc_key: nucleus identifier
            sigma: scale field value

        Returns: dict with all computed properties
        """
        if nuc_key not in NUCLEI:
            raise ValueError(f"Unknown nucleus: {nuc_key}")
        result = self._nucleus_at_sigma(nuc_key, sigma)
        result['environment'] = f'σ={sigma}'
        result['environment_label'] = f'Custom: σ = {sigma}'
        return result

    def at_location(self, nuc_key, r_m, M_kg):
        """Drop a nucleus at a specific location (radius from mass).

        Args:
            nuc_key: nucleus identifier
            r_m: distance from center of mass (meters)
            M_kg: central mass (kg)

        Returns: dict with all computed properties
        """
        if nuc_key not in NUCLEI:
            raise ValueError(f"Unknown nucleus: {nuc_key}")
        sigma = sigma_from_potential(r_m, M_kg)
        result = self._nucleus_at_sigma(nuc_key, sigma)
        result['environment'] = f'r={r_m:.2e}m, M={M_kg:.2e}kg'
        result['environment_label'] = f'At r={r_m:.2e} m from M={M_kg:.2e} kg'
        result['r_m'] = r_m
        result['M_kg'] = M_kg
        return result

    def sweep(self, nuc_key, n_points=50, sigma_max=None):
        """Sweep σ from 0 to σ_conv (or custom max).

        This is the key visualization data: watch a nucleus
        evolve as you increase the gravitational field.

        Returns: list of result dicts, one per σ step.
        """
        if sigma_max is None:
            sigma_max = SIGMA_CONV

        if n_points <= 0:
            return []

        results = []
        for i in range(n_points + 1):
            sigma = (i / n_points) * sigma_max
            results.append(self._nucleus_at_sigma(nuc_key, sigma))

        return results

    def compare_environments(self, nuc_key):
        """Show the same nucleus across ALL environments.

        Returns: list of result dicts, one per environment.
        """
        return [self.drop(nuc_key, env) for env in ENVIRONMENTS]

    def compare_nuclei(self, env_name):
        """Show ALL nuclei in the same environment.

        Returns: list of result dicts, one per nucleus.
        """
        return [self.drop(nuc_key, env_name) for nuc_key in NUCLEI]


# ═══════════════════════════════════════════════════════════════════════
#  PRETTY PRINTER
# ═══════════════════════════════════════════════════════════════════════

def print_drop(result):
    """Print a single drop result."""
    r = result
    safety_sym = Safety.symbol(r['safety'])

    print(f"    {safety_sym} {r['name']} ({r['nucleus']}) at {r['environment_label']}")
    print(f"      σ = {r['sigma']:.6f}  ({r['sigma_fraction']*100:.1f}% of σ_conv)")
    print(f"      e^σ = {r['e_sigma']:.6f}  |  Λ_eff = {r['lambda_eff_mev']:.2f} MeV")
    print(f"      m_p = {r['proton_mass_mev']:.3f} MeV ({r['proton_enhancement']:.6f}×)")
    if r['A'] > 1:
        print(f"      BE  = {r['BE_total_mev']:.3f} MeV ({r['BE_enhancement']:.4f}× vacuum)")
        print(f"        strong: {r['BE_strong_mev']:.3f} MeV | Coulomb: {r['BE_coulomb_mev']:.3f} MeV")
        bound_str = '✓ BOUND' if r['bound'] else '✗ UNBOUND — nucleus dissolves'
        print(f"      Status: {bound_str}")
    print(f"      QCD fraction: {r['qcd_fraction']*100:.2f}%")
    if r['safety'] != 'SAFE' and r.get('safety_note'):
        print(f"      ⚠ {r['safety_note'][:80]}")
    print()


def print_sweep(results):
    """Print a σ sweep as a table."""
    r0 = results[0]
    print(f"  ── {r0['name']} ({r0['nucleus']}) — σ sweep to conversion ──")
    print(f"  {'σ':>10s}  {'%σ_conv':>8s}  {'e^σ':>10s}  {'m_p (MeV)':>10s}  "
          f"{'BE (MeV)':>10s}  {'Bound':>6s}  {'Safety'}")
    print(f"  {'─'*80}")

    for r in results:
        bound = '✓' if r['bound'] else '✗'
        safety = Safety.symbol(r['safety'])
        be_str = f"{r['BE_total_mev']:.2f}" if r['A'] > 1 else '—'
        print(f"  {r['sigma']:10.5f}  {r['sigma_fraction']*100:7.1f}%  {r['e_sigma']:10.4f}  "
              f"{r['proton_mass_mev']:10.3f}  {be_str:>10s}  {bound:>6s}  {safety} {r['safety']}")
    print()


def print_environment_comparison(results):
    """Print one nucleus across all environments."""
    r0 = results[0]
    print()
    print(f"  ╔═══════════════════════════════════════════════════════════╗")
    print(f"  ║  {r0['name']} ({r0['nucleus']}) — DROPPED INTO EVERY ENVIRONMENT")
    print(f"  ╚═══════════════════════════════════════════════════════════╝")
    print()
    for r in results:
        print_drop(r)


def run_sandbox_demo():
    """Run the sandbox demo: drop Iron-56 everywhere."""
    import time
    t0 = time.perf_counter()

    sb = Sandbox()

    print()
    print("  ╔═══════════════════════════════════════════════════════════╗")
    print("  ║  σ-SCALING SANDBOX — DROP MATTER, WATCH PHYSICS CHANGE  ║")
    print("  ╠═══════════════════════════════════════════════════════════╣")
    print("  ║  □σ = −ξR tells us what happens. We just compute it.    ║")
    print("  ╚═══════════════════════════════════════════════════════════╝")

    # 1. Iron-56 across all environments
    print_environment_comparison(sb.compare_environments('Fe-56'))

    # 2. Sweep Iron-56 from vacuum to conversion
    sweep = sb.sweep('Fe-56', n_points=20)
    print_sweep(sweep)

    # 3. Drop at specific location: surface of a 2 M☉ neutron star at 12 km
    print("  ── LOCATION DROP: Fe-56 at NS surface (2 M☉, R=12 km) ──")
    print()
    result = sb.at_location('Fe-56', 12000, 2.0 * M_SUN_KG)
    print_drop(result)

    # 4. Compare all nuclei at neutron star surface
    print("  ── ALL NUCLEI AT NEUTRON STAR SURFACE ──")
    print()
    ns_results = sb.compare_nuclei('neutron_star')
    print(f"  {'Nucleus':<10s}  {'m_p(σ)':>10s}  {'BE(σ)':>10s}  {'Bound':>6s}  {'BE/BE₀':>8s}")
    print(f"  {'─'*55}")
    for r in ns_results:
        be_str = f"{r['BE_total_mev']:.2f}" if r['A'] > 1 else '—'
        bound = '✓' if r['bound'] else '✗'
        be_ratio = f"{r['BE_enhancement']:.4f}" if r['A'] > 1 else '—'
        print(f"  {r['nucleus']:<10s}  {r['proton_mass_mev']:10.3f}  {be_str:>10s}  {bound:>6s}  {be_ratio:>8s}")
    print()

    elapsed = time.perf_counter() - t0
    print(f"  Sandbox computed in {elapsed*1000:.1f} ms")
    print()

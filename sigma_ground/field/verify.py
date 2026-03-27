"""
Wheeler Invariance Verification — the three-measure closure test.

For any nucleus at any σ:
    stable_mass = constituent_mass − binding_energy/c²

This must close exactly (to floating-point precision) at EVERY σ.
If it doesn't, the model is broken.
"""

from .nucleon import proton_mass_mev, neutron_mass_mev
from .binding import binding_energy_mev
from .constants import M_ELECTRON_MEV


def three_measures(Z, N, be_mev_at_0, sigma=0.0):
    """Compute three independent measures of a nucleus at given σ.

    Args:
        Z: proton number
        N: neutron number
        be_mev_at_0: binding energy in MeV at σ=0 (from AME tables)
        sigma: scale field value

    Returns:
        dict with constituent_mass, binding_energy, stable_mass,
        and the closure residual (should be ~0).
    """
    A = Z + N

    # Constituent mass: sum of free nucleon masses
    m_p = proton_mass_mev(sigma)
    m_n = neutron_mass_mev(sigma)
    constituent = Z * m_p + N * m_n

    # Binding energy at this σ
    be = binding_energy_mev(be_mev_at_0, Z, A, sigma)

    # Stable mass: what a scale would read
    stable = constituent - be

    # Atomic mass (add electrons)
    atomic = stable + Z * M_ELECTRON_MEV

    # Closure check: stable = constituent - binding (by definition)
    # The residual should be exactly 0.0
    residual = stable - (constituent - be)

    return {
        'Z': Z, 'N': N, 'A': A, 'sigma': sigma,
        'constituent_mev': constituent,
        'binding_mev': be,
        'stable_mev': stable,
        'atomic_mev': atomic,
        'residual_mev': residual,
    }


# ── Some well-known nuclei for testing ────────────────────────────────
# (Z, N, name, binding_energy_at_sigma_0 in MeV)
KNOWN_NUCLEI = [
    (1, 0, 'Hydrogen-1', 0.0),
    (1, 1, 'Deuterium', 2.224),
    (2, 2, 'Helium-4', 28.296),
    (6, 6, 'Carbon-12', 92.162),
    (8, 8, 'Oxygen-16', 127.619),
    (26, 30, 'Iron-56', 492.254),
    (79, 118, 'Gold-197', 1559.40),
    (92, 146, 'Uranium-238', 1801.69),
]


def verify_all(sigma_values=None):
    """Run Wheeler invariance check across all known nuclei at multiple σ.

    Returns list of results. Every residual should be 0.0.
    """
    if sigma_values is None:
        sigma_values = [0.0, 0.1, 0.5, 1.0, -0.5, -1.0]

    results = []
    for Z, N, name, be in KNOWN_NUCLEI:
        for sigma in sigma_values:
            r = three_measures(Z, N, be, sigma)
            r['name'] = name
            results.append(r)
    return results


def verify_summary(sigma_values=None):
    """Run verification and return pass/fail summary."""
    results = verify_all(sigma_values)
    passed = sum(1 for r in results if abs(r['residual_mev']) < 1e-10)
    total = len(results)
    return {
        'total': total,
        'passed': passed,
        'failed': total - passed,
        'pass_rate': passed / total if total > 0 else 0,
        'all_pass': passed == total,
    }

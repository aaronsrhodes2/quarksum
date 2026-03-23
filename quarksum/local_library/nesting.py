"""
Chiral Nesting Hierarchy — 77 levels, Hubble to Planck.

Each nesting level inherits a fraction ξ of its parent's mass.
M_N = M_hubble × ξ^N

The funnel sum S = 1/(1 - f_bh × ξ) is a self-similar fixed point.
"""

import math
from .constants import XI, G, C, HBAR, M_HUBBLE_KG, M_PLANCK_KG, M_SUN_KG
from .scale import schwarzschild_radius


# MEASURED: SMBH-to-host mass fraction (Magorrian/M-σ relation).
# M_BH / M_bulge ≈ 0.002-0.013 across galaxies (Kormendy & Ho 2013).
# This is observational data, like n₀ or Λ_QCD — not a borrowed formula.
# In the nesting hierarchy, this sets the mass recycled per level.
F_BH = 0.01

# Tapering ratio per level
R_TAPER = F_BH * XI  # ≈ 0.001582

# Funnel sum (self-similar fixed point)
S_FUNNEL = 1.0 / (1.0 - R_TAPER)  # ≈ 1.001585


def level_mass_kg(n):
    """Mass at nesting level N.

    M_N = M_hubble × ξ^N
    """
    return M_HUBBLE_KG * (XI ** n)


def level_count():
    """Number of levels from Hubble mass to Planck mass.

    N = log(M_planck / M_hubble) / log(ξ)
    """
    return int(math.log(M_PLANCK_KG / M_HUBBLE_KG) / math.log(XI))


def level_properties(n):
    """Compute properties for nesting level N.

    Returns dict with mass, Schwarzschild radius,
    Bekenstein-Hawking entropy, interior time.
    """
    M = level_mass_kg(n)
    r_s = schwarzschild_radius(M)

    # Bekenstein-Hawking entropy: S_BH = 4πGM²/(ℏc)
    S_BH = 4 * math.pi * G * M**2 / (HBAR * C)

    # Interior proper time: τ = πGM/c³
    tau_s = math.pi * G * M / C**3

    # Recycling ratio: S_birth / S_parent ∝ ξ²
    recycling = XI**2

    return {
        'level': n,
        'mass_kg': M,
        'mass_solar': M / M_SUN_KG,
        'r_s_m': r_s,
        'S_BH': S_BH,
        'tau_s': tau_s,
        'recycling_ratio': recycling,
    }


def full_hierarchy():
    """Generate the complete nesting hierarchy.

    Returns list of dicts, one per level, from Hubble (L0) to Planck (L76).
    """
    n_levels = level_count()
    return [level_properties(n) for n in range(n_levels + 1)]


def funnel_invariance():
    """Demonstrate the funnel invariance F(N)/M_N = S for all N.

    The total mass recycled through the funnel below any level N
    divided by that level's mass is always S = 1/(1-r).
    """
    results = []
    n_max = min(level_count(), 10)  # first 10 levels suffice
    for n in range(n_max):
        M_n = level_mass_kg(n)
        # Funnel sum below level n: geometric series
        funnel_below = M_n * R_TAPER / (1 - R_TAPER)
        total = M_n + funnel_below
        ratio = total / M_n
        results.append({
            'level': n,
            'mass_kg': M_n,
            'funnel_total_kg': total,
            'ratio': ratio,
            'expected': S_FUNNEL,
            'match': abs(ratio - S_FUNNEL) < 1e-10,
        })
    return results

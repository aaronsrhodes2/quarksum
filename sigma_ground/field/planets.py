"""
Planetary Interior Models — known planets with layered structure.

Each planet is defined by its total mass, total radius, and a set of
concentric layers (core → surface) with density, composition label,
and radial boundary.

All data from standard geophysics / planetary science references.
"""

import math
from .constants import G, C, M_SUN_KG

# ── Earth ─────────────────────────────────────────────────────────────
EARTH = {
    'name': 'Earth',
    'mass_kg': 5.972e24,
    'radius_m': 6.371e6,
    'layers': [
        {
            'name': 'Inner Core',
            'r_outer_m': 1.221e6,
            'density_kg_m3': 13000,
            'composition': 'Solid iron-nickel',
            'color': '#cc3300',      # deep red
            'temp_K': 5400,
        },
        {
            'name': 'Outer Core',
            'r_outer_m': 3.486e6,
            'density_kg_m3': 11000,
            'composition': 'Liquid iron-nickel',
            'color': '#e06030',      # orange-red
            'temp_K': 4500,
        },
        {
            'name': 'Lower Mantle',
            'r_outer_m': 5.701e6,
            'density_kg_m3': 4900,
            'composition': 'Silicate (bridgmanite)',
            'color': '#d4883a',      # brown-orange
            'temp_K': 3000,
        },
        {
            'name': 'Upper Mantle',
            'r_outer_m': 6.336e6,
            'density_kg_m3': 3400,
            'composition': 'Silicate (olivine)',
            'color': '#8a9a5b',      # olive green
            'temp_K': 1600,
        },
        {
            'name': 'Crust',
            'r_outer_m': 6.371e6,
            'density_kg_m3': 2700,
            'composition': 'Silicate rock',
            'color': '#6b8e6b',      # sage green
            'temp_K': 300,
        },
    ],
}

# ── Mars ──────────────────────────────────────────────────────────────
MARS = {
    'name': 'Mars',
    'mass_kg': 6.417e23,
    'radius_m': 3.390e6,
    'layers': [
        {
            'name': 'Core',
            'r_outer_m': 1.830e6,
            'density_kg_m3': 6200,
            'composition': 'Iron-sulfide',
            'color': '#cc4422',
            'temp_K': 2100,
        },
        {
            'name': 'Mantle',
            'r_outer_m': 3.350e6,
            'density_kg_m3': 3500,
            'composition': 'Silicate',
            'color': '#c27840',
            'temp_K': 1500,
        },
        {
            'name': 'Crust',
            'r_outer_m': 3.390e6,
            'density_kg_m3': 2900,
            'composition': 'Basalt + iron oxide',
            'color': '#c1440e',      # Mars red
            'temp_K': 210,
        },
    ],
}

# ── Jupiter ───────────────────────────────────────────────────────────
JUPITER = {
    'name': 'Jupiter',
    'mass_kg': 1.898e27,
    'radius_m': 6.991e7,
    'layers': [
        {
            'name': 'Rocky Core',
            'r_outer_m': 1.5e7,
            'density_kg_m3': 25000,
            'composition': 'Rock + ice (uncertain)',
            'color': '#8B4513',      # saddle brown
            'temp_K': 36000,
        },
        {
            'name': 'Metallic Hydrogen',
            'r_outer_m': 4.5e7,
            'density_kg_m3': 4000,
            'composition': 'Liquid metallic H',
            'color': '#4a6fa5',      # steel blue
            'temp_K': 20000,
        },
        {
            'name': 'Molecular Hydrogen',
            'r_outer_m': 6.7e7,
            'density_kg_m3': 200,
            'composition': 'Molecular H₂ + He',
            'color': '#c8a86e',      # tan
            'temp_K': 2000,
        },
        {
            'name': 'Cloud Deck',
            'r_outer_m': 6.991e7,
            'density_kg_m3': 0.2,
            'composition': 'NH₃, H₂O, H₂S clouds',
            'color': '#dab682',      # cream
            'temp_K': 165,
        },
    ],
}

# ── Neutron Star (for comparison — extreme σ) ─────────────────────────
NEUTRON_STAR = {
    'name': 'Neutron Star (1.4 M☉)',
    'mass_kg': 1.4 * M_SUN_KG,
    'radius_m': 1.1e4,  # ~11 km
    'layers': [
        {
            'name': 'Inner Core',
            'r_outer_m': 5.0e3,
            'density_kg_m3': 1e18,
            'composition': 'Quark-gluon plasma / superfluid neutrons',
            'color': '#6600cc',      # deep purple
            'temp_K': 1e9,
        },
        {
            'name': 'Outer Core',
            'r_outer_m': 9.0e3,
            'density_kg_m3': 4e17,
            'composition': 'Superfluid neutrons + superconducting protons',
            'color': '#3366cc',      # blue
            'temp_K': 5e8,
        },
        {
            'name': 'Inner Crust',
            'r_outer_m': 1.05e4,
            'density_kg_m3': 4e14,
            'composition': 'Neutron-rich nuclei + free neutrons',
            'color': '#5599cc',      # light blue
            'temp_K': 1e8,
        },
        {
            'name': 'Outer Crust',
            'r_outer_m': 1.1e4,
            'density_kg_m3': 1e10,
            'composition': 'Iron-peak nuclei + electrons',
            'color': '#88bbdd',      # pale blue
            'temp_K': 1e7,
        },
    ],
}

# ── All planets registry ──────────────────────────────────────────────
ALL_BODIES = {
    'earth': EARTH,
    'mars': MARS,
    'jupiter': JUPITER,
    'neutron_star': NEUTRON_STAR,
}

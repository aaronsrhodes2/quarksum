"""
Material — the bridge between atomic physics and visual appearance.

A Material has two sides:
1. Physics side: composition, density, bond strength (from QuarkSum, σ-dependent)
2. Optical side: color, reflectance, roughness (EM-based, σ-INVARIANT)

The key SSBM insight: light bounces off atoms via electromagnetism.
EM doesn't care about σ. So colors don't change near a black hole.
But the material's MASS changes (QCD-dependent), and its STRUCTURAL
INTEGRITY changes (bond strength is partly QCD).

This is physically correct and observationally testable.
"""

import math
import sys
import os

# Try to import from local_library for σ-dependent mass calculations
# Falls back to standalone if local_library isn't available
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from local_library.nucleon import proton_mass_mev, neutron_mass_mev
    from local_library.scale import scale_ratio
    HAS_PHYSICS = True
except ImportError:
    HAS_PHYSICS = False


class Material:
    """A material with both physical and optical properties.

    Args:
        name: human-readable name
        color: Vec3(r, g, b) base color [0-1]
        reflectance: 0 = matte, 1 = mirror
        roughness: 0 = smooth, 1 = rough (diffuse scattering)
        opacity: 0 = transparent, 1 = opaque
        ior: index of refraction (glass ≈ 1.5, water ≈ 1.33)
        emission: Vec3(r, g, b) emitted light (for glowing materials)

        # Physics properties
        density_kg_m3: bulk density at σ=0
        mean_Z: average atomic number
        mean_A: average mass number
        composition: human-readable composition string
    """

    def __init__(self, name, color, reflectance=0.0, roughness=0.5,
                 opacity=1.0, ior=1.5, emission=None,
                 density_kg_m3=1000, mean_Z=8, mean_A=16,
                 composition=""):
        self.name = name
        self.color = color
        self.reflectance = reflectance
        self.roughness = roughness
        self.opacity = opacity
        self.ior = ior
        self.emission = emission
        self.density_kg_m3 = density_kg_m3
        self.mean_Z = mean_Z
        self.mean_A = mean_A
        self.composition = composition

    def density_at_sigma(self, sigma):
        """Density at a given σ.

        Mass scales with e^σ (QCD component), volume stays the same
        (EM bonds set interatomic spacing, which is σ-invariant).

        So density scales roughly as e^σ for σ-dominated materials.
        More precisely: only the QCD fraction of mass scales.
        """
        if not HAS_PHYSICS:
            return self.density_kg_m3 * math.exp(sigma * 0.99)

        # Use actual nucleon mass scaling
        m_p_0 = proton_mass_mev(0)
        m_p_sig = proton_mass_mev(sigma)
        return self.density_kg_m3 * (m_p_sig / m_p_0)

    def color_at_sigma(self, sigma):
        """Color at a given σ.

        INVARIANT. Electromagnetic interactions don't depend on Λ_QCD.
        The photon doesn't care about the strong force.

        This is a core SSBM prediction: things near black holes
        look the same color. They're just heavier.
        """
        return self.color  # Always the same

    def __repr__(self):
        return f"Material('{self.name}', Z={self.mean_Z}, A={self.mean_A})"

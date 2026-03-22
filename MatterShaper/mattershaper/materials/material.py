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

        # Dynamics properties (required for fluid/rigid-body simulation)
        viscosity_pa_s: dynamic viscosity in Pa·s at reference conditions.
            None = not a fluid / dynamics not modelled.
            Gas (air) at 20°C: 1.81e-5. Water at 20°C: 1.002e-3. Honey: ~10.
        bulk_modulus_pa: resistance to compression in Pa.
            None = not needed (pure rendering).
            Water: 2.2e9. Steel: ~160e9. Air (ideal gas, P=1atm): ~1.01e5.
        restitution: coefficient of restitution for collisions [0–1].
            0 = perfectly inelastic (clay). 1 = perfectly elastic (ideal).
            MEASURED — elastic wave theory requires the full phonon spectrum.
            Rubber: ~0.85. Steel: ~0.70. Clay: ~0.05.
        reference_temp_K: temperature at which viscosity/density are specified.
    """

    def __init__(self, name, color, reflectance=0.0, roughness=0.5,
                 opacity=1.0, ior=1.5, emission=None,
                 density_kg_m3=1000, mean_Z=8, mean_A=16,
                 composition="",
                 alpha_r=0.0, alpha_g=0.0, alpha_b=0.0,
                 viscosity_pa_s=None, bulk_modulus_pa=None,
                 restitution=0.5, reference_temp_K=293.15):
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
        # Per-channel Beer-Lambert absorption coefficients (scene units: 1/inch).
        # op_i = 1 - exp(-alpha_i × dl) per VolumeNode.
        # σ-INVARIANT: EM absorption doesn't depend on Λ_QCD.
        # Source: 4πk/λ (from imaginary refractive index k) converted to /inch.
        self.alpha_r = alpha_r   # Red channel   (~700 nm representative)
        self.alpha_g = alpha_g   # Green channel (~550 nm representative)
        self.alpha_b = alpha_b   # Blue channel  (~450 nm representative)

        # Dynamics fields — None = not a dynamic material (backward compatible).
        self.viscosity_pa_s   = viscosity_pa_s    # Pa·s   at reference_temp_K
        self.bulk_modulus_pa  = bulk_modulus_pa   # Pa     (compressibility)
        self.restitution      = restitution       # [0–1]  collision elasticity
        self.reference_temp_K = reference_temp_K # K      conditions for above

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

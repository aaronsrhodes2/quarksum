"""
Materials — what things are made of, derived from atomic physics.

Each material knows:
1. Its atomic composition (from QuarkSum: Z, A, binding energy)
2. Its optical properties (reflectance, color, roughness)
3. How those properties change with σ (the SSBM prediction)

At σ = 0, everything is standard. The optical properties are
derived from electromagnetic interactions, which are σ-INVARIANT.
But the MASS of the material, its DENSITY, and its BOND STRENGTH
all depend on σ through the QCD channel.

This means: a ceramic cup looks the same color at any σ,
but it becomes heavier and eventually shatters as σ grows.
"""

from .material import Material
from .library import (
    CERAMIC, STEEL, WATER, GLASS, BASALT, IRON,
    CARBON, ICE, SILICATE, REGOLITH,
)

__all__ = [
    'Material',
    'CERAMIC', 'STEEL', 'WATER', 'GLASS', 'BASALT', 'IRON',
    'CARBON', 'ICE', 'SILICATE', 'REGOLITH',
]

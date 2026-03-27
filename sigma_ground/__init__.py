"""
sigma_ground — Sigma-Ground Physics Library
============================================

Unified physics library covering particle inventory, scalar field
mechanics, and N-body dynamics. Pure Python, zero external dependencies.

  sigma_ground.inventory  — Particle inventory and mass closure tool.
                            Resolves materials → molecules → atoms → quarks.
  sigma_ground.field      — σ-field scalar physics. Constants, bounds,
                            entanglement, and spacetime geometry.
  sigma_ground.dynamics   — N-body dynamics, SPH fluid, leapfrog integrator,
                            Barnes-Hut gravity.

Quick start::

    # Particle inventory
    from sigma_ground.inventory import stoq, build_quick_structure
    s = build_quick_structure("Iron", 1.0)
    result = stoq(s)

    # σ-field constants
    from sigma_ground.field.constants import XI, HBAR, C

    # N-body dynamics
    from sigma_ground.dynamics.scene import PhysicsScene

Physics/Rendering boundary
--------------------------
This package contains ONLY physics. No pixel buffers, no PNG encoding,
no ray tracing. Rendering lives in matter-shaper (separate project).

Author: Aaron Rhodes
"""

from .constants import (
    G, C, HBAR, L_PLANCK,
    XI, SIGMA_CONV, ETA,
    M_SUN_KG, L_SUN_W, AU_M, YEAR_S,
)
from .dynamics.vec import Vec3

__all__ = [
    # Constants
    'G', 'C', 'HBAR', 'L_PLANCK',
    'XI', 'SIGMA_CONV', 'ETA',
    'M_SUN_KG', 'L_SUN_W', 'AU_M', 'YEAR_S',
    # Math primitives
    'Vec3',
]

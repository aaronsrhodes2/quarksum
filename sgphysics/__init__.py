"""
sgphysics — Sigma-Ground Physics Library
=========================================

Unified physics engine for the SSBM (Scale-Shifted Baryonic Matter)
framework. Consolidates all physics from:

  - local_library/   — SSBM σ-field, N-body, celestial mechanics
  - MatterShaper/mattershaper/physics/ — SPH fluid dynamics, rigid-body sim

Architecture
------------
  sgphysics/
  ├── constants.py     — All physical constants (authoritative, measured)
  ├── dynamics/        — Particle dynamics, fluids, gravity, rigid-body
  │   ├── vec.py       — Vec3: 3D vector math (pure, no rendering)
  │   ├── collision.py — Sphere-sphere / sphere-plane impulse response
  │   ├── stepper.py   — Leapfrog integrator with CFL-constrained dt
  │   ├── parcel.py    — PhysicsParcel: matter with dynamics state
  │   ├── scene.py     — PhysicsScene: parcels + gravity + ground
  │   ├── fluid/       — SPH fluid dynamics
  │   │   ├── kernel.py   — Cubic spline smoothing kernel W(r,h)
  │   │   └── eos.py      — Equation of state P(ρ,ρ₀,K)
  │   └── gravity/     — Tree-based gravity
  │       └── barnes_hut.py — Barnes-Hut O(N log N) gravity
  ├── core/            — SSBM σ-field physics (from local_library)
  ├── celestial/       — N-body celestial mechanics (from local_library)
  └── inventory/       — Particle inventory / mass closure (from quarksum)

Physics/Rendering boundary
--------------------------
This package contains ONLY physics. No pixel buffers, no PNG encoding,
no ray tracing. The MatterShaper render layer (entangler) imports from
here; this package never imports from any renderer.

Theory: SSBM by Captain Aaron Rhodes.
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

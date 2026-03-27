"""
sgphysics.dynamics — Particle and continuum dynamics.

Rigid-body physics (PhysicsParcel, PhysicsScene, stepper) and
SPH fluid dynamics (kernel, eos). Also provides the canonical Vec3.

Subpackages:
  fluid/       — SPH: kernel.py, eos.py
  gravity/     — Barnes-Hut tree gravity
"""

from .vec       import Vec3
from .parcel    import PhysicsParcel
from .scene     import PhysicsScene
from .stepper   import step, step_to
from .collision import resolve_sphere_sphere, resolve_sphere_plane

__all__ = [
    'Vec3',
    'PhysicsParcel',
    'PhysicsScene',
    'step',
    'step_to',
    'resolve_sphere_sphere',
    'resolve_sphere_plane',
]

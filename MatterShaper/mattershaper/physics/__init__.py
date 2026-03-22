"""
mattershaper.physics — Dynamics layer for MatterShaper.

Architecture
============
This package adds TIME to MatterShaper. The render pipeline (entangler) is
a snapshot renderer — it knows nothing about velocity or force. This layer
evolves the scene forward in time, then hands updated node positions back
to the renderer.

The separation is strict:
  - Physics parcels own position, velocity, mass.
  - The renderer never sees velocity.
  - The renderer never owns time.

Submodules
----------
  parcel.py    — PhysicsParcel: wraps a geometry object with dynamics state
  scene.py     — PhysicsScene: list of parcels + gravity + ground plane
  collision.py — sphere-sphere and sphere-plane impulse response
  stepper.py   — Leapfrog integrator with CFL-constrained dt

  fluid/       — SPH fluid dynamics (future: dam-break, free surface)
    __init__.py
    kernel.py  — cubic spline kernel W(r,h) and grad W
    eos.py     — equation of state P(ρ,ρ₀,K) for incompressible fluids

Typical usage (rigid-body bounce):
  from mattershaper.physics import PhysicsScene, PhysicsParcel
  from mattershaper.physics.stepper import step

  ball    = PhysicsParcel(radius=0.5, material=copper(), position=Vec3(0,3,0),
                          velocity=Vec3(2,0,0))
  target  = PhysicsParcel(radius=0.5, material=aluminum(), position=Vec3(3,0.5,0),
                          is_static=False)
  scene   = PhysicsScene([ball, target])
  for _ in range(steps):
      step(scene, dt)
"""

from .parcel    import PhysicsParcel
from .scene     import PhysicsScene
from .stepper   import step, step_to

__all__ = ['PhysicsParcel', 'PhysicsScene', 'step', 'step_to']

"""
PhysicsParcel — a piece of matter that moves.

A PhysicsParcel wraps a geometry object (sphere, ellipsoid, plane, …) with
dynamics state: position, velocity, mass, and collision geometry.

The key distinction from the render layer:
  - The renderer's EntanglerSphere knows how to GENERATE surface nodes and
    project them to pixels.
  - PhysicsParcel knows the object's CENTER, RADIUS, MASS, and VELOCITY.
    It is intentionally ignorant of rendering.

The renderer renders a snapshot of node positions.
The physics parcel moves those positions forward in time.
The two communicate through position only.

Mass
----
  m = (4/3)π r³ × ρ   for a sphere
  m = (4/3)π a b c × ρ for an ellipsoid

  ρ = material.density_kg_m3  (kg/m³)
  FIRST_PRINCIPLES: mass = density × volume. No approximation.

  If material.density_kg_m3 is unavailable, mass must be set directly.

Collision geometry
------------------
  For broad-phase collision detection we use a bounding sphere of radius `r`.
  Exact for spherical objects. Conservative (overestimates) for ellipsoids
  and planes. A bounding sphere is fast O(1) to test and correct enough
  for real physics: if the bounding spheres don't touch, nothing inside them
  can touch either.

is_static
---------
  A static parcel (ground plane, wall) has infinite effective mass.
  Impulses act on the colliding parcel only.
  is_static=True → velocity is always Vec3(0,0,0), mass = infinity.

σ-dependence
------------
  mass = (4/3)π r³ × material.density_at_sigma(sigma)
  If sigma ≠ 0, the parcel is heavier. It still bounces correctly —
  Newton's 2nd law and the impulse equation both scale with mass and cancel
  in the collision impulse formula (for equal materials the cancellation is
  exact; for mixed materials the heavier parcel transfers less velocity).
"""

import math
from .vec import Vec3


class PhysicsParcel:
    """A piece of matter with dynamics state.

    Args:
        radius:     bounding sphere radius (m). Required.
        material:   Material instance. density_kg_m3 used for mass.
        position:   Vec3 world-space center. Default: origin.
        velocity:   Vec3 initial velocity (m/s). Default: rest.
        is_static:  If True, parcel never moves (infinite mass). Default: False.
        mass:       Override computed mass (kg). None → compute from density.
        sigma:      σ-field value for density scaling. Default: 0.
        label:      Human-readable name for debugging.
    """

    def __init__(self, radius, material,
                 position=None, velocity=None,
                 is_static=False, mass=None, sigma=0.0,
                 label=''):
        self.radius    = float(radius)
        self.material  = material
        self.position  = position  if position  is not None else Vec3(0, 0, 0)
        self.velocity  = velocity  if velocity  is not None else Vec3(0, 0, 0)
        self.is_static = is_static
        self.sigma     = sigma
        self.label     = label

        # Mass: m = (4/3)π r³ × ρ(σ)
        # FIRST_PRINCIPLES: density × volume (sphere)
        if mass is not None:
            self.mass = float(mass)
        elif is_static:
            # Static parcels get float('inf') mass.
            # NOTE ON INFINITY: this is IEEE 754 computational infinity,
            # not a physical claim. It encodes the limit "M_wall >> M_collider"
            # so that inv_mass = 0 without a conditional branch.
            # In practice, a floor or wall is just very massive — the impulse
            # equation gives v_wall → 0 as M_wall/M_collider → ∞.
            # See physics/constants.py for the full note on different kinds
            # of infinity (IEEE 754, Cantor cardinals, physical singularities).
            self.mass = float('inf')
        else:
            rho = material.density_at_sigma(sigma)
            self.mass = (4.0 / 3.0) * math.pi * (radius ** 3) * rho

        # Restitution: from material if available, else 0.5
        self.restitution = getattr(material, 'restitution', 0.5)

    @property
    def inv_mass(self):
        """Reciprocal mass 1/m (kg⁻¹) — IEEE 754 infinity-safe.

        Static parcels return 0.0, encoding the limit M_wall → ∞.
        This means static objects absorb impulses without moving, which is
        exactly the correct physics: if M₂ >> M₁, the impulse equation gives
        Δv₁ ≈ −(1+e)v_rel and Δv₂ ≈ 0.

        FIRST_PRINCIPLES: appears in the collision impulse formula
          j = −(1+e) v_rel / (1/m₁ + 1/m₂)
        For a static wall: 1/m₂ = 0, giving j = −(1+e) v_rel × m₁.
        """
        if self.is_static or self.mass == float('inf'):
            return 0.0
        return 1.0 / self.mass

    def kinetic_energy(self):
        """Translational kinetic energy KE = ½mv² (joules).

        FIRST_PRINCIPLES: classical (non-relativistic) mechanics.
        Valid when v << c. At simulation scales, v < 100 m/s, so
        relativistic correction β = v/c < 3×10⁻⁷ — negligible.

        Returns 0.0 for static parcels (they carry no kinetic energy
        in the simulation frame — no motion, no KE).
        """
        if self.is_static:
            return 0.0
        v2 = self.velocity.dot(self.velocity)
        return 0.5 * self.mass * v2

    def momentum(self):
        """Linear momentum p = mv (kg·m/s), returned as Vec3.

        FIRST_PRINCIPLES: Newtonian mechanics. In an isolated two-body
        collision: p₁ + p₂ = const. Verified by test_bounce_physics.py
        (momentum conservation error < 2%).

        Returns Vec3(0,0,0) for static parcels (infinite mass, zero velocity).
        Note: their momentum is physically undefined (∞ × 0 = NaN in IEEE 754),
        so we return the physically motivated limit: zero contribution.
        """
        if self.is_static:
            return Vec3(0, 0, 0)
        return self.velocity * self.mass

    def __repr__(self):
        lbl = f' "{self.label}"' if self.label else ''
        return (f"PhysicsParcel{lbl}(r={self.radius:.3f}, "
                f"m={self.mass:.3f} kg, "
                f"pos={self.position}, vel={self.velocity})")

"""
Collision detection and impulse response for rigid body simulation.

Physics
=======

Sphere-sphere collision
-----------------------
Two spheres collide when their center-to-center distance d < r₁ + r₂.

The contact normal n̂ points from sphere 1's center to sphere 2's center:
  n̂ = (p₂ - p₁) / |p₂ - p₁|

The relative velocity along the contact normal:
  v_rel = (v₁ - v₂) · n̂

If v_rel ≤ 0, the spheres are already separating — no impulse needed.

The impulse magnitude (derivation from Newton's 2nd law + restitution):
  j = -(1 + e) × v_rel / (1/m₁ + 1/m₂)

Where e = min(e₁, e₂) is the coefficient of restitution.
  e = 0: perfectly inelastic (clay). Objects stick together.
  e = 1: perfectly elastic. Kinetic energy conserved.

Velocity updates:
  v₁' = v₁ + j/m₁ × n̂
  v₂' = v₂ - j/m₂ × n̂

FIRST_PRINCIPLES: this is the exact solution for two rigid spheres
interacting via a central force impulse. No energy dissipation beyond e.
Source: Goldsmith (1960) "Impact" pp.8-12; Stronge (2000) "Impact Mechanics".

Sphere-plane collision
----------------------
A plane is defined by a point on it and its outward normal.
The ground plane: point = Vec3(0,0,0), normal = Vec3(0,1,0).

Contact when: (p - p_plane) · n_plane < r
  (the sphere center is within radius of the plane)

The relative velocity of the sphere toward the plane:
  v_rel = v · n_plane   (positive = moving toward plane)

If v_rel ≤ 0, sphere moving away — no impulse.

Impulse magnitude (plane has infinite mass, inv_mass = 0):
  j = -(1 + e) × v_rel / (1/m)

Velocity update:
  v' = v + j/m × n_plane

Overlap resolution
------------------
After applying impulse, we also positionally resolve overlap (push apart).
Without this, spheres can tunnel through each other over multiple time steps
if dt is large relative to collision duration.

Position correction: push each sphere out by half the penetration depth
along the contact normal, weighted by inverse mass.
  penetration = r₁ + r₂ - d
  correction = penetration × (inv_mass₁ / (inv_mass₁ + inv_mass₂))
  p₁ -= correction × n̂ × inv_mass₁ / (inv_mass₁ + inv_mass₂)
  p₂ += correction × n̂ × inv_mass₂ / (inv_mass₁ + inv_mass₂)

σ-dependence
------------
All σ effects are already in parcel.mass (via density_at_sigma).
The collision equations use mass only — σ-dependence flows through correctly.

Origin tags
-----------
  Impulse formula: FIRST_PRINCIPLES (Newton + restitution model)
  Restitution: MEASURED (per material in physics_materials.py)
  Overlap resolution: NOT_PHYSICS (numerical artifact correction)
"""

import math
from .vec import Vec3


# ── Sphere-sphere ────────────────────────────────────────────────────────────

def sphere_sphere_collision(p1, p2, tolerance=1e-9):
    """Check if two PhysicsParcels (spheres) are overlapping.

    Returns (is_colliding, penetration_depth, contact_normal)
    contact_normal points from p1 toward p2.
    """
    delta = p2.position - p1.position
    dist  = delta.length()
    min_d = p1.radius + p2.radius

    if dist < tolerance:
        # Degenerate: same center. Push along +Y arbitrarily.
        return True, min_d, Vec3(0, 1, 0)

    if dist >= min_d:
        return False, 0.0, Vec3(0, 0, 0)

    n_hat = delta * (1.0 / dist)
    penetration = min_d - dist
    return True, penetration, n_hat


def resolve_sphere_sphere(p1, p2):
    """Apply impulse and position correction for a sphere-sphere collision.

    Modifies p1.velocity, p2.velocity, p1.position, p2.position in place.
    Static parcels (is_static=True) are never moved.

    Returns True if a collision was resolved, False if spheres are separating.
    """
    is_col, penetration, n_hat = sphere_sphere_collision(p1, p2)
    if not is_col:
        return False

    # Relative velocity along contact normal
    v_rel = (p1.velocity - p2.velocity).dot(n_hat)

    # Already separating — no impulse needed
    if v_rel <= 0.0:
        return False

    # Restitution: use minimum (conservative: less bouncy wins)
    e = min(p1.restitution, p2.restitution)

    # Impulse magnitude j = -(1+e) × v_rel / (1/m1 + 1/m2)
    inv_m_sum = p1.inv_mass + p2.inv_mass
    if inv_m_sum < 1e-30:
        return False   # Both static — nothing to do

    j = -(1.0 + e) * v_rel / inv_m_sum

    # Apply velocity impulse
    if not p1.is_static:
        p1.velocity = p1.velocity + n_hat * (j * p1.inv_mass)
    if not p2.is_static:
        p2.velocity = p2.velocity - n_hat * (j * p2.inv_mass)

    # Position correction (NOT_PHYSICS — numerical overlap fix)
    # Slop: allow small overlap before correcting (avoids jitter at rest)
    _SLOP = 0.001    # 1 mm
    _PERCENT = 0.80  # correct 80% of penetration per step
    correction = max(penetration - _SLOP, 0.0) * _PERCENT / inv_m_sum

    if not p1.is_static:
        p1.position = p1.position - n_hat * (correction * p1.inv_mass)
    if not p2.is_static:
        p2.position = p2.position + n_hat * (correction * p2.inv_mass)

    return True


# ── Sphere-plane ─────────────────────────────────────────────────────────────

def sphere_plane_collision(parcel, plane_point, plane_normal):
    """Check if a PhysicsParcel (sphere) is penetrating an infinite plane.

    Returns (is_colliding, penetration_depth, contact_normal)
    contact_normal = plane_normal (points away from the solid side).
    """
    n = plane_normal.normalized()
    # Signed distance from plane to center (positive = above plane)
    signed_dist = (parcel.position - plane_point).dot(n)
    penetration = parcel.radius - signed_dist

    if penetration <= 0.0:
        return False, 0.0, n

    return True, penetration, n


def resolve_sphere_plane(parcel, plane_point, plane_normal,
                         plane_restitution=0.5):
    """Apply impulse and position correction for a sphere-plane collision.

    The plane has infinite mass (is_static is implied).
    Modifies parcel.velocity and parcel.position in place.

    Returns True if a collision was resolved.
    """
    is_col, penetration, n = sphere_plane_collision(parcel, plane_point,
                                                    plane_normal)
    if not is_col:
        return False

    v_rel = parcel.velocity.dot(n)
    if v_rel >= 0.0:
        return False   # Already moving away from plane

    # Restitution: use minimum of parcel and plane
    e = min(parcel.restitution, plane_restitution)

    # Impulse: plane has infinite mass → inv_mass_plane = 0
    j = -(1.0 + e) * v_rel / parcel.inv_mass  if parcel.inv_mass > 0 else 0.0

    if not parcel.is_static:
        parcel.velocity = parcel.velocity + n * (j * parcel.inv_mass)

    # Position correction (NOT_PHYSICS)
    _SLOP    = 0.001
    _PERCENT = 0.80
    correction = max(penetration - _SLOP, 0.0) * _PERCENT

    if not parcel.is_static:
        parcel.position = parcel.position + n * correction

    return True

"""
Cone / Frustum — a truncated cone defined by two circular cross-sections.

Tangle-cone intersection: transform to local frame, solve the quadratic
for an infinite cone, then clamp to the height range [0, h].

A frustum (truncated cone) has:
    base_radius (at y=0) and top_radius (at y=h)

Special cases:
    top_radius = 0       → pointed cone
    top_radius = base_r  → cylinder
    any taper in between  → frustum (cups, legs, fingers, trunks)

The math:
    An infinite cone along Y: x² + z² = (r(y))²
    where r(y) = base_radius + (top_radius - base_radius) * (y / h)
         = r0 + (r1 - r0) * y/h

    Substituting ray P(t) = O + tD:
        (Ox + t*Dx)² + (Oz + t*Dz)² = (r0 + slope*(Oy + t*Dy))²

    This expands to a standard quadratic At² + Bt + C = 0.

No external dependencies. Just the quadratic formula.
"""

import math
from .primitives import Vec3, Tangle, Hit
from .ellipsoid import rotation_matrix, _apply, _transpose, IDENTITY


class Cone:
    """A frustum (truncated cone) with arbitrary position and orientation.

    Defined by two circular ends stacked along the local Y axis:
        base (y=0): radius = base_radius
        top (y=h):  radius = top_radius

    Includes flat caps at both ends.

    Args:
        base_center: Vec3 position of the base circle center
        height: distance from base to top along the cone axis
        base_radius: radius at the base
        top_radius: radius at the top (0 = pointed cone)
        rotation: 3-tuple of 3 Vec3 rows (rotation matrix), or None for Y-up
        material: Material object
    """

    def __init__(self, base_center=None, height=1.0,
                 base_radius=0.5, top_radius=0.0,
                 rotation=None, material=None):
        self.base_center = base_center or Vec3(0, 0, 0)
        self.height = float(height)
        self.base_radius = float(base_radius)
        self.top_radius = float(top_radius)
        self.rotation = rotation or IDENTITY
        self.rotation_T = _transpose(self.rotation)
        self.material = material

        # Precompute slope: how radius changes per unit height
        self.slope = (self.top_radius - self.base_radius) / self.height if self.height > 0 else 0

    def intersect(self, tangle, t_min=0.001, t_max=float('inf')):
        """Tangle-frustum intersection.

        Tests three surfaces:
        1. The conical side wall
        2. The base cap (disc at y=0)
        3. The top cap (disc at y=h)

        Returns the nearest valid hit.
        """
        # Transform tangle into local frame
        oc = tangle.origin - self.base_center
        oc_local = _apply(self.rotation_T, oc)
        dir_local = _apply(self.rotation_T, tangle.direction)

        best_hit = None

        # ── Side wall intersection ──
        # Cone equation: x² + z² = (r0 + slope*y)²
        # With ray: P(t) = O + t*D
        #   (Ox + t*Dx)² + (Oz + t*Dz)² = (r0 + slope*(Oy + t*Dy))²

        r0 = self.base_radius
        s = self.slope

        Ox, Oy, Oz = oc_local.x, oc_local.y, oc_local.z
        Dx, Dy, Dz = dir_local.x, dir_local.y, dir_local.z

        # Expand and collect terms for At² + Bt + C = 0
        A = Dx*Dx + Dz*Dz - s*s * Dy*Dy
        B = Ox*Dx + Oz*Dz - s*s * Oy*Dy - s * r0 * Dy
        C = Ox*Ox + Oz*Oz - s*s * Oy*Oy - 2*s*r0*Oy - r0*r0

        # B here is actually half-B (from 2*B*t), so discriminant = B²-AC
        disc = B*B - A*C

        if disc >= 0:
            sqrt_disc = math.sqrt(disc)

            for sign in (-1, 1):
                if abs(A) < 1e-12:
                    # Degenerate case (cylinder-like, A ≈ 0)
                    if abs(B) > 1e-12:
                        t_hit = -C / (2 * B)
                    else:
                        continue
                else:
                    t_hit = (-B + sign * sqrt_disc) / A

                if t_hit < t_min or t_hit > t_max:
                    continue

                # Check height bounds
                hit_local = Vec3(Ox + t_hit * Dx, Oy + t_hit * Dy, Oz + t_hit * Dz)
                y_hit = hit_local.y

                if y_hit < 0 or y_hit > self.height:
                    continue

                # Compute normal on the cone surface
                # The cone surface is f(x,y,z) = x² + z² - (r0 + s*y)² = 0
                # ∇f = (2x, -2s(r0+s*y), 2z)
                r_at_y = r0 + s * y_hit
                normal_local = Vec3(
                    hit_local.x,
                    -s * r_at_y,
                    hit_local.z,
                ).normalized()

                # Transform back to world
                point = tangle.at(t_hit)
                normal_world = _apply(self.rotation, normal_local).normalized()

                if best_hit is None or t_hit < best_hit.t:
                    best_hit = Hit(t_hit, point, normal_world, self.material, self)
                    t_max = t_hit
                break  # first valid hit from sorted pair is nearest

        # ── Cap intersections ──
        # Base cap: y = 0 plane, radius ≤ base_radius
        best_hit = self._intersect_cap(
            tangle, oc_local, dir_local, 0, self.base_radius,
            Vec3(0, -1, 0), t_min, t_max, best_hit
        )
        if best_hit and best_hit.t < t_max:
            t_max = best_hit.t

        # Top cap: y = height plane, radius ≤ top_radius
        if self.top_radius > 0:
            best_hit = self._intersect_cap(
                tangle, oc_local, dir_local, self.height, self.top_radius,
                Vec3(0, 1, 0), t_min, t_max, best_hit
            )

        return best_hit

    def _intersect_cap(self, tangle, oc_local, dir_local, y_plane, cap_radius,
                       normal_local, t_min, t_max, best_hit):
        """Intersect a circular cap at y = y_plane."""
        if abs(dir_local.y) < 1e-12:
            return best_hit  # parallel to cap

        t_hit = (y_plane - oc_local.y) / dir_local.y
        if t_hit < t_min or t_hit > t_max:
            return best_hit

        hit_local = Vec3(
            oc_local.x + t_hit * dir_local.x,
            y_plane,
            oc_local.z + t_hit * dir_local.z,
        )

        # Check if hit is within cap radius
        dist_sq = hit_local.x * hit_local.x + hit_local.z * hit_local.z
        if dist_sq > cap_radius * cap_radius:
            return best_hit

        point = tangle.at(t_hit)
        normal_world = _apply(self.rotation, normal_local).normalized()

        if best_hit is None or t_hit < best_hit.t:
            return Hit(t_hit, point, normal_world, self.material, self)
        return best_hit

    def bounding_box(self):
        max_r = max(self.base_radius, self.top_radius)
        extent = Vec3(max_r, self.height, max_r)
        center = self.base_center + Vec3(0, self.height / 2, 0)
        return (center - extent, center + extent)

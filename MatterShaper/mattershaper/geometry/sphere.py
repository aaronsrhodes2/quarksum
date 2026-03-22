"""
Sphere — the simplest 3D shape.

Tangle-sphere intersection is a quadratic equation.
Derived from first principles: |P(t) - center|² = r²
"""

import math
from .primitives import Vec3, Tangle, Hit


class Sphere:
    """A sphere in 3D space.

    Args:
        center: Vec3 position
        radius: float in scene units (meters by default)
        material: Material object (defines appearance + composition)
    """

    def __init__(self, center=None, radius=1.0, material=None):
        self.center = center or Vec3(0, 0, 0)
        self.radius = radius
        self.material = material

    def intersect(self, tangle, t_min=0.001, t_max=float('inf')):
        """Test tangle intersection.

        Solves: |origin + t*dir - center|² = r²
        Expanding: t² + 2t(dir·oc) + |oc|² - r² = 0
        where oc = origin - center.

        Returns Hit or None.
        """
        oc = tangle.origin - self.center
        a = tangle.direction.dot(tangle.direction)
        b = oc.dot(tangle.direction)
        c = oc.dot(oc) - self.radius * self.radius

        discriminant = b * b - a * c
        if discriminant < 0:
            return None

        sqrt_d = math.sqrt(discriminant)

        # Try the nearer root first
        t = (-b - sqrt_d) / a
        if t < t_min or t > t_max:
            t = (-b + sqrt_d) / a
            if t < t_min or t > t_max:
                return None

        point = tangle.at(t)
        normal = (point - self.center) * (1.0 / self.radius)

        return Hit(t, point, normal, self.material, self)

    def bounding_box(self):
        """Axis-aligned bounding box: (min_corner, max_corner)."""
        r = Vec3(self.radius, self.radius, self.radius)
        return (self.center - r, self.center + r)

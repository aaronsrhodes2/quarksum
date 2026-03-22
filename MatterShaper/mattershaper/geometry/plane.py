"""
Plane — infinite flat surface.

Floors, tables, walls. Tangle-plane intersection is one dot product.
"""

import math
from .primitives import Vec3, Tangle, Hit


class Plane:
    """An infinite plane defined by a point and a normal.

    Args:
        point: Vec3, any point on the plane
        normal: Vec3, surface normal (outward direction)
        material: Material object
    """

    def __init__(self, point=None, normal=None, material=None):
        self.point = point or Vec3(0, 0, 0)
        self.normal = (normal or Vec3(0, 1, 0)).normalized()
        self.material = material

    def intersect(self, tangle, t_min=0.001, t_max=float('inf')):
        """Tangle-plane intersection.

        Plane: (P - point)·normal = 0
        Tangle: P = origin + t*dir

        Substituting: t = (point - origin)·normal / (dir·normal)
        """
        denom = tangle.direction.dot(self.normal)
        if abs(denom) < 1e-10:
            return None  # Tangle parallel to plane

        t = (self.point - tangle.origin).dot(self.normal) / denom
        if t < t_min or t > t_max:
            return None

        point = tangle.at(t)
        # Normal always faces the tangle
        normal = self.normal if denom < 0 else -self.normal

        return Hit(t, point, normal, self.material, self)

    def bounding_box(self):
        # Infinite plane has no finite bounding box
        big = 1e10
        return (Vec3(-big, -big, -big), Vec3(big, big, big))

"""
Ellipsoid — triaxial 3D shape, now with arbitrary orientation.

Tangle-ellipsoid intersection: transform tangle into the ellipsoid's
local coordinate frame (rotate + scale to unit sphere), solve
the sphere equation, transform the normal back.

No external geometry library — just matrix arithmetic.
"""

import math
from .primitives import Vec3, Tangle, Hit


def _rot_x(angle):
    """Rotation matrix around X axis (radians). Returns 3 row Vec3s."""
    c, s = math.cos(angle), math.sin(angle)
    return (Vec3(1, 0, 0), Vec3(0, c, -s), Vec3(0, s, c))

def _rot_y(angle):
    """Rotation matrix around Y axis (radians)."""
    c, s = math.cos(angle), math.sin(angle)
    return (Vec3(c, 0, s), Vec3(0, 1, 0), Vec3(-s, 0, c))

def _rot_z(angle):
    """Rotation matrix around Z axis (radians)."""
    c, s = math.cos(angle), math.sin(angle)
    return (Vec3(c, -s, 0), Vec3(s, c, 0), Vec3(0, 0, 1))

def _mat_mul_rows(A, B):
    """Multiply 3x3 matrices stored as row tuples. A[i] dot B_col[j]."""
    # Extract B columns
    bc0 = Vec3(B[0].x, B[1].x, B[2].x)
    bc1 = Vec3(B[0].y, B[1].y, B[2].y)
    bc2 = Vec3(B[0].z, B[1].z, B[2].z)
    return (
        Vec3(A[0].dot(bc0), A[0].dot(bc1), A[0].dot(bc2)),
        Vec3(A[1].dot(bc0), A[1].dot(bc1), A[1].dot(bc2)),
        Vec3(A[2].dot(bc0), A[2].dot(bc1), A[2].dot(bc2)),
    )

def _transpose(M):
    """Transpose a 3x3 row-tuple matrix."""
    return (
        Vec3(M[0].x, M[1].x, M[2].x),
        Vec3(M[0].y, M[1].y, M[2].y),
        Vec3(M[0].z, M[1].z, M[2].z),
    )

def _apply(M, v):
    """Apply 3x3 matrix (row tuples) to Vec3."""
    return Vec3(M[0].dot(v), M[1].dot(v), M[2].dot(v))

def rotation_matrix(rx=0, ry=0, rz=0):
    """Build a rotation matrix from Euler angles (radians): Rz @ Ry @ Rx."""
    Rx = _rot_x(rx)
    Ry = _rot_y(ry)
    Rz = _rot_z(rz)
    return _mat_mul_rows(Rz, _mat_mul_rows(Ry, Rx))

IDENTITY = (Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))


class Ellipsoid:
    """A triaxial ellipsoid with arbitrary orientation.

    (x/a)² + (y/b)² + (z/c)² = 1 in local frame,
    then rotated by R and translated to center.

    Args:
        center: Vec3 position
        radii: Vec3(a, b, c) semi-axis lengths
        rotation: tuple of 3 Vec3 rows (rotation matrix), or None for axis-aligned
        material: Material object
    """

    def __init__(self, center=None, radii=None, rotation=None, material=None):
        self.center = center or Vec3(0, 0, 0)
        self.radii = radii or Vec3(1, 1, 1)
        self.rotation = rotation or IDENTITY
        self.rotation_T = _transpose(self.rotation)
        self.material = material

    def intersect(self, tangle, t_min=0.001, t_max=float('inf')):
        """Tangle-ellipsoid intersection with rotation support.

        Strategy:
        1. Translate tangle to ellipsoid-centered coords
        2. Rotate tangle into ellipsoid's local frame (R^T)
        3. Scale to unit sphere
        4. Solve sphere intersection
        5. Transform normal back: R @ local_normal
        """
        # Step 1: translate
        oc = tangle.origin - self.center

        # Step 2: rotate into local frame
        oc_local = _apply(self.rotation_T, oc)
        dir_local = _apply(self.rotation_T, tangle.direction)

        # Step 3: scale to unit sphere
        inv_r = Vec3(1.0/self.radii.x, 1.0/self.radii.y, 1.0/self.radii.z)
        oc_s = Vec3(oc_local.x * inv_r.x, oc_local.y * inv_r.y, oc_local.z * inv_r.z)
        dir_s = Vec3(dir_local.x * inv_r.x, dir_local.y * inv_r.y, dir_local.z * inv_r.z)

        # Step 4: solve |oc_s + t * dir_s|² = 1
        a = dir_s.dot(dir_s)
        b = oc_s.dot(dir_s)
        c = oc_s.dot(oc_s) - 1.0

        discriminant = b * b - a * c
        if discriminant < 0:
            return None

        sqrt_d = math.sqrt(discriminant)

        t = (-b - sqrt_d) / a
        if t < t_min or t > t_max:
            t = (-b + sqrt_d) / a
            if t < t_min or t > t_max:
                return None

        point = tangle.at(t)

        # Step 5: normal in local frame, then rotate back
        p_local = _apply(self.rotation_T, point - self.center)
        normal_local = Vec3(
            p_local.x / (self.radii.x * self.radii.x),
            p_local.y / (self.radii.y * self.radii.y),
            p_local.z / (self.radii.z * self.radii.z),
        )
        # Rotate normal back to world frame
        normal_world = _apply(self.rotation, normal_local).normalized()

        return Hit(t, point, normal_world, self.material, self)

    def bounding_box(self):
        r = self.radii
        # Conservative AABB for rotated ellipsoid
        max_r = max(r.x, r.y, r.z)
        extent = Vec3(max_r, max_r, max_r)
        return (self.center - extent, self.center + extent)

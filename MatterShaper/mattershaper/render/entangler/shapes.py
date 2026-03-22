"""
Entangler Quadric Shapes — analytic geometry, zero shared code.

Each shape knows:
  - Its center, size, orientation
  - Its material (physics-aware)
  - How to generate surface nodes (push rendering)

No intersect() method. No ray testing. These shapes don't answer
questions — they speak when activated.
"""

import math
from .vec import Vec3


# ── Rotation matrices ─────────────────────────────────────────────
# Pure trig. Written from scratch.

def _rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return ((1, 0, 0), (0, c, -s), (0, s, c))

def _rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, 0, s), (0, 1, 0), (-s, 0, c))

def _rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))

def _mat_mul(A, B):
    """Multiply two 3x3 matrices stored as tuple-of-tuples."""
    result = []
    for i in range(3):
        row = []
        for j in range(3):
            val = sum(A[i][k] * B[k][j] for k in range(3))
            row.append(val)
        result.append(tuple(row))
    return tuple(result)

def _apply_mat(M, v):
    """Apply 3x3 matrix to Vec3."""
    return Vec3(
        M[0][0]*v.x + M[0][1]*v.y + M[0][2]*v.z,
        M[1][0]*v.x + M[1][1]*v.y + M[1][2]*v.z,
        M[2][0]*v.x + M[2][1]*v.y + M[2][2]*v.z,
    )

def rotation_matrix(rx=0, ry=0, rz=0):
    """Euler rotation Rz @ Ry @ Rx."""
    return _mat_mul(_rot_z(rz), _mat_mul(_rot_y(ry), _rot_x(rx)))

IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


# ── Shapes ────────────────────────────────────────────────────────

class EntanglerSphere:
    """A sphere. Knows its center, radius, material.

    fill_volume=True: the entangler generates VolumeNodes filling the interior
    for Beer-Lambert volumetric rendering AND physics simulation (mass, gravity).
    fill_volume=False (default): surface-only rendering, existing behavior.
    """

    def __init__(self, center=None, radius=1.0, material=None, fill_volume=False):
        self.center = center or Vec3(0, 0, 0)
        self.radius = radius
        self.material = material
        self.shape_type = 'sphere'
        self.fill_volume = fill_volume


class EntanglerEllipsoid:
    """A triaxial ellipsoid with arbitrary orientation.
    (x/a)² + (y/b)² + (z/c)² = 1 in local frame.

    fill_volume=True: volumetric Beer-Lambert fill (same as EntanglerSphere).
    """

    def __init__(self, center=None, radii=None, rotation=None, material=None,
                 fill_volume=False):
        self.center = center or Vec3(0, 0, 0)
        self.radii = radii or Vec3(1, 1, 1)
        self.rotation = rotation or IDENTITY
        self.material = material
        self.shape_type = 'ellipsoid'
        self.fill_volume = fill_volume


class EntanglerTorus:
    """A torus (donut) in the XZ-plane (Y=0 plane) of local space.

    Parametric surface:
        position(θ, φ) = center + R(θ) + r(θ, φ)
        where R(θ) = (R_major cosθ, 0, R_major sinθ)  — major circle
              r(θ, φ) = (r_minor cosφ cosθ, r_minor sinφ, r_minor cosφ sinθ)

    Normal (outward from tube centre):
        n(θ, φ) = (cosθ cosφ, sinφ, sinθ cosφ)

    Surface area: 4π² R_major r_minor

    Args:
        center:   Vec3, world position of torus centre
        R_major:  float, major radius (centre of tube to centre of torus)
        r_minor:  float, minor radius (tube cross-section radius)
        rotation: 3×3 tuple-of-tuples rotation matrix (default: IDENTITY — torus in XZ plane)
        material: Material
    """

    def __init__(self, center=None, R_major=1.0, r_minor=0.2,
                 rotation=None, material=None):
        self.center   = center or Vec3(0, 0, 0)
        self.R_major  = R_major
        self.r_minor  = r_minor
        self.rotation = rotation or IDENTITY
        self.material = material
        self.shape_type = 'torus'
        self.fill_volume = False   # torus is always surface-only

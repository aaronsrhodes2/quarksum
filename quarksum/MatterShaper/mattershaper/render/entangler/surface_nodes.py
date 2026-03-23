"""
Entangler Surface Nodes — matter that knows where it is.

Each node is a point on an analytic surface with:
  - Position (where it exists)
  - Normal (how it faces)
  - Material (what it's made of)

Generation uses Fibonacci spiral on S² — proven uniform
distribution via the golden angle (irrational rotation).
No mesh. No approximation. Parametric quadric solved directly.

Zero shared code with any ray tracer.
"""

import math
from .vec import Vec3
from .shapes import _apply_mat


class SurfaceNode:
    """A point on a surface that knows what it is.

    Not a vertex. Not a sample. A piece of matter that exists at
    this location, has this orientation, and is made of this material.
    """
    __slots__ = ('position', 'normal', 'material')

    def __init__(self, position, normal, material):
        self.position = position
        self.normal = normal.normalized()
        self.material = material


# ── Golden angle ─────────────────────────────────────────────────
# π(3 − √5) radians. This is the exact angle that maximizes
# angular separation in a spiral on S². Proven property of the
# golden ratio — successive points never align.

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))


def _generate_sphere_nodes(sphere, density):
    """Generate surface nodes on a sphere using Fibonacci spiral.

    Node count = surface_area × density (exact 4πr²).
    Distribution: Fibonacci spiral — proven nearly-uniform on S².
    Normal: radial direction (exact for sphere).
    """
    area = 4.0 * math.pi * sphere.radius * sphere.radius
    n = max(int(area * density), 20)

    nodes = []
    for i in range(n):
        # Fibonacci spiral: uniform spacing on [-1, 1]
        y = 1.0 - (2.0 * i / (n - 1))
        r_ring = math.sqrt(max(0.0, 1.0 - y * y))
        theta = GOLDEN_ANGLE * i

        x = r_ring * math.cos(theta)
        z = r_ring * math.sin(theta)

        # Scale to sphere radius + translate to center
        pos = Vec3(
            sphere.center.x + x * sphere.radius,
            sphere.center.y + y * sphere.radius,
            sphere.center.z + z * sphere.radius,
        )
        # Normal = radial direction (unit vector, exact for sphere)
        normal = Vec3(x, y, z)

        nodes.append(SurfaceNode(pos, normal, sphere.material))

    return nodes


def _generate_ellipsoid_nodes(ellipsoid, density):
    """Generate surface nodes on an ellipsoid.

    Strategy: Fibonacci spiral on unit sphere → scale by radii.
    Normal: ∇((x/a)² + (y/b)² + (z/c)²) = (2x/a², 2y/b², 2z/c²).
    This is exact calculus — gradient of the implicit surface.

    Surface area: Knud Thomsen approximation (p=1.6075).
    This is the ONE approximation — used only for node COUNT,
    not for positions or normals.
    """
    rx = ellipsoid.radii.x
    ry = ellipsoid.radii.y
    rz = ellipsoid.radii.z

    # Knud Thomsen surface area (for node count only)
    p = 1.6075
    ap, bp, cp = rx ** p, ry ** p, rz ** p
    area = 4.0 * math.pi * ((ap * bp + ap * cp + bp * cp) / 3.0) ** (1.0 / p)

    n = max(int(area * density), 20)
    nodes = []

    for i in range(n):
        y_unit = 1.0 - (2.0 * i / (n - 1))
        r_ring = math.sqrt(max(0.0, 1.0 - y_unit * y_unit))
        theta = GOLDEN_ANGLE * i

        x_unit = r_ring * math.cos(theta)
        z_unit = r_ring * math.sin(theta)

        # Scale unit sphere point to ellipsoid in local frame
        x_local = x_unit * rx
        y_local = y_unit * ry
        z_local = z_unit * rz

        # Rotate to world frame + translate
        local_pos = Vec3(x_local, y_local, z_local)
        world_offset = _apply_mat(ellipsoid.rotation, local_pos)
        pos = ellipsoid.center + world_offset

        # Normal: exact gradient of ellipsoid implicit equation
        # ∇f = (2x/a², 2y/b², 2z/c²) — the 2's cancel in normalization
        normal_local = Vec3(
            x_local / (rx * rx),
            y_local / (ry * ry),
            z_local / (rz * rz),
        )
        normal_world = _apply_mat(ellipsoid.rotation, normal_local).normalized()

        nodes.append(SurfaceNode(pos, normal_world, ellipsoid.material))

    return nodes


def generate_surface_nodes(shape, density=100):
    """Generate surface nodes for any supported quadric.

    Args:
        shape: EntanglerSphere or EntanglerEllipsoid
        density: nodes per unit area (higher = finer detail)

    Returns:
        list of SurfaceNode
    """
    if shape.shape_type == 'sphere':
        return _generate_sphere_nodes(shape, density)
    elif shape.shape_type == 'ellipsoid':
        return _generate_ellipsoid_nodes(shape, density)
    else:
        raise ValueError(
            f"Entangler: unsupported shape type '{shape.shape_type}'"
        )

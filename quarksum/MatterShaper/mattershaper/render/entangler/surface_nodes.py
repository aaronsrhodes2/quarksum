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


def _generate_box_nodes(box, density):
    """Surface nodes on a box — uniform grid on each of 6 faces."""
    hx, hy, hz = box.half.x, box.half.y, box.half.z
    # Each face: (face-centre direction, u-axis, v-axis, half-u, half-v)
    faces = [
        (Vec3( 1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1), hy, hz),
        (Vec3(-1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1), hy, hz),
        (Vec3( 0, 1, 0), Vec3(1, 0, 0), Vec3(0, 0, 1), hx, hz),
        (Vec3( 0,-1, 0), Vec3(1, 0, 0), Vec3(0, 0, 1), hx, hz),
        (Vec3( 0, 0, 1), Vec3(1, 0, 0), Vec3(0, 1, 0), hx, hy),
        (Vec3( 0, 0,-1), Vec3(1, 0, 0), Vec3(0, 1, 0), hx, hy),
    ]
    nodes = []
    for n_l, u_ax, v_ax, hu, hv in faces:
        n_side = max(2, int(math.sqrt(4 * hu * hv * density)))
        fc = Vec3(n_l.x * hx, n_l.y * hy, n_l.z * hz)
        for i in range(n_side):
            for j in range(n_side):
                u = -hu + 2 * hu * (i + 0.5) / n_side
                v = -hv + 2 * hv * (j + 0.5) / n_side
                local = Vec3(
                    fc.x + u_ax.x * u + v_ax.x * v,
                    fc.y + u_ax.y * u + v_ax.y * v,
                    fc.z + u_ax.z * u + v_ax.z * v,
                )
                world_pos = box.center + _apply_mat(box.rotation, local)
                world_n   = _apply_mat(box.rotation, n_l).normalized()
                nodes.append(SurfaceNode(world_pos, world_n, box.material))
    return nodes


def _generate_cylinder_nodes(cyl, density):
    """Surface nodes on a cylinder — side wall + two end-caps."""
    r, h = cyl.radius, cyl.height
    nodes = []
    # Side wall
    n_t = max(8, int(2 * math.pi * r * math.sqrt(density)))
    n_y = max(2, int(h * math.sqrt(density)))
    for i in range(n_t):
        theta = 2 * math.pi * (i + 0.5) / n_t
        ct, st = math.cos(theta), math.sin(theta)
        for j in range(n_y):
            y_l = -h / 2 + h * (j + 0.5) / n_y
            local   = Vec3(r * ct, y_l, r * st)
            normal_l = Vec3(ct, 0, st)
            world_pos = cyl.center + _apply_mat(cyl.rotation, local)
            world_n   = _apply_mat(cyl.rotation, normal_l).normalized()
            nodes.append(SurfaceNode(world_pos, world_n, cyl.material))
    # End caps
    n_cap = max(8, int(math.pi * r * r * density))
    for sign, normal_l in ((1, Vec3(0, 1, 0)), (-1, Vec3(0, -1, 0))):
        y_l = sign * h / 2
        for k in range(n_cap):
            rad = r * math.sqrt((k + 0.5) / n_cap)
            ang = GOLDEN_ANGLE * k
            local = Vec3(rad * math.cos(ang), y_l, rad * math.sin(ang))
            world_pos = cyl.center + _apply_mat(cyl.rotation, local)
            world_n   = _apply_mat(cyl.rotation, normal_l).normalized()
            nodes.append(SurfaceNode(world_pos, world_n, cyl.material))
    return nodes


def _generate_plane_nodes(plane, density):
    """Surface nodes on a finite rectangular XZ patch (normal = +Y local)."""
    hx, hz = plane.half_x, plane.half_z
    n_side = max(2, int(math.sqrt(4 * hx * hz * density)))
    normal_l = Vec3(0, 1, 0)
    nodes = []
    for i in range(n_side):
        for j in range(n_side):
            x = -hx + 2 * hx * (i + 0.5) / n_side
            z = -hz + 2 * hz * (j + 0.5) / n_side
            local = Vec3(x, 0, z)
            world_pos = plane.center + _apply_mat(plane.rotation, local)
            world_n   = _apply_mat(plane.rotation, normal_l).normalized()
            nodes.append(SurfaceNode(world_pos, world_n, plane.material))
    return nodes


def _generate_torus_nodes(torus, density):
    """Surface nodes on a torus — analytic parametric surface."""
    R, r = torus.major_radius, torus.minor_radius
    area = 4 * math.pi * math.pi * R * r
    n_theta = max(16, int(2 * math.pi * R * math.sqrt(density)))
    n_phi   = max(8,  int(2 * math.pi * r * math.sqrt(density)))
    nodes = []
    for i in range(n_theta):
        theta = 2 * math.pi * (i + 0.5) / n_theta
        ct, st = math.cos(theta), math.sin(theta)
        for j in range(n_phi):
            phi = 2 * math.pi * (j + 0.5) / n_phi
            cp, sp = math.cos(phi), math.sin(phi)
            local    = Vec3((R + r * cp) * ct, r * sp, (R + r * cp) * st)
            normal_l = Vec3(ct * cp, sp, st * cp)
            world_pos = torus.center + _apply_mat(torus.rotation, local)
            world_n   = _apply_mat(torus.rotation, normal_l).normalized()
            nodes.append(SurfaceNode(world_pos, world_n, torus.material))
    return nodes


def generate_surface_nodes(shape, density=100):
    """Generate surface nodes for any supported shape.

    Args:
        shape: any Entangler shape object
        density: nodes per unit area

    Returns:
        list of SurfaceNode
    """
    if shape.shape_type == 'sphere':
        return _generate_sphere_nodes(shape, density)
    elif shape.shape_type == 'ellipsoid':
        return _generate_ellipsoid_nodes(shape, density)
    elif shape.shape_type == 'box':
        return _generate_box_nodes(shape, density)
    elif shape.shape_type == 'cylinder':
        return _generate_cylinder_nodes(shape, density)
    elif shape.shape_type == 'plane':
        return _generate_plane_nodes(shape, density)
    elif shape.shape_type == 'torus':
        return _generate_torus_nodes(shape, density)
    else:
        raise ValueError(
            f"Entangler: unsupported shape type '{shape.shape_type}'"
        )

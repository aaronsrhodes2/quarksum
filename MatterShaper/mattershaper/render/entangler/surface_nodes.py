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


def _generate_torus_nodes(torus, density):
    """Generate surface nodes on a torus.

    Parameterisation (XZ-plane torus before rotation):
        θ ∈ [0, 2π)  — angle around the major circle (in XZ plane)
        φ ∈ [0, 2π)  — angle around the tube cross-section

        position(θ, φ) = ((R + r cosφ) cosθ,  r sinφ,  (R + r cosφ) sinθ)
        normal(θ, φ)   = (cosφ cosθ,            sinφ,   cosφ sinθ)

    Area element:  dA = r (R + r cosφ) dθ dφ
    Surface area:  4π² R r

    Node distribution: golden-angle Fibonacci on the (θ, φ) parameter square,
    corrected for the area element — φ is sampled from a look-up table so each
    node covers equal area.  This is exact; no mesh, no quadrature.

    Normal: exact from the parametric gradient — no approximation.
    """
    R = torus.R_major
    r = torus.r_minor

    # Surface area for node count
    area = 4.0 * math.pi * math.pi * R * r
    n    = max(int(area * density), 20)

    # Pre-build CDF for φ so that uniform sampling in CDF-space → area-uniform φ.
    # dA ∝ (R + r cosφ) — integrates to 2πR per full revolution.
    # CDF(φ) = (R φ + r sinφ) / (2πR).  Inverted by bisection below.
    # (For R >> r, this is nearly uniform in φ — the correction is small but exact.)
    N_CDF   = 4096
    phi_arr = [2.0 * math.pi * k / N_CDF for k in range(N_CDF + 1)]
    cdf_arr = [(R * p + r * math.sin(p)) / (2.0 * math.pi * R) for p in phi_arr]

    def _cdf_inv(u):
        """Invert CDF by bisection — exact."""
        lo, hi = 0, N_CDF
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if cdf_arr[mid] < u:
                lo = mid
            else:
                hi = mid
        # Linear interpolation in last interval
        c0, c1 = cdf_arr[lo], cdf_arr[hi]
        if c1 == c0:
            return phi_arr[lo]
        t = (u - c0) / (c1 - c0)
        return phi_arr[lo] + t * (phi_arr[hi] - phi_arr[lo])

    rot   = torus.rotation
    cx, cy, cz = torus.center.x, torus.center.y, torus.center.z
    nodes = []

    # Golden-angle Fibonacci on unit square → mapped through area-CDF for φ
    phi_golden = (1.0 + math.sqrt(5.0)) / 2.0
    for i in range(n):
        u_theta = i / n                           # uniform in θ
        u_phi   = (i / phi_golden) % 1.0          # golden-angle in φ-CDF space

        theta = 2.0 * math.pi * u_theta
        phi   = _cdf_inv(u_phi)

        cos_t, sin_t = math.cos(theta), math.sin(theta)
        cos_p, sin_p = math.cos(phi),   math.sin(phi)

        # Local position (XZ-plane torus)
        lx = (R + r * cos_p) * cos_t
        ly =       r * sin_p
        lz = (R + r * cos_p) * sin_t

        # Local normal (exact from parametric gradient)
        nx_l = cos_p * cos_t
        ny_l = sin_p
        nz_l = cos_p * sin_t

        # Rotate to world frame + translate
        local_p = Vec3(lx, ly, lz)
        local_n = Vec3(nx_l, ny_l, nz_l)
        world_p = _apply_mat(rot, local_p)
        world_n = _apply_mat(rot, local_n)

        pos    = Vec3(cx + world_p.x, cy + world_p.y, cz + world_p.z)
        normal = world_n  # already unit length (cos²+sin²=1)

        nodes.append(SurfaceNode(pos, normal, torus.material))

    return nodes


def generate_surface_nodes(shape, density=100):
    """Generate surface nodes for any supported quadric.

    Args:
        shape: EntanglerSphere, EntanglerEllipsoid, or EntanglerTorus
        density: nodes per unit area (higher = finer detail).
                 If the shape carries a ``density_override`` attribute, that
                 value replaces the caller-supplied density.  This lets
                 per-shape density be set without modifying the engine call.

    Returns:
        list of SurfaceNode
    """
    density = getattr(shape, 'density_override', None) or density

    if shape.shape_type == 'sphere':
        return _generate_sphere_nodes(shape, density)
    elif shape.shape_type == 'ellipsoid':
        return _generate_ellipsoid_nodes(shape, density)
    elif shape.shape_type == 'torus':
        return _generate_torus_nodes(shape, density)
    else:
        raise ValueError(
            f"Entangler: unsupported shape type '{shape.shape_type}'"
        )

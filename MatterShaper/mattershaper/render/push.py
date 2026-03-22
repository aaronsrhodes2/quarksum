"""
Push Renderer — Matter draws itself.

DEPRECATED — first-generation renderer. Single-pass, surface-only.
  Use mattershaper.render.entangler.engine.entangle() instead.
  The entangler is a strict superset: same push architecture, plus
  Beer-Lambert volume rendering, shadow maps, and foreshortening-corrected
  splats.

  Still used by:
    - mattershaper/shaper.py  (the fluent MatterShaper API)
    - render_push_test.py     (legacy test script)

  PushCamera and PushLight here are identical to the canonical versions
  in mattershaper.render.entangler.projection / .illumination.
  New code should import from there.

Architecture:
  1. Light source activates surface nodes
  2. Each surface node computes its response (color from material + normal)
  3. Surface nodes project themselves onto the pixel grid
  4. Depth buffer resolves occlusion (closest node wins)

No Ray objects. No intersection tests. No tracing calls.
The matter is the subject, not the object.

"The quark pixels fire from the outside."
"""

import math
from ..geometry.primitives import Vec3


# ── Surface Node ──────────────────────────────────────────────────
# A point on an analytic surface that knows its position, normal,
# and material. This is the fundamental unit of push rendering.
# It's the "quark pixel" — the matter element that talks to light.

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


# ── Surface Node Generation ───────────────────────────────────────
# Sample points on analytic quadric surfaces. The density parameter
# controls how many nodes per unit area. Higher = finer detail.
#
# No mesh. We solve the parametric quadric equation directly.

def _generate_sphere_nodes(sphere, density):
    """Generate surface nodes on a sphere using Fibonacci spiral.

    The Fibonacci spiral gives nearly-uniform distribution on S²
    with no clustering at poles. It's a FIRST_PRINCIPLES geometric
    construction — the golden angle ensures maximal angular separation.
    """
    # Target node count from surface area × density
    area = 4.0 * math.pi * sphere.radius ** 2
    n = max(int(area * density), 20)

    nodes = []
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))  # ~2.3999 rad

    for i in range(n):
        # Fibonacci spiral on unit sphere
        y = 1.0 - (2.0 * i / (n - 1))  # -1 to 1
        r_ring = math.sqrt(max(0, 1.0 - y * y))
        theta = golden_angle * i

        x = r_ring * math.cos(theta)
        z = r_ring * math.sin(theta)

        # Scale to actual sphere
        pos = Vec3(
            sphere.center.x + x * sphere.radius,
            sphere.center.y + y * sphere.radius,
            sphere.center.z + z * sphere.radius,
        )
        # Normal = outward radial direction
        normal = Vec3(x, y, z)  # already unit length

        nodes.append(SurfaceNode(pos, normal, sphere.material))

    return nodes


def _generate_ellipsoid_nodes(ellipsoid, density):
    """Generate surface nodes on an ellipsoid.

    Strategy: Fibonacci spiral on unit sphere, then scale by radii.
    Normal is the gradient of (x/a)²+(y/b)²+(z/c)²=1, which is
    (2x/a², 2y/b², 2z/c²) — pure calculus, no approximation.
    """
    from ..geometry.ellipsoid import _apply

    rx, ry, rz = ellipsoid.radii.x, ellipsoid.radii.y, ellipsoid.radii.z

    # Approximate surface area (Knud Thomsen formula, geometric)
    p = 1.6075
    ap = rx ** p
    bp = ry ** p
    cp = rz ** p
    area = 4.0 * math.pi * ((ap*bp + ap*cp + bp*cp) / 3.0) ** (1.0/p)

    n = max(int(area * density), 20)
    nodes = []
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))

    for i in range(n):
        y_unit = 1.0 - (2.0 * i / (n - 1))
        r_ring = math.sqrt(max(0, 1.0 - y_unit * y_unit))
        theta = golden_angle * i

        x_unit = r_ring * math.cos(theta)
        z_unit = r_ring * math.sin(theta)

        # Scale to ellipsoid in local frame
        x_local = x_unit * rx
        y_local = y_unit * ry
        z_local = z_unit * rz

        # Rotate to world frame
        local_pos = Vec3(x_local, y_local, z_local)
        world_offset = _apply(ellipsoid.rotation, local_pos)
        pos = ellipsoid.center + world_offset

        # Normal: gradient of ellipsoid equation in local frame
        # ∇((x/a)²+(y/b)²+(z/c)²) = (2x/a², 2y/b², 2z/c²)
        normal_local = Vec3(
            x_local / (rx * rx),
            y_local / (ry * ry),
            z_local / (rz * rz),
        )
        # Rotate normal to world frame
        normal_world = _apply(ellipsoid.rotation, normal_local).normalized()

        nodes.append(SurfaceNode(pos, normal_world, ellipsoid.material))

    return nodes


def generate_surface_nodes(shape, density=100):
    """Generate surface nodes for any supported quadric.

    Args:
        shape: Sphere, Ellipsoid, Cone, etc.
        density: nodes per unit area (higher = finer)

    Returns:
        list of SurfaceNode
    """
    from ..geometry.sphere import Sphere
    from ..geometry.ellipsoid import Ellipsoid

    if isinstance(shape, Sphere):
        return _generate_sphere_nodes(shape, density)
    elif isinstance(shape, Ellipsoid):
        return _generate_ellipsoid_nodes(shape, density)
    else:
        raise ValueError(f"Push renderer: unsupported shape type {type(shape).__name__}")


# ── Camera (Projection) ──────────────────────────────────────────
# The pixel grid is just a bucket array. Nodes project themselves
# onto it via perspective division. No rays fired.

class PushCamera:
    """A passive receiver — a grid of pixel buckets.

    The camera doesn't DO anything. It's a coordinate frame and
    a pixel grid. The surface nodes project onto it.
    """

    def __init__(self, pos, look_at, width, height, fov=60):
        self.pos = pos
        self.look_at = look_at
        self.width = width
        self.height = height
        self.fov = fov

        # Build camera basis vectors
        self.forward = (look_at - pos).normalized()
        world_up = Vec3(0, 1, 0)

        # Handle degenerate case (looking straight up/down)
        if abs(self.forward.dot(world_up)) > 0.999:
            world_up = Vec3(0, 0, 1)

        self.right = self.forward.cross(world_up).normalized()
        self.up = self.right.cross(self.forward).normalized()

        # Perspective projection parameters
        self.aspect = width / height
        self.tan_half_fov = math.tan(math.radians(fov / 2.0))


def project_node(world_pos, camera):
    """Project a 3D point onto the pixel grid.

    Pure perspective math. No rays.

    Args:
        world_pos: Vec3 position in world space
        camera: PushCamera

    Returns:
        (px, py) pixel coordinates, or None if behind camera or off-screen
    """
    # Vector from camera to point
    to_point = world_pos - camera.pos

    # Project onto camera basis
    z = to_point.dot(camera.forward)  # depth
    if z <= 0.001:
        return None  # behind camera

    x = to_point.dot(camera.right)
    y = to_point.dot(camera.up)

    # Perspective division
    ndc_x = x / (z * camera.tan_half_fov * camera.aspect)
    ndc_y = y / (z * camera.tan_half_fov)

    # NDC [-1, 1] → pixel [0, width/height]
    px = (ndc_x + 1.0) * 0.5 * camera.width
    py = (1.0 - ndc_y) * 0.5 * camera.height  # flip Y (screen Y is down)

    # Bounds check
    if px < 0 or px >= camera.width or py < 0 or py >= camera.height:
        return None

    return (px, py)


# ── Illumination ──────────────────────────────────────────────────
# The light source is the trigger. It activates surface nodes.
# Each node computes its own response from its material + normal.

class PushLight:
    """An artificial light source — the activation signal.

    The light doesn't trace rays. It's a position and intensity.
    Surface nodes compute their own response to it.
    """
    def __init__(self, pos, intensity=1.0, color=None):
        self.pos = pos
        self.intensity = intensity
        self.color = color or Vec3(1, 1, 1)


def illuminate_node(node, light):
    """A surface node computes its response to a light source.

    Lambertian diffuse + simple specular highlight.
    The node does this itself — the light just provides direction + intensity.

    Args:
        node: SurfaceNode
        light: PushLight

    Returns:
        Vec3 color response
    """
    # Direction from node to light
    to_light = (light.pos - node.position)
    dist = to_light.length()
    if dist < 1e-10:
        return Vec3(0, 0, 0)
    to_light_dir = to_light * (1.0 / dist)

    # Lambertian diffuse: how much does this surface face the light?
    n_dot_l = max(0.0, node.normal.dot(to_light_dir))

    # Material color × light intensity × angular factor
    mat_color = node.material.color
    diff = mat_color * (n_dot_l * light.intensity)

    # Ambient term (minimal — so we can see shape even in shadow)
    ambient = mat_color * 0.08

    # Total response
    return (diff + ambient).clamp(0, 1)


# ── Push Render ───────────────────────────────────────────────────
# The full pipeline: generate nodes → illuminate → project → resolve

def push_render(objects, camera, light, density=200, bg_color=None):
    """Render a scene by push projection. No ray tracing.

    1. For each object, generate surface nodes
    2. Each node computes its illumination response
    3. Each node projects itself onto the pixel grid
    4. Depth buffer resolves occlusion (closest wins)

    Args:
        objects: list of geometry objects (Sphere, Ellipsoid, etc.)
        camera: PushCamera
        light: PushLight
        density: surface node density (nodes per unit area)
        bg_color: Vec3 background color (default: dark gray)

    Returns:
        2D list of Vec3 colors [height][width]
    """
    bg = bg_color or Vec3(0.12, 0.12, 0.14)

    # Initialize pixel buffer and depth buffer
    pixels = [[Vec3(bg.x, bg.y, bg.z) for _ in range(camera.width)]
              for _ in range(camera.height)]
    depth = [[float('inf') for _ in range(camera.width)]
             for _ in range(camera.height)]

    # For each object: generate nodes, illuminate, project
    for obj in objects:
        nodes = generate_surface_nodes(obj, density)

        for node in nodes:
            # Node computes its color response to the light
            color = illuminate_node(node, light)

            # Node projects itself onto the pixel grid
            proj = project_node(node.position, camera)
            if proj is None:
                continue

            px, py = proj
            ix = int(px)
            iy = int(py)

            # Bounds safety
            if ix < 0 or ix >= camera.width or iy < 0 or iy >= camera.height:
                continue

            # Depth test with splatting: each node covers a footprint derived
            # from its Voronoi cell area projected through the surface normal.
            z = (node.position - camera.pos).dot(camera.forward)

            # Foreshortening-corrected circular splat.
            # Each node owns Voronoi area = 1/density on the surface.
            # Frontal cell radius: cell_r_front = sqrt(1/(π×density)).
            # Tilted by θ from camera direction, the projected area scales by
            # 1/cos(θ): projected_r = cell_r_front / sqrt(cos_theta).
            # Nodes near the limb (cos_theta→0) need larger splats because the
            # same surface patch covers more pixels when seen at a grazing angle.
            focal_px = camera.width / (2.0 * camera.tan_half_fov * camera.aspect)
            cell_r_front = math.sqrt(1.0 / (math.pi * density)) if density > 0 else 0.1
            to_cam = (camera.pos - node.position).normalized()
            cos_theta = max(0.05, node.normal.dot(to_cam))
            proj_r = cell_r_front / math.sqrt(cos_theta)
            # NOT_PHYSICS — sacrificed for The Edge.
            # Mutant variable: overlap_factor = 1.2
            # Physics says proj_r is the exact foreshortening-corrected Voronoi
            # cell radius. The pixel grid is discrete; circles of exact radius
            # leave diagonal corner gaps at the pixel boundary. 1.2× overlap
            # closes those gaps. This fudge lives ONLY at the pixel-grid edge.
            # Cap at 12px: prevents edge-on nodes from blotching the background.
            splat_r = min(12, max(1, math.ceil(proj_r * focal_px / z * 1.2)))

            for sy in range(-splat_r, splat_r + 1):
                for sx in range(-splat_r, splat_r + 1):
                    if sx * sx + sy * sy > splat_r * splat_r:
                        continue
                    px2 = ix + sx
                    py2 = iy + sy
                    if 0 <= px2 < camera.width and 0 <= py2 < camera.height:
                        if z < depth[py2][px2]:
                            depth[py2][px2] = z
                            pixels[py2][px2] = color

    return pixels


# ── PNG Output ────────────────────────────────────────────────────
# Write pixel buffer to PNG. Pure Python, no PIL.

def _write_png(pixels, filepath):
    """Write pixel buffer to PNG file.

    Uses raw PPM as intermediate → convert with system tools if available,
    otherwise writes PPM directly.
    """
    height = len(pixels)
    width = len(pixels[0])

    # Write as PPM (simplest image format — no dependencies)
    ppm_path = filepath.rsplit('.', 1)[0] + '.ppm'
    with open(ppm_path, 'wb') as f:
        f.write(f"P6\n{width} {height}\n255\n".encode())
        for row in pixels:
            for p in row:
                r, g, b = p.to_rgb()
                f.write(bytes([r, g, b]))

    # Try to convert to PNG
    import subprocess
    try:
        subprocess.run(['convert', ppm_path, filepath],
                      capture_output=True, timeout=10)
        import os
        if os.path.exists(filepath):
            os.remove(ppm_path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # ImageMagick not available — keep PPM
        import os
        if filepath != ppm_path:
            os.rename(ppm_path, filepath)


def push_render_to_file(objects, camera, light, filepath,
                         density=200, bg_color=None):
    """Render and save to file."""
    pixels = push_render(objects, camera, light, density, bg_color)
    _write_png(pixels, filepath)
    return filepath

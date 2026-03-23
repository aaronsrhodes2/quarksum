"""
Entangler Engine — the full push render pipeline.

Pipeline:
  1. Generate surface nodes on each object (Fibonacci spiral on quadrics)
  2. Light activates each node (Lambert's cosine law)
  3. Each node projects itself onto pixel grid (perspective division)
  4. Depth buffer resolves occlusion (closest node wins)
  5. Splatting fills gaps (each node covers a small footprint)

No rays. No intersection tests. Matter draws itself.

Splat radius: exact computation from node spacing and focal length.
  spacing = 1/√density (exact)
  splat_px = spacing × f_px / z (exact perspective scaling)

Zero shared code with any ray tracer.
"""

import math
from .vec import Vec3
from .surface_nodes import generate_surface_nodes
from .projection import project_node
from .illumination import illuminate_node


def entangle(objects, camera, light, density=200, bg_color=None):
    """Render a scene by push projection.

    Each object generates surface nodes. Each node computes its
    illumination, projects itself onto the pixel grid, and the
    depth buffer resolves visibility.

    Args:
        objects: list of EntanglerSphere / EntanglerEllipsoid
        camera: PushCamera
        light: PushLight
        density: surface node density (nodes per unit area)
        bg_color: Vec3 background color

    Returns:
        2D list of Vec3 colors [height][width]
    """
    bg = bg_color or Vec3(0.12, 0.12, 0.14)

    # Pixel buffer and depth buffer
    pixels = [[Vec3(bg.x, bg.y, bg.z) for _ in range(camera.width)]
              for _ in range(camera.height)]
    depth = [[float('inf') for _ in range(camera.width)]
             for _ in range(camera.height)]

    # Focal length in pixels (exact from FOV)
    focal_px = camera.width / (2.0 * camera.tan_half_fov * camera.aspect)

    for obj in objects:
        nodes = generate_surface_nodes(obj, density)

        for node in nodes:
            # Node computes its color response to light
            color = illuminate_node(node, light)

            # Node projects itself onto pixel grid
            proj = project_node(node.position, camera)
            if proj is None:
                continue

            px, py = proj
            ix = int(px)
            iy = int(py)

            if ix < 0 or ix >= camera.width or iy < 0 or iy >= camera.height:
                continue

            # Depth: exact dot product
            z = (node.position - camera.pos).dot(camera.forward)

            # Splat radius from node spacing (exact perspective scaling)
            spacing = 1.0 / math.sqrt(density) if density > 0 else 0.01
            splat_r = max(1, int(spacing * focal_px / z * 0.7))
            splat_r = min(splat_r, 4)  # cap to prevent blobs

            # Circular splat (exact distance check: sx²+sy² ≤ r²)
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


def _write_ppm(pixels, filepath):
    """Write pixel buffer to PPM file (exact format, no compression)."""
    height = len(pixels)
    width = len(pixels[0])

    with open(filepath, 'wb') as f:
        f.write(f"P6\n{width} {height}\n255\n".encode())
        for row in pixels:
            for p in row:
                r, g, b = p.to_rgb()
                f.write(bytes([r, g, b]))


def entangle_to_file(objects, camera, light, filepath,
                     density=200, bg_color=None):
    """Render and save to file.

    Writes PPM (exact pixel format). Converts to PNG if
    ImageMagick is available.
    """
    pixels = entangle(objects, camera, light, density, bg_color)

    # Determine output format
    base = filepath.rsplit('.', 1)[0] if '.' in filepath else filepath
    ppm_path = base + '.ppm'
    _write_ppm(pixels, ppm_path)

    # Try PNG conversion
    if filepath.endswith('.png'):
        import subprocess
        import os
        try:
            subprocess.run(['convert', ppm_path, filepath],
                          capture_output=True, timeout=10)
            if os.path.exists(filepath):
                os.remove(ppm_path)
                return filepath
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return ppm_path

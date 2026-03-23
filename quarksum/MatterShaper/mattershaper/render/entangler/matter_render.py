"""
Matter Render — push rendering from MatterNodes.

This is the Entangler v2: instead of sampling surfaces with Fibonacci
spirals, we build actual crystal lattices and let the surface atoms
(nodes with broken entanglement bonds) emit their color.

The rendering pipeline:
  1. Build matter: fill shape with crystal lattice (lattice_fill.py)
  2. Detect surface: nodes with broken bonds are emitters (matter_node.py)
  3. Illuminate: each surface node computes its Lambert response
  4. Project: each node projects itself onto the pixel grid
  5. Depth resolve: closest node wins (z-buffer)

Same push philosophy as the original Entangler.
Same projection math. Same illumination model.
But the surface nodes are REAL atomic positions, not samples.

The rendering IS the physics. The physics IS the rendering.
Entanglement is reality's TV.

Zero shared code with any ray tracer.
"""

import math
from .vec import Vec3
from .projection import PushCamera, project_node
from .illumination import PushLight, illuminate_node
from .surface_nodes import SurfaceNode
from .lattice_fill import (
    build_matter_cube, build_matter_sphere,
    fill_cube_with_lattice, connect_neighbors,
    resolve_all_surfaces, get_surface_nodes,
)


def matter_node_to_surface_node(mnode):
    """Convert a MatterNode to a SurfaceNode for the illumination pipeline.

    The MatterNode has richer information (bonds, lattice index, broken
    fraction). The SurfaceNode has the interface the illumination code
    expects (position, normal, material).

    This is a thin adapter — no information is lost.
    """
    return SurfaceNode(mnode.position, mnode.normal, mnode.material)


def entangle_matter(matter_objects, camera, light, bg_color=None):
    """Render a scene where objects are built from actual crystal lattices.

    Each matter_object is a dict:
      {
        'type': 'cube' or 'sphere',
        'center': Vec3,
        'size': float (edge_length for cube, radius for sphere),
        'crystal_structure': 'fcc', 'bcc', etc.,
        'lattice_param_m': float,
        'material': Material,
      }

    The pipeline:
      1. Build each object (fill lattice, connect bonds, find surface)
      2. Surface nodes illuminate themselves
      3. Surface nodes project onto pixel grid
      4. Z-buffer resolves occlusion

    Args:
        matter_objects: list of matter object dicts
        camera: PushCamera
        light: PushLight
        bg_color: Vec3 background color

    Returns:
        (pixels_2d, stats_dict)
        pixels_2d: 2D list of Vec3 colors [height][width]
        stats_dict: rendering statistics
    """
    bg = bg_color or Vec3(0.12, 0.12, 0.14)

    # Pixel buffer and depth buffer
    pixels = [[Vec3(bg.x, bg.y, bg.z) for _ in range(camera.width)]
              for _ in range(camera.height)]
    depth = [[float('inf') for _ in range(camera.width)]
             for _ in range(camera.height)]

    # Focal length in pixels (exact from FOV)
    focal_px = camera.width / (2.0 * camera.tan_half_fov * camera.aspect)

    total_atoms = 0
    total_surface = 0
    total_rendered = 0

    for obj in matter_objects:
        # Build matter from lattice
        if obj['type'] == 'cube':
            all_nodes, surface_nodes = build_matter_cube(
                obj['center'], obj['size'],
                obj['crystal_structure'], obj['lattice_param_m'],
                obj['material'],
            )
        elif obj['type'] == 'sphere':
            all_nodes, surface_nodes = build_matter_sphere(
                obj['center'], obj['size'],
                obj['crystal_structure'], obj['lattice_param_m'],
                obj['material'],
            )
        else:
            raise ValueError(f"Unknown matter type: {obj['type']}")

        total_atoms += len(all_nodes)
        total_surface += len(surface_nodes)

        # Surface nodes emit: push rendering
        for mnode in surface_nodes:
            snode = matter_node_to_surface_node(mnode)

            # Node illuminates itself
            color = illuminate_node(snode, light)

            # Node projects itself onto pixel grid
            proj = project_node(snode.position, camera)
            if proj is None:
                continue

            px, py = proj
            ix = int(px)
            iy = int(py)

            if ix < 0 or ix >= camera.width or iy < 0 or iy >= camera.height:
                continue

            # Depth
            z = (snode.position - camera.pos).dot(camera.forward)
            if z <= 0:
                continue

            # Splat: for atomic-scale nodes rendered at macro scale,
            # many atoms map to the same pixel. The natural splat is 1px.
            # We add a small splat to prevent gaps.
            splat_r = 1

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

            total_rendered += 1

    stats = {
        'total_atoms': total_atoms,
        'surface_atoms': total_surface,
        'rendered_nodes': total_rendered,
        'surface_fraction': total_surface / total_atoms if total_atoms > 0 else 0,
        'resolution': (camera.width, camera.height),
    }

    return pixels, stats


def _write_ppm(pixels, filepath):
    """Write pixel buffer to PPM file."""
    height = len(pixels)
    width = len(pixels[0])
    with open(filepath, 'wb') as f:
        f.write(f"P6\n{width} {height}\n255\n".encode())
        for row in pixels:
            for p in row:
                r, g, b = p.to_rgb()
                f.write(bytes([r, g, b]))


def entangle_matter_to_file(matter_objects, camera, light, filepath,
                            bg_color=None):
    """Build matter, render, and save to file.

    Returns:
        (output_path, stats_dict)
    """
    pixels, stats = entangle_matter(matter_objects, camera, light, bg_color)

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
                return filepath, stats
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return ppm_path, stats

"""
Entangler Render Bridge — Shape/Color JSON → push-rendered PNG.

Converts Nagatha's .shape.json + .color.json into entangler objects
and renders via the push projection pipeline.

Primitive mapping:
  sphere   → EntanglerSphere
  ellipsoid → EntanglerEllipsoid (with rotation)
  cone     → 8 stacked EntanglerEllipsoid slices
"""

import sys
import os
import json
import math
import struct
import time
import zlib

# Ensure MatterShaper is importable
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.shapes import (
    EntanglerSphere, EntanglerEllipsoid, rotation_matrix,
)
from mattershaper.render.entangler.surface_nodes import generate_surface_nodes
from mattershaper.render.entangler.projection import PushCamera, project_node
from mattershaper.render.entangler.illumination import PushLight, illuminate_node
from mattershaper.render.entangler.engine import entangle, _write_ppm
from mattershaper.materials.material import Material


def make_material(mat_id, color_map):
    """Build an entangler Material from a color map entry."""
    mats = color_map.get('materials', {})
    m = mats.get(mat_id, {})

    # Handle both formats: color=[r,g,b] vs separate r,g,b keys
    if 'color' in m:
        c = m['color']
        r, g, b = c[0], c[1], c[2]
    else:
        r = m.get('r', 0.6)
        g = m.get('g', 0.6)
        b = m.get('b', 0.6)

    return Material(
        name=m.get('label', mat_id),
        color=Vec3(r, g, b),
        reflectance=m.get('reflectance', m.get('specular', 0.1)),
        roughness=m.get('roughness', 0.5),
        density_kg_m3=m.get('density_kg_m3', 1000),
        mean_Z=m.get('mean_Z', 7),
        mean_A=m.get('mean_A', 14),
        composition=m.get('composition', ''),
    )


def _get_pos(layer):
    """Get position from layer, handling 'pos' vs 'center' keys."""
    return layer.get('pos') or layer.get('center') or [0, 0, 0]


def _get_layers(shape_map):
    """Get layers list, handling both wrapper formats."""
    return shape_map.get('layers', [])


def compute_bounding_box(shape_map):
    """Compute AABB from shape map layers."""
    mins = [float('inf')] * 3
    maxs = [float('-inf')] * 3

    for layer in _get_layers(shape_map):
        ltype = layer['type']

        if ltype == 'sphere':
            p = _get_pos(layer)
            r = layer['radius']
            for i in range(3):
                mins[i] = min(mins[i], p[i] - r)
                maxs[i] = max(maxs[i], p[i] + r)

        elif ltype == 'ellipsoid':
            p = _get_pos(layer)
            radii = layer['radii']
            for i in range(3):
                mins[i] = min(mins[i], p[i] - radii[i])
                maxs[i] = max(maxs[i], p[i] + radii[i])

        elif ltype == 'cone':
            p = layer.get('base_pos', _get_pos(layer))
            h = layer['height']
            br = layer['base_radius']
            tr = layer['top_radius']
            r_max = max(br, tr)
            mins[0] = min(mins[0], p[0] - r_max)
            mins[1] = min(mins[1], p[1])
            mins[2] = min(mins[2], p[2] - r_max)
            maxs[0] = max(maxs[0], p[0] + r_max)
            maxs[1] = max(maxs[1], p[1] + h)
            maxs[2] = max(maxs[2], p[2] + r_max)

    cx = (mins[0] + maxs[0]) / 2
    cy = (mins[1] + maxs[1]) / 2
    cz = (mins[2] + maxs[2]) / 2
    dx = maxs[0] - mins[0]
    dy = maxs[1] - mins[1]
    dz = maxs[2] - mins[2]
    extent = math.sqrt(dx**2 + dy**2 + dz**2)

    return {
        'min': mins, 'max': maxs,
        'center': (cx, cy, cz),
        'size': (dx, dy, dz),
        'extent': extent,
    }


def shape_map_to_entangler_objects(shape_map, color_map):
    """Convert shape/color JSON into a list of entangler objects."""
    objects = []
    mat_cache = {}

    for layer in _get_layers(shape_map):
        mat_id = layer['material']
        if mat_id not in mat_cache:
            mat_cache[mat_id] = make_material(mat_id, color_map)
        mat = mat_cache[mat_id]

        ltype = layer['type']

        if ltype == 'sphere':
            p = _get_pos(layer)
            obj = EntanglerSphere(
                center=Vec3(p[0], p[1], p[2]),
                radius=layer['radius'],
                material=mat,
            )
            objects.append(obj)

        elif ltype == 'ellipsoid':
            p = _get_pos(layer)
            r = layer['radii']
            # Clamp zero radii to a small value to avoid division by zero
            min_r = 0.005
            rx = max(abs(r[0]), min_r)
            ry = max(abs(r[1]), min_r)
            rz = max(abs(r[2]), min_r)
            rot = layer.get('rotate', [0, 0, 0])
            obj = EntanglerEllipsoid(
                center=Vec3(p[0], p[1], p[2]),
                radii=Vec3(rx, ry, rz),
                rotation=rotation_matrix(rot[0], rot[1], rot[2]),
                material=mat,
            )
            objects.append(obj)

        elif ltype == 'cone':
            # Approximate cone as stacked ellipsoid slices
            p = layer.get('base_pos', _get_pos(layer))
            h = layer['height']
            br = layer['base_radius']
            tr = layer['top_radius']
            rot = layer.get('rotate', [0, 0, 0])
            rot_mat = rotation_matrix(rot[0], rot[1], rot[2])

            n_slices = 8
            for i in range(n_slices):
                frac = (i + 0.5) / n_slices
                y_local = frac * h
                r_at_y = br + (tr - br) * frac
                slice_h = h / n_slices

                obj = EntanglerEllipsoid(
                    center=Vec3(p[0], p[1] + y_local, p[2]),
                    radii=Vec3(r_at_y, slice_h * 0.6, r_at_y),
                    rotation=rot_mat,
                    material=mat,
                )
                objects.append(obj)

    return objects


def write_png(pixels, filepath):
    """Write pixel buffer to PNG using pure Python (struct + zlib)."""
    height = len(pixels)
    width = len(pixels[0])

    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter: none
        for p in row:
            r, g, b = p.to_rgb()
            raw.extend([r, g, b])

    compressed = zlib.compress(bytes(raw))

    def chunk(ctype, data):
        c = ctype + data
        crc = zlib.crc32(c) & 0xffffffff
        return struct.pack('>I', len(data)) + c + struct.pack('>I', crc)

    with open(filepath, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)))
        f.write(chunk(b'IDAT', compressed))
        f.write(chunk(b'IEND', b''))


def render_object_entangler(key, shape_map, color_map, output_dir,
                            width=512, height=512, density=1200):
    """Render an object from shape/color JSON using the entangler.

    Returns dict with render metadata.
    """
    os.makedirs(output_dir, exist_ok=True)

    name = shape_map.get('name', key)

    # Normalize: some formats have layers at root level
    if 'layers' not in shape_map and isinstance(shape_map.get('layers'), list):
        pass  # already fine
    # If no layers key, check if the shape map itself IS a list of layers
    objects = shape_map_to_entangler_objects(shape_map, color_map)

    if not objects:
        return {'error': f'No renderable layers in {key}'}

    # Auto-camera from bounding box
    bbox = compute_bounding_box(shape_map)
    cx, cy, cz = bbox['center']
    extent = bbox['extent']

    cam_dist = max(0.6, extent * 2.5)
    cam_height = max(0.2, cy + extent * 0.4)

    camera = PushCamera(
        pos=Vec3(cam_dist * 0.7, cam_height, cam_dist * 0.7),
        look_at=Vec3(cx, cy, cz),
        width=width, height=height,
        fov=45,
    )

    light_dist = max(2.0, extent * 4)
    light = PushLight(
        pos=Vec3(light_dist * 0.75, light_dist * 1.0, light_dist * 0.5),
        intensity=1.0,
        color=Vec3(1.0, 0.95, 0.88),
    )

    bg = Vec3(0.08, 0.08, 0.12)

    t0 = time.time()
    pixels = entangle(objects, camera, light, density=density, bg_color=bg)
    render_time = time.time() - t0

    timestamp = int(time.time())
    filename = f'{key}.png'
    filepath = os.path.join(output_dir, filename)

    write_png(pixels, filepath)

    return {
        'key': key,
        'name': name,
        'filename': filename,
        'renderer': 'entangler',
        'width': width,
        'height': height,
        'density': density,
        'render_time_s': round(render_time, 2),
        'timestamp': timestamp,
        'primitives': len(shape_map.get('layers', [])),
        'entangler_objects': len(objects),
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python -m gallery.entangler_render <base_path>")
        print("  e.g.: python -m gallery.entangler_render object_maps/coffee_mug")
        sys.exit(1)

    base = sys.argv[1]
    with open(base + '.shape.json', encoding='utf-8') as f:
        shape = json.load(f)
    with open(base + '.color.json', encoding='utf-8') as f:
        color = json.load(f)

    out = os.path.join(os.path.dirname(__file__), 'renders')
    key = os.path.basename(base)
    result = render_object_entangler(key, shape, color, out)
    print(json.dumps(result, indent=2))

"""
MatterShaper — Render from Shape Map + Color Map.

Reads a .shape.json and .color.json pair, builds the scene,
and renders it with studio lighting on a neutral floor.

Auto-scales camera to fit any object size — from bananas to buildings.

Usage:
    python render_from_maps.py object_maps/coffee_mug
    # reads coffee_mug.shape.json + coffee_mug.color.json
    # outputs renders/{name}.png
"""

import sys
import os
import json
import math
import time

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper import MatterShaper, Material, Vec3


def load_maps(base_path):
    """Load shape + color map pair from a base path (no extension)."""
    shape_path = base_path + '.shape.json'
    color_path = base_path + '.color.json'

    with open(shape_path) as f:
        shape_map = json.load(f)
    with open(color_path) as f:
        color_map = json.load(f)

    return shape_map, color_map


def make_material(mat_id, color_map):
    """Build a Material from a color map entry."""
    m = color_map['materials'][mat_id]
    c = m['color']
    return Material(
        name=m.get('label', mat_id),
        color=Vec3(c[0], c[1], c[2]),
        reflectance=m.get('reflectance', 0.1),
        roughness=m.get('roughness', 0.5),
        density_kg_m3=m.get('density_kg_m3', 1000),
        mean_Z=m.get('mean_Z', 7),
        mean_A=m.get('mean_A', 14),
        composition=m.get('composition', ''),
    )


def compute_bounding_box(shape_map):
    """Compute axis-aligned bounding box from shape map layers.

    Returns (min_x, min_y, min_z, max_x, max_y, max_z, center_x, center_y, center_z, extent).
    """
    mins = [float('inf')] * 3
    maxs = [float('-inf')] * 3

    for layer in shape_map['layers']:
        ltype = layer['type']

        if ltype == 'sphere':
            p = layer['pos']
            r = layer['radius']
            for i in range(3):
                mins[i] = min(mins[i], p[i] - r)
                maxs[i] = max(maxs[i], p[i] + r)

        elif ltype == 'ellipsoid':
            p = layer['pos']
            radii = layer['radii']
            for i in range(3):
                mins[i] = min(mins[i], p[i] - radii[i])
                maxs[i] = max(maxs[i], p[i] + radii[i])

        elif ltype == 'cone':
            p = layer['base_pos']
            h = layer['height']
            br = layer['base_radius']
            tr = layer['top_radius']
            r_max = max(br, tr)
            # Base at p, top at p + (0, h, 0)
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
        'min': mins,
        'max': maxs,
        'center': (cx, cy, cz),
        'size': (dx, dy, dz),
        'extent': extent,
    }


def build_object(ms, shape_map, color_map, offset=(0, 0, 0)):
    """Add all layers from a shape map to the scene, with optional offset."""
    ox, oy, oz = offset
    mat_cache = {}

    for layer in shape_map['layers']:
        # Resolve material
        mat_id = layer['material']
        if mat_id not in mat_cache:
            mat_cache[mat_id] = make_material(mat_id, color_map)
        mat = mat_cache[mat_id]

        ltype = layer['type']

        if ltype == 'sphere':
            p = layer['pos']
            ms.sphere(
                pos=(p[0] + ox, p[1] + oy, p[2] + oz),
                radius=layer['radius'],
                material=mat,
            )

        elif ltype == 'ellipsoid':
            p = layer['pos']
            r = layer['radii']
            rot = layer.get('rotate', [0, 0, 0])
            ms.ellipsoid(
                pos=(p[0] + ox, p[1] + oy, p[2] + oz),
                radii=tuple(r),
                rotate=tuple(rot),
                material=mat,
            )

        elif ltype == 'cone':
            p = layer['base_pos']
            rot = layer.get('rotate', [0, 0, 0])
            ms.cone(
                base_pos=(p[0] + ox, p[1] + oy, p[2] + oz),
                height=layer['height'],
                base_radius=layer['base_radius'],
                top_radius=layer['top_radius'],
                rotate=tuple(rot),
                material=mat,
            )

        elif ltype == 'plane':
            ms.plane(
                y=layer.get('y', 0) + oy,
                material=mat,
            )

    return mat_cache


def render_object(base_path, width=400, height=400, camera_distance=None,
                  camera_height=None, look_y=None, fov=45):
    """Full pipeline: load maps → auto-scale camera → build scene → render."""
    shape_map, color_map = load_maps(base_path)
    name = shape_map['name']

    print(f"MatterShaper — {name}")
    print("=" * 50)
    print(f"Reference: {shape_map.get('reference', 'N/A')}")
    print(f"Scale: {shape_map.get('scale_note', 'N/A')}")
    print(f"Layers: {len(shape_map['layers'])}")

    # Auto-scale camera from bounding box
    bbox = compute_bounding_box(shape_map)
    cx, cy, cz = bbox['center']
    extent = bbox['extent']

    if camera_distance is None:
        # Place camera at ~2.5× the object extent for good framing
        camera_distance = max(0.6, extent * 2.5)
    if camera_height is None:
        # Camera at ~object center height + a bit above
        camera_height = max(0.2, cy + extent * 0.4)
    if look_y is None:
        # Look at vertical center of the object
        look_y = cy

    print(f"BBox: size=({bbox['size'][0]:.3f}, {bbox['size'][1]:.3f}, {bbox['size'][2]:.3f}), "
          f"extent={extent:.3f}")
    print(f"Camera: dist={camera_distance:.3f}, height={camera_height:.3f}, look_y={look_y:.3f}")

    ms = MatterShaper()
    ms.background(0.08, 0.08, 0.12)
    ms.ambient(0.10, 0.10, 0.13)

    # Neutral floor
    floor_mat = Material(
        name='Studio Floor',
        color=Vec3(0.35, 0.35, 0.38),
        reflectance=0.15,
        roughness=0.40,
    )
    ms.plane(y=0, material=floor_mat)

    # Build the object at origin
    build_object(ms, shape_map, color_map)

    # Studio lighting — scaled to object size
    light_dist = max(2.0, extent * 4)
    ms.light(pos=(light_dist * 0.75, light_dist * 1.0, light_dist * 0.5),
             color=(1.0, 0.95, 0.88), intensity=0.85)
    ms.light(pos=(-light_dist * 0.75, light_dist * 0.75, light_dist * 0.25),
             color=(0.65, 0.72, 0.95), intensity=0.40)
    ms.light(pos=(0, light_dist * 0.5, -light_dist),
             color=(0.8, 0.8, 0.9), intensity=0.30)
    ms.light(pos=(0, extent * 0.3, light_dist * 0.75),
             color=(0.9, 0.85, 0.8), intensity=0.15)

    # Camera — auto-positioned
    ms.camera(
        pos=(camera_distance * 0.7, camera_height, camera_distance * 0.7),
        look_at=(cx, look_y, cz),
        fov=fov,
    )

    print(ms)

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'renders')
    os.makedirs(out_dir, exist_ok=True)

    safe_name = name.lower().replace(' ', '_')
    out_path = os.path.join(out_dir, f'{safe_name}_map.png')

    print(f"\nRendering {width}×{height} ({width * height:,} rays)...")
    t0 = time.time()
    result = ms.render(out_path, width=width, height=height)
    t1 = time.time()

    print(f"Done in {t1-t0:.2f}s")
    print(f"Output: {result['filepath']}")
    print(f"Scene: {result['objects']} objects, {result['lights']} lights")

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python render_from_maps.py <base_path>")
        print("  e.g.: python render_from_maps.py object_maps/coffee_mug")
        sys.exit(1)

    base_path = sys.argv[1]
    render_object(base_path, width=400, height=400)


if __name__ == '__main__':
    main()

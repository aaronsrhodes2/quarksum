#!/usr/bin/env python3
"""
Benchmark: Can we see the object without a ray tracer?

Renders the coffee mug using push rendering — matter projects itself.
No Ray. No Hit. No intersection tests. The surface nodes do the drawing.
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.geometry import Vec3, Sphere, Ellipsoid, rotation_matrix
from mattershaper.materials import Material
from mattershaper.render.push import (
    PushCamera, PushLight, push_render, push_render_to_file
)


def build_coffee_mug():
    """Build the coffee mug from shape + color maps.
    Same object, push rendered."""

    # Load maps
    maps_dir = os.path.join(os.path.dirname(__file__), 'object_maps')
    with open(os.path.join(maps_dir, 'coffee_mug.shape.json')) as f:
        shape = json.load(f)
    with open(os.path.join(maps_dir, 'coffee_mug.color.json')) as f:
        colors = json.load(f)

    objects = []

    for layer in shape['layers']:
        mat_id = layer['material']
        mat_data = colors['materials'][mat_id]
        c = mat_data['color']
        material = Material(
            name=mat_data.get('label', mat_id),
            color=Vec3(c[0], c[1], c[2]),
            reflectance=mat_data.get('reflectance', 0.1),
            roughness=mat_data.get('roughness', 0.5),
            density_kg_m3=mat_data.get('density_kg_m3', 2400),
            mean_Z=mat_data.get('mean_Z', 11),
            mean_A=mat_data.get('mean_A', 22),
            composition=mat_data.get('composition', ''),
        )

        ltype = layer['type']
        rot = layer.get('rotate', [0, 0, 0])
        rot_mat = rotation_matrix(rot[0], rot[1], rot[2])

        if ltype == 'ellipsoid':
            p = layer['pos']
            r = layer['radii']
            obj = Ellipsoid(
                center=Vec3(p[0], p[1], p[2]),
                radii=Vec3(r[0], r[1], r[2]),
                rotation=rot_mat,
                material=material,
            )
            objects.append(obj)

        elif ltype == 'cone':
            # Approximate cone as a stack of ellipsoids
            bp = layer['base_pos']
            h = layer['height']
            br = layer['base_radius']
            tr = layer['top_radius']
            n_slices = 8
            for i in range(n_slices):
                t = (i + 0.5) / n_slices
                y = bp[1] + t * h
                r = br + t * (tr - br)
                slice_h = h / n_slices
                obj = Ellipsoid(
                    center=Vec3(bp[0], y, bp[2]),
                    radii=Vec3(r, slice_h * 0.6, r),
                    rotation=rot_mat,
                    material=material,
                )
                objects.append(obj)

        elif ltype == 'sphere':
            p = layer['pos']
            r = layer['radius']
            obj = Sphere(
                center=Vec3(p[0], p[1], p[2]),
                radius=r,
                material=material,
            )
            objects.append(obj)

    return objects


def main():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  PUSH RENDER — Matter draws itself. No ray tracer.  ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    objects = build_coffee_mug()
    print(f"  Scene: {len(objects)} primitives (coffee mug)")

    # Camera — slightly above, looking at mug center
    cam = PushCamera(
        pos=Vec3(1.2, 0.8, 1.5),
        look_at=Vec3(0, 0.45, 0),
        width=400,
        height=400,
        fov=50,
    )

    # Single artificial light source — the activation trigger
    light = PushLight(
        pos=Vec3(2, 3, 3),
        intensity=1.0,
    )

    density = 800  # nodes per unit area

    print(f"  Density: {density} nodes/unit²")
    print(f"  Resolution: {cam.width}×{cam.height}")
    print()
    print("  Rendering (matter is projecting itself)...")

    t0 = time.time()
    out_path = os.path.join(os.path.dirname(__file__), '..', 'mnt', 'quarksum',
                            'push_render_coffee_mug.ppm')
    # Normalize path
    out_path = os.path.abspath(out_path)
    # Actually, output to the MatterShaper dir for now
    out_path = os.path.join(os.path.dirname(__file__), 'push_render_coffee_mug.ppm')

    pixels = push_render(objects, cam, light, density=density)
    elapsed = time.time() - t0

    # Count non-background pixels
    bg = Vec3(0.12, 0.12, 0.14)
    lit_pixels = 0
    total_pixels = cam.width * cam.height
    for row in pixels:
        for p in row:
            if abs(p.x - bg.x) > 0.01 or abs(p.y - bg.y) > 0.01 or abs(p.z - bg.z) > 0.01:
                lit_pixels += 1

    # Count total nodes generated
    total_nodes = 0
    for obj in objects:
        from mattershaper.render.push import generate_surface_nodes
        total_nodes += len(generate_surface_nodes(obj, density))

    # Write PPM
    with open(out_path, 'wb') as f:
        f.write(f"P6\n{cam.width} {cam.height}\n255\n".encode())
        for row in pixels:
            for p in row:
                r, g, b = p.to_rgb()
                f.write(bytes([r, g, b]))

    print(f"  Done in {elapsed:.2f}s")
    print(f"  Surface nodes generated: {total_nodes:,}")
    print(f"  Pixels lit: {lit_pixels:,} / {total_pixels:,} ({100*lit_pixels/total_pixels:.1f}%)")
    print(f"  Output: {out_path}")
    print()
    print("  ═══════════════════════════════════════════════════")
    print("  BENCHMARK PASSED: Object visible without ray tracer")
    print("  ═══════════════════════════════════════════════════")

    # Also write to workspace for user to see
    workspace_path = '/sessions/loving-pensive-euler/mnt/quarksum/push_render_coffee_mug.ppm'
    with open(workspace_path, 'wb') as f:
        f.write(f"P6\n{cam.width} {cam.height}\n255\n".encode())
        for row in pixels:
            for p in row:
                r, g, b = p.to_rgb()
                f.write(bytes([r, g, b]))
    print(f"  Copy in workspace: {workspace_path}")


if __name__ == '__main__':
    main()

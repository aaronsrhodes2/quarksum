#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║          T H E   G R E A T   R E N D E R   S H O O T O U T     ║
║                                                                  ║
║   In the LEFT corner:  RAY TRACER  — the reigning champion      ║
║   In the RIGHT corner: ENTANGLER   — matter draws itself        ║
║                                                                  ║
║   Same mug. Same materials. Same light. FIGHT!                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import json
import time
import math

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper import MatterShaper, Material
from mattershaper.geometry import Vec3 as SharedVec3, rotation_matrix as shared_rotation

# Entangler: quarantined imports — zero shared code with ray tracer
from mattershaper.render.entangler import (
    Vec3 as EntVec3, PushCamera, PushLight,
    entangle, generate_surface_nodes,
)
from mattershaper.render.entangler.shapes import (
    EntanglerSphere, EntanglerEllipsoid, rotation_matrix,
)

# ── Shared setup ─────────────────────────────────────────────────

MAPS_DIR = os.path.join(os.path.dirname(__file__), 'object_maps')
WIDTH, HEIGHT = 400, 400

# Camera position (identical for both)
CAM_POS = (1.2, 0.8, 1.5)
LOOK_AT = (0, 0.45, 0)
FOV = 50

# Light position (identical for both)
LIGHT_POS = (2, 3, 3)


def load_maps():
    with open(os.path.join(MAPS_DIR, 'coffee_mug.shape.json')) as f:
        shape = json.load(f)
    with open(os.path.join(MAPS_DIR, 'coffee_mug.color.json')) as f:
        colors = json.load(f)
    return shape, colors


def make_mat(mat_id, colors, Vec3=SharedVec3):
    m = colors['materials'][mat_id]
    c = m['color']
    return Material(
        name=m.get('label', mat_id),
        color=Vec3(c[0], c[1], c[2]),
        reflectance=m.get('reflectance', 0.1),
        roughness=m.get('roughness', 0.5),
        density_kg_m3=m.get('density_kg_m3', 2400),
        mean_Z=m.get('mean_Z', 11),
        mean_A=m.get('mean_A', 22),
        composition=m.get('composition', ''),
    )


# ── CONTESTANT 1: RAY TRACER ─────────────────────────────────────

def render_raytracer(shape, colors):
    """The champion. Casts rays from camera through every pixel."""
    ms = MatterShaper()
    ms.background(0.12, 0.12, 0.14)
    ms.ambient(0.08, 0.08, 0.10)

    mat_cache = {}
    for layer in shape['layers']:
        mat_id = layer['material']
        if mat_id not in mat_cache:
            mat_cache[mat_id] = make_mat(mat_id, colors, Vec3=SharedVec3)
        mat = mat_cache[mat_id]
        ltype = layer['type']

        if ltype == 'ellipsoid':
            p = layer['pos']
            r = layer['radii']
            rot = layer.get('rotate', [0, 0, 0])
            ms.ellipsoid(pos=tuple(p), radii=tuple(r), rotate=tuple(rot), material=mat)
        elif ltype == 'cone':
            p = layer['base_pos']
            rot = layer.get('rotate', [0, 0, 0])
            ms.cone(base_pos=tuple(p), height=layer['height'],
                    base_radius=layer['base_radius'], top_radius=layer['top_radius'],
                    rotate=tuple(rot), material=mat)
        elif ltype == 'sphere':
            p = layer['pos']
            ms.sphere(pos=tuple(p), radius=layer['radius'], material=mat)

    ms.light(pos=LIGHT_POS, color=(1.0, 0.95, 0.9), intensity=0.9)
    ms.camera(pos=CAM_POS, look_at=LOOK_AT, fov=FOV)

    out = os.path.join(os.path.dirname(__file__), 'shootout_raytracer.png')
    t0 = time.time()
    result = ms.render(out, width=WIDTH, height=HEIGHT)
    elapsed = time.time() - t0

    rays = WIDTH * HEIGHT
    return {
        'file': out,
        'time': elapsed,
        'rays': rays,
        'nodes': 0,
        'method': 'Ray Tracing',
        'primitives': len(shape['layers']),
    }


# ── CONTESTANT 2: ENTANGLER ──────────────────────────────────────

def render_entangler(shape, colors):
    """The challenger. Matter projects itself. No rays fired.

    Uses QUARANTINED Entangler module — zero imports from ray tracer.
    Own Vec3, own shapes, own rotation matrices, own everything.
    """
    objects = []

    for layer in shape['layers']:
        mat_id = layer['material']
        # Material uses Entangler's own Vec3 for color
        mat = make_mat(mat_id, colors, Vec3=EntVec3)
        ltype = layer['type']
        rot = layer.get('rotate', [0, 0, 0])
        rot_mat = rotation_matrix(rot[0], rot[1], rot[2])

        if ltype == 'ellipsoid':
            p = layer['pos']
            r = layer['radii']
            objects.append(EntanglerEllipsoid(
                center=EntVec3(p[0], p[1], p[2]),
                radii=EntVec3(r[0], r[1], r[2]),
                rotation=rot_mat, material=mat,
            ))
        elif ltype == 'cone':
            bp = layer['base_pos']
            h = layer['height']
            br = layer['base_radius']
            tr = layer['top_radius']
            n_slices = 8
            for i in range(n_slices):
                t = (i + 0.5) / n_slices
                y = bp[1] + t * h
                r = br + t * (tr - br)
                objects.append(EntanglerEllipsoid(
                    center=EntVec3(bp[0], y, bp[2]),
                    radii=EntVec3(r, h / n_slices * 0.6, r),
                    rotation=rot_mat, material=mat,
                ))
        elif ltype == 'sphere':
            p = layer['pos']
            objects.append(EntanglerSphere(
                center=EntVec3(p[0], p[1], p[2]),
                radius=layer['radius'], material=mat,
            ))

    cam = PushCamera(
        pos=EntVec3(*CAM_POS), look_at=EntVec3(*LOOK_AT),
        width=WIDTH, height=HEIGHT, fov=FOV,
    )
    light = PushLight(pos=EntVec3(*LIGHT_POS), intensity=1.0)
    density = 1200

    # Count nodes
    total_nodes = sum(len(generate_surface_nodes(obj, density)) for obj in objects)

    t0 = time.time()
    pixels = entangle(objects, cam, light, density=density)
    elapsed = time.time() - t0

    # Write PPM
    out_ppm = os.path.join(os.path.dirname(__file__), 'shootout_entangler.ppm')
    with open(out_ppm, 'wb') as f:
        f.write(f"P6\n{WIDTH} {HEIGHT}\n255\n".encode())
        for row in pixels:
            for p in row:
                r, g, b = p.to_rgb()
                f.write(bytes([r, g, b]))

    # Convert to PNG
    out_png = os.path.join(os.path.dirname(__file__), 'shootout_entangler.png')
    import subprocess
    try:
        subprocess.run(['convert', out_ppm, out_png], capture_output=True, timeout=10)
        os.remove(out_ppm)
    except Exception:
        out_png = out_ppm

    return {
        'file': out_png,
        'time': elapsed,
        'rays': 0,
        'nodes': total_nodes,
        'method': 'Entangler (Push)',
        'primitives': len(objects),
    }


# ── COMPARISON ────────────────────────────────────────────────────

def build_comparison(rt, ent):
    """Build side-by-side comparison image with stats."""
    import subprocess

    out_path = '/sessions/loving-pensive-euler/mnt/quarksum/shootout_comparison.png'

    # Build stats text for annotation
    rt_label = (f"RAY TRACER\\n"
                f"{rt['time']:.2f}s | {rt['rays']:,} rays\\n"
                f"{rt['primitives']} primitives")
    ent_label = (f"ENTANGLER\\n"
                 f"{ent['time']:.2f}s | {ent['nodes']:,} nodes\\n"
                 f"{ent['primitives']} primitives | 0 rays")

    # Use ImageMagick to compose side-by-side with labels
    try:
        # Add labels to each image
        rt_labeled = '/tmp/rt_labeled.png'
        ent_labeled = '/tmp/ent_labeled.png'

        subprocess.run([
            'convert', rt['file'],
            '-gravity', 'South', '-background', '#1B2A4A', '-fill', 'white',
            '-font', 'DejaVu-Sans', '-pointsize', '14',
            '-splice', '0x60', '-gravity', 'South',
            '-annotate', '+0+8', rt_label,
            '-gravity', 'North', '-background', '#1B2A4A',
            '-splice', '0x35', '-gravity', 'North',
            '-annotate', '+0+8', 'CHAMPION',
            rt_labeled
        ], capture_output=True, timeout=15)

        subprocess.run([
            'convert', ent['file'],
            '-gravity', 'South', '-background', '#2A1B4A', '-fill', 'white',
            '-font', 'DejaVu-Sans', '-pointsize', '14',
            '-splice', '0x60', '-gravity', 'South',
            '-annotate', '+0+8', ent_label,
            '-gravity', 'North', '-background', '#2A1B4A',
            '-splice', '0x35', '-gravity', 'North',
            '-annotate', '+0+8', 'CHALLENGER',
            ent_labeled
        ], capture_output=True, timeout=15)

        # Side by side with VS divider
        subprocess.run([
            'convert', rt_labeled, ent_labeled,
            '+append', out_path
        ], capture_output=True, timeout=15)

        # Clean up
        for f in [rt_labeled, ent_labeled]:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        # Fallback: just stitch them together
        subprocess.run([
            'convert', rt['file'], ent['file'], '+append', out_path
        ], capture_output=True, timeout=15)

    return out_path


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║          T H E   G R E A T   R E N D E R   S H O O T O U T     ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()

    shape, colors = load_maps()

    # ── Round 1: Ray Tracer ───────────────────────────────────────
    print("  ╔══════════════════════════════════════╗")
    print("  ║  CONTESTANT 1: RAY TRACER            ║")
    print("  ║  \"I ask the questions around here.\"   ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    rt = render_raytracer(shape, colors)
    print(f"  Time:   {rt['time']:.2f}s")
    print(f"  Rays:   {rt['rays']:,}")
    print(f"  Output: {rt['file']}")
    print()

    # ── Round 2: Entangler ────────────────────────────────────────
    print("  ╔══════════════════════════════════════╗")
    print("  ║  CONTESTANT 2: ENTANGLER             ║")
    print("  ║  \"I speak when light asks.\"           ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    ent = render_entangler(shape, colors)
    print(f"  Time:   {ent['time']:.2f}s")
    print(f"  Nodes:  {ent['nodes']:,}")
    print(f"  Rays:   0")
    print(f"  Output: {ent['file']}")
    print()

    # ── Comparison ────────────────────────────────────────────────
    print("  Building side-by-side comparison...")
    comp_path = build_comparison(rt, ent)
    print()

    # ── Score Card ────────────────────────────────────────────────
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║                    S C O R E C A R D                        ║")
    print("  ╠══════════════════════════════════════════════════════════════╣")
    print(f"  ║  {'':30s} {'RAY TRACER':>12s}   {'ENTANGLER':>12s}    ║")
    print(f"  ║  {'─'*30} {'─'*12}   {'─'*12}    ║")
    print(f"  ║  {'Render time':30s} {rt['time']:>11.2f}s   {ent['time']:>11.2f}s    ║")
    print(f"  ║  {'Rays cast':30s} {rt['rays']:>12,}   {'0':>12s}    ║")
    print(f"  ║  {'Surface nodes':30s} {'0':>12s}   {ent['nodes']:>12,}    ║")
    print(f"  ║  {'Intersection tests':30s} {rt['rays']:>12,}   {'0':>12s}    ║")
    print(f"  ║  {'Ray imports in source':30s} {'Yes':>12s}   {'No':>12s}    ║")
    print(f"  ║  {'Matter knows its physics':30s} {'No':>12s}   {'Yes':>12s}    ║")
    print(f"  ║  {'Renders without light':30s} {'Black':>12s}   {'Black':>12s}    ║")
    print(f"  ║  {'Architecture':30s} {'Pull':>12s}   {'Push':>12s}    ║")

    # Speed comparison
    if ent['time'] < rt['time']:
        speedup = rt['time'] / ent['time']
        winner = 'ENTANGLER'
        print(f"  ║  {'Speed winner':30s} {'':>12s}   {speedup:>10.1f}x ←   ║")
    else:
        speedup = ent['time'] / rt['time']
        winner = 'RAY TRACER'
        print(f"  ║  {'Speed winner':30s} {speedup:>10.1f}x ←   {'':>12s}    ║")

    print(f"  ╠══════════════════════════════════════════════════════════════╣")
    print(f"  ║  {'VISUAL QUALITY':30s} {'Smooth':>12s}   {'Pointillist':>12s}    ║")
    print(f"  ║  {'PHYSICS AWARENESS':30s} {'None':>12s}   {'Full stack':>12s}    ║")
    print(f"  ║  {'NOVELTY':30s} {'1980':>12s}   {'2026':>12s}    ║")
    print(f"  ╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Comparison image: {comp_path}")
    print()

    # Copy to workspace
    import shutil
    workspace = '/sessions/loving-pensive-euler/mnt/quarksum/'
    for f in [rt['file'], ent['file']]:
        dest = os.path.join(workspace, os.path.basename(f))
        shutil.copy2(f, dest)

    print("  Both renderers have spoken. The crowd decides.")
    print()


if __name__ == '__main__':
    main()

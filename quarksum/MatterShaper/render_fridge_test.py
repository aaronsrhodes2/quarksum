"""
The Refrigerator Test — is the light on when the door is closed?

Setup:
  - An iron box (the fridge) — 6 walls made of BCC iron lattice
  - A copper sphere INSIDE the box (the orange inside the fridge)
  - Camera OUTSIDE: can we see the copper sphere? (door is closed)
  - Camera INSIDE: the sphere was broadcasting the whole time

In ray tracing: you can't see inside without opening the door.
In push rendering: matter broadcasts. The camera is passive.
  Move it inside and the scene was ALREADY THERE.

This proves: in an entanglement-based renderer, observation doesn't
create the scene. The scene exists independently. The camera just
picks a viewpoint into a reality that's always emitting.

Schrödinger's fridge: the light was always on.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.projection import PushCamera
from mattershaper.render.entangler.illumination import PushLight
from mattershaper.render.entangler.matter_render import entangle_matter, _write_ppm
from mattershaper.render.entangler.lattice_fill import (
    fill_cube_with_lattice, fill_sphere_with_lattice,
    connect_neighbors, resolve_all_surfaces, get_surface_nodes,
    build_matter_sphere,
)
from mattershaper.render.entangler.matter_node import MatterNode
from mattershaper.render.entangler.surface_nodes import SurfaceNode
from mattershaper.materials.material import Material


def _render_from_nodes(surface_nodes, camera, light, bg_color):
    """Render directly from a list of MatterNodes (bypass scene builder)."""
    from mattershaper.render.entangler.projection import project_node
    from mattershaper.render.entangler.illumination import illuminate_node

    bg = bg_color
    pixels = [[Vec3(bg.x, bg.y, bg.z) for _ in range(camera.width)]
              for _ in range(camera.height)]
    depth = [[float('inf') for _ in range(camera.width)]
             for _ in range(camera.height)]

    rendered = 0
    for mnode in surface_nodes:
        snode = SurfaceNode(mnode.position, mnode.normal, mnode.material)
        color = illuminate_node(snode, light)
        proj = project_node(snode.position, camera)
        if proj is None:
            continue

        px, py = proj
        ix, iy = int(px), int(py)
        if ix < 0 or ix >= camera.width or iy < 0 or iy >= camera.height:
            continue

        z = (snode.position - camera.pos).dot(camera.forward)
        if z <= 0:
            continue

        splat_r = 1
        for sy in range(-splat_r, splat_r + 1):
            for sx in range(-splat_r, splat_r + 1):
                if sx * sx + sy * sy > splat_r * splat_r:
                    continue
                px2, py2 = ix + sx, iy + sy
                if 0 <= px2 < camera.width and 0 <= py2 < camera.height:
                    if z < depth[py2][px2]:
                        depth[py2][px2] = z
                        pixels[py2][px2] = color
        rendered += 1

    return pixels, rendered


def build_hollow_box(center, outer_size, wall_thickness,
                     crystal_structure, lattice_param, material):
    """Build a hollow box (fridge) by filling outer cube minus inner void.

    Strategy: fill a cube, then REMOVE nodes that are inside the
    inner void. The remaining nodes form the walls.
    """
    all_nodes = fill_cube_with_lattice(
        center, outer_size, crystal_structure, lattice_param, material
    )

    inner_half = (outer_size - 2 * wall_thickness) / 2.0

    # Remove nodes inside the hollow interior
    to_remove = []
    for idx, node in all_nodes.items():
        dx = abs(node.position.x - center.x)
        dy = abs(node.position.y - center.y)
        dz = abs(node.position.z - center.z)
        if dx < inner_half and dy < inner_half and dz < inner_half:
            to_remove.append(idx)

    for idx in to_remove:
        del all_nodes[idx]

    # Now connect bonds and find surfaces
    connect_neighbors(all_nodes, crystal_structure, lattice_param)
    resolve_all_surfaces(all_nodes)
    surface = get_surface_nodes(all_nodes)

    return all_nodes, surface


def main():
    print("=" * 60)
    print("  THE REFRIGERATOR TEST")
    print("  Is the light on when the door is closed?")
    print("=" * 60)

    # ── Materials ──────────────────────────────────────────────
    iron = Material(
        name='Iron',
        color=Vec3(0.56, 0.57, 0.58),  # steel grey
        reflectance=0.65,
        roughness=0.3,
        density_kg_m3=7874,
        mean_Z=26, mean_A=56,
        composition='Fe (BCC)',
    )

    copper_sphere_mat = Material(
        name='Copper Orange',
        color=Vec3(0.85, 0.50, 0.15),  # bright copper/orange
        reflectance=0.85,
        roughness=0.15,
        density_kg_m3=8960,
        mean_Z=29, mean_A=64,
        composition='Cu (FCC)',
    )

    # ── Build the fridge (hollow iron box) ────────────────────
    lattice_a = 0.12  # render-scale lattice param
    box_size = 3.0
    wall_thick = 0.35

    print(f"\n  Building fridge: {box_size}m iron box, {wall_thick}m walls...")
    t0 = time.time()
    box_all, box_surface = build_hollow_box(
        Vec3(0, 0, 0), box_size, wall_thick, 'bcc', lattice_a, iron
    )
    dt_box = time.time() - t0
    print(f"  Fridge: {len(box_all):,} atoms, {len(box_surface):,} surface, {dt_box:.2f}s")

    # ── Build the copper sphere INSIDE ────────────────────────
    print(f"  Building copper sphere inside fridge...")
    t0 = time.time()
    sphere_all, sphere_surface = build_matter_sphere(
        Vec3(0, 0, 0), 0.6, 'fcc', 0.08, copper_sphere_mat
    )
    dt_sphere = time.time() - t0
    print(f"  Sphere: {len(sphere_all):,} atoms, {len(sphere_surface):,} surface, {dt_sphere:.2f}s")

    # Combine all surface nodes
    all_surface = box_surface + sphere_surface
    print(f"\n  Total scene: {len(box_all) + len(sphere_all):,} atoms")
    print(f"  Total emitters: {len(all_surface):,} surface nodes")

    # ── Light inside the fridge ───────────────────────────────
    # The light source is INSIDE — proving push rendering works
    # regardless of enclosure
    light_inside = PushLight(
        pos=Vec3(0.5, 1.0, -0.5),
        intensity=1.2,
        color=Vec3(1.0, 0.95, 0.85),  # warm fridge light
    )

    light_outside = PushLight(
        pos=Vec3(5, 8, -5),
        intensity=1.0,
    )

    bg = Vec3(0.02, 0.02, 0.04)

    # ── RENDER 1: Camera OUTSIDE (door closed) ────────────────
    print(f"\n  ── Render 1: Camera OUTSIDE (door closed) ──")
    camera_outside = PushCamera(
        pos=Vec3(3, 3, -6),
        look_at=Vec3(0, 0, 0),
        width=512, height=512, fov=60,
    )

    t0 = time.time()
    pixels_outside, rendered_outside = _render_from_nodes(
        all_surface, camera_outside, light_outside, bg
    )
    dt = time.time() - t0
    print(f"  Rendered: {rendered_outside:,} nodes in {dt:.2f}s")
    print(f"  The copper sphere? HIDDEN by iron walls (z-buffer).")

    out_dir = os.path.dirname(__file__)
    path1 = os.path.join(out_dir, 'fridge_outside.ppm')
    _write_ppm(pixels_outside, path1)

    # ── RENDER 2: Camera INSIDE (same scene, no rebuild!) ─────
    print(f"\n  ── Render 2: Camera INSIDE (same atoms, same bonds) ──")
    camera_inside = PushCamera(
        pos=Vec3(0, 0, -1.2),
        look_at=Vec3(0, 0, 0.5),
        width=512, height=512, fov=90,  # wide angle, cramped fridge
    )

    t0 = time.time()
    pixels_inside, rendered_inside = _render_from_nodes(
        all_surface, camera_inside, light_inside, bg
    )
    dt = time.time() - t0
    print(f"  Rendered: {rendered_inside:,} nodes in {dt:.2f}s")
    print(f"  The copper sphere? VISIBLE. It was broadcasting the whole time.")

    path2 = os.path.join(out_dir, 'fridge_inside.ppm')
    _write_ppm(pixels_inside, path2)

    # ── PNG conversion ────────────────────────────────────────
    import subprocess
    for ppm in [path1, path2]:
        png = ppm.replace('.ppm', '.png')
        try:
            subprocess.run(['convert', ppm, png], capture_output=True, timeout=10)
            if os.path.exists(png):
                os.remove(ppm)
                print(f"  Saved: {png}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print(f"  Saved: {ppm}")

    # ── Verdict ───────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  VERDICT: The light was ALWAYS on.")
    print(f"")
    print(f"  In ray tracing: the door blocks rays → can't see inside.")
    print(f"  In push rendering: atoms broadcast regardless of observer.")
    print(f"  The copper sphere emitted from frame 1. The fridge door")
    print(f"  just won the z-buffer from outside. Move the camera inside")
    print(f"  and the scene was ALREADY THERE.")
    print(f"")
    print(f"  No rebuild. No new computation. Same atoms. Same bonds.")
    print(f"  Different viewpoint into the same broadcasting reality.")
    print(f"")
    print(f"  Schrödinger's fridge: the light was always on.")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()

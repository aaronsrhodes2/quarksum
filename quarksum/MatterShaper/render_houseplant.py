"""
Houseplant Render — a potted plant built from matter primitives.

Scene:
  - Terracotta pot (hollow box, BCC ceramic lattice)
  - Dark soil filling the pot top
  - Central stem (vertical chain of small FCC spheres)
  - Leaves (FCC ellipsoid-like flattened spheres at various angles)

All geometry is lattice-based matter.  Every surface atom broadcasts
its own color — the camera is passive.  Push rendering: matter draws itself.
"""

import sys
import os
import time
import math

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.projection import PushCamera, project_node
from mattershaper.render.entangler.illumination import PushLight, illuminate_node
from mattershaper.render.entangler.matter_render import _write_ppm
from mattershaper.render.entangler.lattice_fill import (
    fill_cube_with_lattice, fill_sphere_with_lattice,
    connect_neighbors, resolve_all_surfaces, get_surface_nodes,
    build_matter_sphere,
)
from mattershaper.render.entangler.surface_nodes import (
    SurfaceNode, generate_surface_nodes,
)
from mattershaper.render.entangler.shapes import EntanglerEllipsoid, rotation_matrix
from mattershaper.materials.material import Material


# ── Rendering engine (from fridge test, extended for mixed nodes) ──

def _render_scene(surface_nodes, camera, light, bg_color):
    """Render a list of SurfaceNodes to a pixel buffer."""
    bg = bg_color
    pixels = [[Vec3(bg.x, bg.y, bg.z) for _ in range(camera.width)]
              for _ in range(camera.height)]
    depth = [[float('inf') for _ in range(camera.width)]
             for _ in range(camera.height)]

    rendered = 0
    for snode in surface_nodes:
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


def build_hollow_box(center, outer_size_x, outer_size_y, outer_size_z,
                     wall_thickness, crystal_structure, lattice_param, material):
    """Build a hollow rectangular box by filling outer cube and removing interior."""
    # Use the largest dimension to fill, then trim
    max_dim = max(outer_size_x, outer_size_y, outer_size_z)
    all_nodes = fill_cube_with_lattice(
        center, max_dim, crystal_structure, lattice_param, material
    )

    half_x = outer_size_x / 2.0
    half_y = outer_size_y / 2.0
    half_z = outer_size_z / 2.0
    inner_half_x = half_x - wall_thickness
    inner_half_y = half_y - wall_thickness
    inner_half_z = half_z - wall_thickness

    # Remove nodes outside the rectangular bounds
    to_remove = []
    for idx, node in all_nodes.items():
        dx = abs(node.position.x - center.x)
        dy = abs(node.position.y - center.y)
        dz = abs(node.position.z - center.z)
        # Outside the box entirely
        if dx > half_x or dy > half_y or dz > half_z:
            to_remove.append(idx)
        # Inside the hollow interior
        elif (dx < inner_half_x and dy < inner_half_y and dz < inner_half_z):
            to_remove.append(idx)

    for idx in to_remove:
        del all_nodes[idx]

    connect_neighbors(all_nodes, crystal_structure, lattice_param)
    resolve_all_surfaces(all_nodes)
    surface = get_surface_nodes(all_nodes)
    return all_nodes, surface


def build_flat_slab(center, size_x, size_y, size_z,
                    crystal_structure, lattice_param, material):
    """Build a solid rectangular slab."""
    max_dim = max(size_x, size_y, size_z)
    all_nodes = fill_cube_with_lattice(
        center, max_dim, crystal_structure, lattice_param, material
    )

    half_x = size_x / 2.0
    half_y = size_y / 2.0
    half_z = size_z / 2.0

    to_remove = []
    for idx, node in all_nodes.items():
        dx = abs(node.position.x - center.x)
        dy = abs(node.position.y - center.y)
        dz = abs(node.position.z - center.z)
        if dx > half_x or dy > half_y or dz > half_z:
            to_remove.append(idx)

    for idx in to_remove:
        del all_nodes[idx]

    connect_neighbors(all_nodes, crystal_structure, lattice_param)
    resolve_all_surfaces(all_nodes)
    surface = get_surface_nodes(all_nodes)
    return all_nodes, surface


def matter_to_surface(matter_nodes):
    """Convert MatterNodes to SurfaceNodes."""
    return [SurfaceNode(m.position, m.normal, m.material) for m in matter_nodes]


def main():
    print("=" * 60)
    print("  HOUSEPLANT RENDER")
    print("  Matter broadcasting from every atom")
    print("=" * 60)

    # ── Materials ──────────────────────────────────────────────
    terracotta = Material(
        name='Terracotta',
        color=Vec3(0.76, 0.40, 0.22),
        reflectance=0.25,
        roughness=0.7,
        density_kg_m3=1800,
        mean_Z=14, mean_A=28,
        composition='Clay ceramic',
    )

    soil = Material(
        name='Soil',
        color=Vec3(0.22, 0.15, 0.08),
        reflectance=0.10,
        roughness=0.9,
        density_kg_m3=1300,
        mean_Z=10, mean_A=20,
        composition='Organic soil',
    )

    stem_mat = Material(
        name='Stem',
        color=Vec3(0.25, 0.45, 0.15),
        reflectance=0.20,
        roughness=0.6,
        density_kg_m3=850,
        mean_Z=6, mean_A=12,
        composition='Plant cellulose',
    )

    leaf_dark = Material(
        name='Leaf Dark',
        color=Vec3(0.15, 0.52, 0.12),
        reflectance=0.30,
        roughness=0.4,
        density_kg_m3=700,
        mean_Z=6, mean_A=12,
        composition='Chlorophyll leaf',
    )

    leaf_light = Material(
        name='Leaf Light',
        color=Vec3(0.28, 0.62, 0.18),
        reflectance=0.35,
        roughness=0.35,
        density_kg_m3=700,
        mean_Z=6, mean_A=12,
        composition='Chlorophyll leaf',
    )

    leaf_young = Material(
        name='Leaf Young',
        color=Vec3(0.45, 0.70, 0.20),
        reflectance=0.35,
        roughness=0.3,
        density_kg_m3=650,
        mean_Z=6, mean_A=12,
        composition='Young leaf',
    )

    lattice_a = 0.10  # render-scale lattice parameter

    all_surface_nodes = []
    total_atoms = 0

    # ── Pot (hollow terracotta box) ───────────────────────────
    pot_width = 1.6
    pot_height = 1.4
    pot_depth = 1.6
    pot_wall = 0.20
    pot_center = Vec3(0, -0.7, 0)  # pot sits below origin

    print(f"\n  Building terracotta pot...")
    t0 = time.time()
    pot_all, pot_surf = build_hollow_box(
        pot_center, pot_width, pot_height, pot_depth,
        pot_wall, 'bcc', lattice_a, terracotta
    )
    dt = time.time() - t0
    print(f"  Pot: {len(pot_all):,} atoms, {len(pot_surf):,} surface, {dt:.2f}s")
    all_surface_nodes.extend(matter_to_surface(pot_surf))
    total_atoms += len(pot_all)

    # ── Soil (flat slab inside pot top) ───────────────────────
    soil_y = pot_center.y + pot_height / 2.0 - pot_wall - 0.08
    soil_center = Vec3(0, soil_y, 0)

    print(f"  Building soil...")
    t0 = time.time()
    soil_all, soil_surf = build_flat_slab(
        soil_center,
        pot_width - 2 * pot_wall - 0.05,
        0.15,
        pot_depth - 2 * pot_wall - 0.05,
        'bcc', lattice_a * 0.9, soil
    )
    dt = time.time() - t0
    print(f"  Soil: {len(soil_all):,} atoms, {len(soil_surf):,} surface, {dt:.2f}s")
    all_surface_nodes.extend(matter_to_surface(soil_surf))
    total_atoms += len(soil_all)

    # ── Stem (chain of small spheres going upward) ────────────
    print(f"  Building stem...")
    t0 = time.time()
    stem_base_y = soil_y + 0.1
    stem_segments = 8
    stem_atom_count = 0
    for i in range(stem_segments):
        frac = i / float(stem_segments - 1)
        # Slight curve
        sx = 0.08 * math.sin(frac * 1.2)
        sz = 0.05 * math.cos(frac * 0.8)
        sy = stem_base_y + i * 0.25
        seg_all, seg_surf = build_matter_sphere(
            Vec3(sx, sy, sz), 0.12, 'fcc', lattice_a * 0.7, stem_mat
        )
        all_surface_nodes.extend(matter_to_surface(seg_surf))
        stem_atom_count += len(seg_all)
    dt = time.time() - t0
    print(f"  Stem: {stem_atom_count:,} atoms, {dt:.2f}s")
    total_atoms += stem_atom_count

    # ── Leaves (ellipsoid-shaped clusters at various angles) ──
    print(f"  Building leaves...")
    t0 = time.time()

    # Each leaf: (position, radius, angle_offset, material)
    stem_top_y = stem_base_y + (stem_segments - 1) * 0.25
    leaves = [
        # Lower leaves — larger, darker
        (Vec3(0.6, stem_top_y - 0.8, 0.3), 0.45, leaf_dark),
        (Vec3(-0.5, stem_top_y - 0.7, -0.4), 0.42, leaf_dark),
        (Vec3(0.3, stem_top_y - 0.6, -0.6), 0.40, leaf_dark),
        # Middle leaves
        (Vec3(-0.5, stem_top_y - 0.3, 0.5), 0.38, leaf_light),
        (Vec3(0.55, stem_top_y - 0.2, -0.3), 0.36, leaf_light),
        (Vec3(-0.3, stem_top_y - 0.1, -0.5), 0.35, leaf_light),
        # Upper leaves — smaller, younger green
        (Vec3(0.35, stem_top_y + 0.1, 0.25), 0.30, leaf_young),
        (Vec3(-0.25, stem_top_y + 0.2, -0.2), 0.28, leaf_young),
        (Vec3(0.1, stem_top_y + 0.35, 0.15), 0.22, leaf_young),
        # Top tuft
        (Vec3(0.05, stem_top_y + 0.5, -0.05), 0.18, leaf_young),
    ]

    leaf_atom_count = 0
    for pos, radius, mat in leaves:
        # Use ellipsoid surface nodes for flat leaf shape
        ell = EntanglerEllipsoid(
            center=pos,
            radii=Vec3(radius, radius * 0.3, radius * 0.8),
            material=mat,
        )
        leaf_snodes = generate_surface_nodes(ell, density=120)
        all_surface_nodes.extend(leaf_snodes)
        leaf_atom_count += len(leaf_snodes)

    dt = time.time() - t0
    print(f"  Leaves: {leaf_atom_count:,} surface nodes, {dt:.2f}s")
    total_atoms += leaf_atom_count

    print(f"\n  Total scene: {total_atoms:,} atoms/nodes")
    print(f"  Total emitters: {len(all_surface_nodes):,}")

    # ── Lighting ──────────────────────────────────────────────
    light = PushLight(
        pos=Vec3(4, 6, -5),
        intensity=1.1,
        color=Vec3(1.0, 0.97, 0.90),  # warm sunlight
    )

    bg = Vec3(0.85, 0.88, 0.92)  # soft sky background

    # ── Camera ────────────────────────────────────────────────
    print(f"\n  Rendering 512x512...")
    camera = PushCamera(
        pos=Vec3(2.5, 1.5, -4.5),
        look_at=Vec3(0, 0.3, 0),
        width=512, height=512, fov=50,
    )

    t0 = time.time()
    pixels, rendered = _render_scene(all_surface_nodes, camera, light, bg)
    dt = time.time() - t0
    print(f"  Rendered: {rendered:,} nodes in {dt:.2f}s")

    # ── Save ──────────────────────────────────────────────────
    out_dir = os.path.dirname(__file__)
    path_ppm = os.path.join(out_dir, 'houseplant.ppm')
    _write_ppm(pixels, path_ppm)

    # Try PNG conversion
    import subprocess
    path_png = path_ppm.replace('.ppm', '.png')
    try:
        subprocess.run(['convert', path_ppm, path_png],
                       capture_output=True, timeout=10)
        if os.path.exists(path_png):
            os.remove(path_ppm)
            print(f"  Saved: {path_png}")
        else:
            print(f"  Saved: {path_ppm}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"  Saved: {path_ppm}")

    print(f"\n{'=' * 60}")
    print(f"  Every atom in this plant broadcast its own color.")
    print(f"  The camera didn't ask. Matter just speaks.")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()

"""
Entanglement Stress Tests — two experiments that break the observation problem.

═══════════════════════════════════════════════════════════════════════
TEST 1: THE FOREST TEST
  "If a tree falls in a forest and no one is around, does it make a sound?"

  Push rendering answer: YES. The tree's atoms are broadcasting whether
  or not a camera exists. We build the tree, then place a camera later.
  The tree was always there.

═══════════════════════════════════════════════════════════════════════
TEST 2: SCHRÖDINGER'S CRYSTAL
  The classic cat paradox — but humane. No cats harmed.

  Setup: A sealed iron box containing a copper crystal and a "σ-trigger."
  The σ-field may or may not have spiked past σ_conv ≈ 1.849.
  - If σ stayed low: crystal is INTACT (bonds hold, lattice stands)
  - If σ spiked high: crystal SHATTERED (bonds broke, atoms scattered)

  In quantum mechanics: until observed, the crystal is in superposition.
  In push rendering: the atoms INSIDE were broadcasting one definite
  state the entire time. The box just blocks the z-buffer.

  "Collapse" isn't observation — it's just moving the camera.
═══════════════════════════════════════════════════════════════════════
"""

import sys
import os
import math
import time
import random

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.projection import PushCamera, project_node
from mattershaper.render.entangler.illumination import PushLight, illuminate_node
from mattershaper.render.entangler.matter_render import _write_ppm
from mattershaper.render.entangler.lattice_fill import (
    fill_cube_with_lattice, fill_sphere_with_lattice,
    connect_neighbors, resolve_all_surfaces, get_surface_nodes,
    build_matter_cube, build_matter_sphere, COORDINATION,
)
from mattershaper.render.entangler.matter_node import MatterNode
from mattershaper.render.entangler.surface_nodes import SurfaceNode
from mattershaper.materials.material import Material


def _render_nodes(surface_nodes, camera, light, bg_color):
    """Render from a list of MatterNodes."""
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


def _save_png(pixels, name, out_dir):
    """Save pixels as PPM, convert to PNG if possible."""
    ppm = os.path.join(out_dir, f'{name}.ppm')
    _write_ppm(pixels, ppm)
    try:
        import subprocess
        png = os.path.join(out_dir, f'{name}.png')
        subprocess.run(['convert', ppm, png], capture_output=True, timeout=10)
        if os.path.exists(png):
            os.remove(ppm)
            return png
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ppm


def build_hollow_box(center, size, wall_thick, struct, a, material):
    """Build hollow box walls."""
    all_nodes = fill_cube_with_lattice(center, size, struct, a, material)
    inner_half = (size - 2 * wall_thick) / 2.0
    to_remove = []
    for idx, node in all_nodes.items():
        dx = abs(node.position.x - center.x)
        dy = abs(node.position.y - center.y)
        dz = abs(node.position.z - center.z)
        if dx < inner_half and dy < inner_half and dz < inner_half:
            to_remove.append(idx)
    for idx in to_remove:
        del all_nodes[idx]
    connect_neighbors(all_nodes, struct, a)
    resolve_all_surfaces(all_nodes)
    return all_nodes, get_surface_nodes(all_nodes)


def build_cylinder(center, radius, height, struct, a, material):
    """Build a cylinder by filling a cube and carving to circular cross-section."""
    # Fill a tall box
    all_nodes = fill_cube_with_lattice(
        center, max(2 * radius, height) + a, struct, a, material
    )
    # Keep only nodes within the cylinder
    to_remove = []
    half_h = height / 2.0
    for idx, node in all_nodes.items():
        dx = node.position.x - center.x
        dz = node.position.z - center.z
        dy = node.position.y - center.y
        r = math.sqrt(dx * dx + dz * dz)
        if r > radius or abs(dy) > half_h:
            to_remove.append(idx)
    for idx in to_remove:
        del all_nodes[idx]
    connect_neighbors(all_nodes, struct, a)
    resolve_all_surfaces(all_nodes)
    return all_nodes, get_surface_nodes(all_nodes)


def shatter_crystal(nodes, center, intensity=2.0, seed=42):
    """Shatter a crystal by displacing atoms based on σ-spike.

    At σ > σ_conv ≈ 1.849, nuclear bonds fail. The lattice structure
    disintegrates. Atoms scatter from their lattice sites.

    We model this as: each atom is displaced from its lattice position
    by a random vector scaled by the σ-spike intensity. Bonds break
    because neighbors are no longer at the expected distance.

    The material changes: lattice-ordered copper → disordered debris.
    """
    rng = random.Random(seed)

    # Create a debris material (dull, scattered)
    debris_mat = Material(
        name='Shattered Cu',
        color=Vec3(0.45, 0.30, 0.12),  # tarnished, dull
        reflectance=0.1,
        roughness=0.9,
        density_kg_m3=8960,
        mean_Z=29, mean_A=64,
        composition='Cu (shattered, bonds broken)',
    )

    shattered = {}
    for idx, node in nodes.items():
        # Displacement proportional to σ-spike and distance from center
        d_to_center = node.position - center
        dist = d_to_center.length()

        # Explosion-like: atoms further out scatter more
        scatter = intensity * (0.5 + dist * 0.3)
        dx = rng.gauss(0, scatter * 0.3)
        dy = rng.gauss(0, scatter * 0.3)
        dz = rng.gauss(0, scatter * 0.3)

        new_pos = Vec3(
            node.position.x + dx,
            node.position.y + dy,
            node.position.z + dz,
        )

        new_node = MatterNode(new_pos, idx, debris_mat, node.max_neighbors)
        # No bonds form (everything is scattered beyond NN distance)
        new_node.is_surface = True  # All atoms exposed
        new_node.normal = (new_pos - center).normalized()
        shattered[idx] = new_node

    return shattered, list(shattered.values())


# ═══════════════════════════════════════════════════════════════════
# TEST 1: THE FOREST TEST
# ═══════════════════════════════════════════════════════════════════

def test_forest():
    print("\n" + "=" * 60)
    print("  TEST 1: THE FOREST TEST")
    print("  If a tree exists and no camera is around...")
    print("=" * 60)

    # ── Materials ──────────────────────────────────────────────
    bark = Material(
        name='Oak Bark',
        color=Vec3(0.36, 0.22, 0.10),
        reflectance=0.05, roughness=0.85,
        density_kg_m3=600, mean_Z=6, mean_A=12,
        composition='Cellulose (C₆H₁₀O₅)n',
    )
    leaves = Material(
        name='Leaves',
        color=Vec3(0.15, 0.55, 0.12),
        reflectance=0.08, roughness=0.7,
        density_kg_m3=700, mean_Z=7, mean_A=14,
        composition='Chlorophyll + cellulose',
    )
    ground = Material(
        name='Earth',
        color=Vec3(0.28, 0.18, 0.08),
        reflectance=0.02, roughness=0.95,
        density_kg_m3=1500, mean_Z=11, mean_A=22,
        composition='Silicate soil',
    )

    a = 0.12  # lattice param (render-scale)

    # ── PHASE 1: Build the tree (NO CAMERA EXISTS) ────────────
    print("\n  Phase 1: Building tree... (no camera exists yet)")

    t0 = time.time()

    # Trunk: cylinder
    print("    Trunk (iron-BCC analog for wood)...")
    trunk_all, trunk_surf = build_cylinder(
        Vec3(0, 0.8, 0), 0.25, 1.6, 'bcc', a, bark
    )

    # Canopy: three overlapping spheres
    print("    Canopy spheres...")
    canopy_nodes = []
    canopy_centers = [Vec3(0, 2.2, 0), Vec3(0.4, 2.5, 0.2), Vec3(-0.3, 2.4, -0.2)]
    canopy_radii = [0.7, 0.5, 0.55]
    for c, r in zip(canopy_centers, canopy_radii):
        _, surf = build_matter_sphere(c, r, 'fcc', a * 0.8, leaves)
        canopy_nodes.extend(surf)

    # Ground plane: flat cube
    print("    Ground plane...")
    _, ground_surf = build_matter_cube(
        Vec3(0, -0.3, 0), 4.0, 'bcc', a * 1.5, ground
    )
    # Only keep top-facing ground nodes
    ground_surf = [n for n in ground_surf if n.normal.y > 0.3]

    all_surface = trunk_surf + canopy_nodes + ground_surf
    dt = time.time() - t0

    total_atoms = len(trunk_all) + sum(
        len(fill_sphere_with_lattice(c, r, 'fcc', a * 0.8, leaves))
        for c, r in zip(canopy_centers, canopy_radii)
    )

    print(f"\n    Tree built: ~{total_atoms:,} atoms, {len(all_surface):,} emitters")
    print(f"    Build time: {dt:.2f}s")
    print(f"    Camera count: 0 (tree is broadcasting to nobody)")

    # ── PHASE 2: Drop a camera in ────────────────────────────
    print("\n  Phase 2: Placing camera... (tree was always here)")

    light = PushLight(pos=Vec3(4, 6, -3), intensity=1.0,
                      color=Vec3(1.0, 0.95, 0.85))
    bg = Vec3(0.45, 0.65, 0.90)  # sky blue

    camera = PushCamera(
        pos=Vec3(3, 2.5, -4),
        look_at=Vec3(0, 1.2, 0),
        width=512, height=512, fov=50,
    )

    t0 = time.time()
    pixels, rendered = _render_nodes(all_surface, camera, light, bg)
    dt = time.time() - t0

    print(f"    Rendered: {rendered:,} nodes in {dt:.2f}s")
    print(f"    The tree was broadcasting the entire time.")
    print(f"    The camera didn't create the tree. It just tuned in.")

    out_dir = os.path.dirname(__file__)
    path = _save_png(pixels, 'forest_test', out_dir)
    print(f"    Saved: {path}")

    return path


# ═══════════════════════════════════════════════════════════════════
# TEST 2: SCHRÖDINGER'S CRYSTAL
# ═══════════════════════════════════════════════════════════════════

def test_schrodinger():
    print("\n" + "=" * 60)
    print("  TEST 2: SCHRÖDINGER'S CRYSTAL")
    print("  σ-decay: is the crystal intact or shattered?")
    print("  (No cats were harmed in this experiment)")
    print("=" * 60)

    # ── Materials ──────────────────────────────────────────────
    iron = Material(
        name='Iron Box',
        color=Vec3(0.50, 0.50, 0.52),
        reflectance=0.6, roughness=0.3,
        density_kg_m3=7874, mean_Z=26, mean_A=56,
        composition='Fe (BCC)',
    )
    copper = Material(
        name='Pure Copper Crystal',
        color=Vec3(0.85, 0.50, 0.15),
        reflectance=0.85, roughness=0.15,
        density_kg_m3=8960, mean_Z=29, mean_A=64,
        composition='Cu (FCC)',
    )

    a_box = 0.12
    a_crystal = 0.07

    # ── Build the sealed box ──────────────────────────────────
    print("\n  Building sealed iron box...")
    box_all, box_surf = build_hollow_box(
        Vec3(0, 0, 0), 3.0, 0.35, 'bcc', a_box, iron
    )
    print(f"    Box: {len(box_all):,} atoms, {len(box_surf):,} surface")

    # ── Build the crystal INSIDE ──────────────────────────────
    print("  Building copper crystal inside box...")
    crystal_all, crystal_surf = build_matter_sphere(
        Vec3(0, 0, 0), 0.6, 'fcc', a_crystal, copper
    )
    print(f"    Crystal: {len(crystal_all):,} atoms, {len(crystal_surf):,} surface")

    # ── σ-DECAY: Two possible outcomes ────────────────────────
    # The σ-trigger has fired. One of two things happened:
    print("\n  σ-trigger activated inside the box!")
    print("  Outcome determined by physics, not observation.")

    # STATE A: σ stayed below σ_conv → crystal intact
    state_a_surface = box_surf + crystal_surf
    print(f"    State A (σ < σ_conv): crystal INTACT — {len(crystal_surf):,} atoms broadcasting")

    # STATE B: σ spiked past σ_conv → bonds broke → atoms scattered
    shattered_all, shattered_surf = shatter_crystal(
        crystal_all, Vec3(0, 0, 0), intensity=0.4
    )
    # Filter to only those inside the box
    inner_half = (3.0 - 2 * 0.35) / 2.0
    shattered_inside = [
        n for n in shattered_surf
        if (abs(n.position.x) < inner_half and
            abs(n.position.y) < inner_half and
            abs(n.position.z) < inner_half)
    ]
    state_b_surface = box_surf + shattered_inside
    print(f"    State B (σ > σ_conv): crystal SHATTERED — {len(shattered_inside):,} debris atoms broadcasting")

    # ── Lights ────────────────────────────────────────────────
    light_outside = PushLight(pos=Vec3(5, 8, -5), intensity=1.0)
    light_inside = PushLight(pos=Vec3(0.5, 0.8, -0.5), intensity=1.2,
                             color=Vec3(1.0, 0.95, 0.85))
    bg = Vec3(0.02, 0.02, 0.04)

    out_dir = os.path.dirname(__file__)

    # ── RENDER: Outside view (can't tell which state) ─────────
    print(f"\n  ── View from OUTSIDE (sealed box) ──")
    cam_out = PushCamera(
        pos=Vec3(3, 3, -6), look_at=Vec3(0, 0, 0),
        width=512, height=512, fov=60,
    )

    # Both states look the same from outside!
    pixels_out, r = _render_nodes(state_a_surface, cam_out, light_outside, bg)
    print(f"    Rendered: {r:,} nodes")
    print(f"    From here: INDETERMINATE. The box hides the outcome.")
    path_out = _save_png(pixels_out, 'schrodinger_outside', out_dir)
    print(f"    Saved: {path_out}")

    # ── RENDER: Inside view — STATE A (crystal intact) ────────
    print(f"\n  ── View from INSIDE — State A: Crystal INTACT ──")
    cam_in = PushCamera(
        pos=Vec3(0, 0, -1.2), look_at=Vec3(0, 0, 0.5),
        width=512, height=512, fov=90,
    )

    pixels_a, r = _render_nodes(state_a_surface, cam_in, light_inside, bg)
    print(f"    Rendered: {r:,} nodes")
    print(f"    The crystal is HERE. Intact. Bonds holding. Broadcasting copper.")
    path_a = _save_png(pixels_a, 'schrodinger_intact', out_dir)
    print(f"    Saved: {path_a}")

    # ── RENDER: Inside view — STATE B (crystal shattered) ─────
    print(f"\n  ── View from INSIDE — State B: Crystal SHATTERED ──")

    pixels_b, r = _render_nodes(state_b_surface, cam_in, light_inside, bg)
    print(f"    Rendered: {r:,} nodes")
    print(f"    Debris cloud. Bonds broken. σ exceeded σ_conv ≈ 1.849.")
    print(f"    The atoms are still broadcasting — just from scattered positions.")
    path_b = _save_png(pixels_b, 'schrodinger_shattered', out_dir)
    print(f"    Saved: {path_b}")

    return path_out, path_a, path_b


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print("╔" + "═" * 58 + "╗")
    print("║  ENTANGLEMENT STRESS TESTS                              ║")
    print("║  Matter broadcasts. The camera is just a viewpoint.     ║")
    print("╚" + "═" * 58 + "╝")

    forest_path = test_forest()

    schro_out, schro_a, schro_b = test_schrodinger()

    print("\n" + "=" * 60)
    print("  CONCLUSIONS")
    print("=" * 60)
    print("""
  1. THE FOREST: The tree existed before any camera. Its atoms
     were broadcasting from the moment they were placed. The camera
     didn't create the scene — it tuned into an existing broadcast.

  2. SCHRÖDINGER'S CRYSTAL: From outside the box, the state is
     hidden (z-buffer occlusion, not superposition). From inside,
     the crystal was ALWAYS in one definite state — intact OR
     shattered. The atoms knew. They were broadcasting.

     The "collapse" isn't caused by observation.
     It's caused by moving your viewpoint into the broadcast range.

  In push rendering, there is no observer effect.
  Matter is always on. Reality is always broadcasting.
  You just choose where to listen.

  Entanglement is reality's TV.
""")


if __name__ == '__main__':
    main()

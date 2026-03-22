"""
MatterShaper — Coffee Cup Scene v2 (Decomposition Method).

Instead of one big ellipsoid per shape, we DECOMPOSE each object
into many small primitives packed together. The surface emerges
from the union of hundreds of shapes — every bump, ridge, and
curve is defined by adding another sphere or ellipsoid from inside.

Technique:
  - Cup wall: rings of spheres stacked vertically (cylinder from spheres)
  - Rim: tighter ring at the top with slight outward flare
  - Handle: chain of spheres forming a curved loop
  - Base: disc of spheres
  - Coffee surface: cluster of overlapping flat ellipsoids (meniscus)
  - Broken shards: fans of flat ellipsoids at scattered angles
  - Spill: organic network of overlapping puddle-ellipsoids
"""

import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper import MatterShaper, Material, Vec3


# ── Materials ────────────────────────────────────────────────────────

CERAMIC = Material(
    name="White Ceramic", color=Vec3(0.92, 0.90, 0.85),
    reflectance=0.12, roughness=0.25,
    density_kg_m3=2400, mean_Z=11, mean_A=22,
    composition='SiO₂ + Al₂O₃ (porcelain)',
)

CERAMIC_RIM = Material(
    name="Ceramic Rim", color=Vec3(0.96, 0.94, 0.90),
    reflectance=0.20, roughness=0.15,
)

CERAMIC_INNER = Material(
    name="Ceramic Inner", color=Vec3(0.88, 0.85, 0.80),
    reflectance=0.08, roughness=0.35,
)

CERAMIC_BASE = Material(
    name="Ceramic Base", color=Vec3(0.85, 0.82, 0.78),
    reflectance=0.06, roughness=0.40,
)

CERAMIC_STAINED = Material(
    name="Coffee-Stained Ceramic", color=Vec3(0.72, 0.62, 0.50),
    reflectance=0.08, roughness=0.45,
)

COFFEE_SURFACE = Material(
    name="Coffee", color=Vec3(0.25, 0.14, 0.07),
    reflectance=0.35, roughness=0.05,
)

COFFEE_WET = Material(
    name="Coffee Spill", color=Vec3(0.22, 0.12, 0.06),
    reflectance=0.45, roughness=0.02,
)

COFFEE_EDGE = Material(
    name="Coffee Edge", color=Vec3(0.18, 0.10, 0.05),
    reflectance=0.30, roughness=0.08,
)

STEEL_FLOOR = Material(
    name="Brushed Steel", color=Vec3(0.55, 0.56, 0.58),
    reflectance=0.45, roughness=0.20,
    density_kg_m3=7800, mean_Z=26, mean_A=56,
)


# ── Shape Builders ───────────────────────────────────────────────────

def ring_of_spheres(ms, cx, cy, cz, radius, sphere_r, n, material):
    """Place n spheres in a ring (horizontal circle)."""
    for i in range(n):
        angle = 2 * math.pi * i / n
        x = cx + radius * math.cos(angle)
        z = cz + radius * math.sin(angle)
        ms.sphere(pos=(x, cy, z), radius=sphere_r, material=material)


def cylinder_wall(ms, cx, cz, base_y, height, radius, sphere_r,
                  rings, per_ring, material, taper_top=1.0, taper_bottom=1.0):
    """Build a cylindrical wall from stacked rings of spheres.

    taper_top/taper_bottom: radius multiplier at top/bottom (1.0 = straight).
    """
    for ring_i in range(rings):
        t = ring_i / max(1, rings - 1)  # 0 at bottom, 1 at top
        y = base_y + height * t
        # Interpolate taper
        taper = taper_bottom + (taper_top - taper_bottom) * t
        r = radius * taper
        ring_of_spheres(ms, cx, y, cz, r, sphere_r, per_ring, material)


def handle_arc(ms, cx, cy, cz, width, height, n, sphere_r, material):
    """Build a handle as a chain of spheres along a half-ellipse arc."""
    for i in range(n):
        t = i / max(1, n - 1)
        angle = math.pi * t  # 0 to π (half circle, top to bottom)
        x = cx + width * math.cos(angle)  # actually goes right then left, but we want outward
        # Actually: handle sticks out to the side
        # Arc in the XY plane, offset in X
        hx = cx + width * math.sin(angle)
        hy = cy + height * 0.5 - height * t  # top to bottom
        ms.sphere(pos=(hx, hy, cz), radius=sphere_r, material=material)


def disc(ms, cx, cy, cz, radius, n_rings, material):
    """Fill a disc with concentric rings of spheres."""
    for r_i in range(n_rings):
        t = (r_i + 1) / n_rings
        r = radius * t
        circumference = 2 * math.pi * r
        sphere_r = radius / (n_rings * 1.8)
        n_in_ring = max(4, int(circumference / (sphere_r * 1.6)))
        ring_of_spheres(ms, cx, cy, cz, r, sphere_r, n_in_ring, material)
    # Center sphere
    ms.sphere(pos=(cx, cy, cz), radius=radius / (n_rings * 1.5), material=material)


def coffee_surface(ms, cx, cy, cz, radius, material):
    """Coffee surface with meniscus — overlapping flat ellipsoids."""
    # Main surface
    ms.ellipsoid(pos=(cx, cy, cz), radii=(radius * 0.85, 0.012, radius * 0.85),
                 material=material)
    # Meniscus ring — slightly higher at edges, touching the cup wall
    n_edge = 14
    for i in range(n_edge):
        angle = 2 * math.pi * i / n_edge
        ex = cx + radius * 0.80 * math.cos(angle)
        ez = cz + radius * 0.80 * math.sin(angle)
        ms.ellipsoid(
            pos=(ex, cy + 0.005, ez),
            radii=(0.06, 0.008, 0.06),
            material=material,
        )


def spill_puddle(ms, cx, cy, cz, main_radius, tendrils, material, edge_mat):
    """Organic coffee puddle — central blob with irregular tendrils."""
    # Central puddle body — several overlapping ellipsoids
    ms.ellipsoid(pos=(cx, cy, cz), radii=(main_radius * 0.7, 0.006, main_radius * 0.6),
                 rotate=(0, 0.15, 0), material=material)
    ms.ellipsoid(pos=(cx + 0.05, cy, cz - 0.03),
                 radii=(main_radius * 0.5, 0.005, main_radius * 0.55),
                 rotate=(0, -0.2, 0), material=material)

    # Tendrils — elongated ellipsoids radiating outward
    for angle, length, width, offset in tendrils:
        tx = cx + offset * math.cos(angle)
        tz = cz + offset * math.sin(angle)
        ms.ellipsoid(
            pos=(tx, cy - 0.001, tz),
            radii=(length, 0.004, width),
            rotate=(0, angle, 0),
            material=edge_mat,
        )

    # Droplets — small spheres around the periphery
    n_drops = 8
    for i in range(n_drops):
        a = 2 * math.pi * i / n_drops + 0.3
        dr = main_radius * (0.9 + 0.4 * math.sin(i * 2.7))
        dx = cx + dr * math.cos(a)
        dz = cz + dr * math.sin(a)
        drop_r = 0.008 + 0.006 * (i % 3)
        ms.sphere(pos=(dx, cy + drop_r * 0.5, dz), radius=drop_r, material=material)


def shard_cluster(ms, cx, cy, cz, shards, material_a, material_b):
    """Scatter ceramic shards — each shard is a fan of flat ellipsoids."""
    for i, (dx, dz, size, rx, ry, rz) in enumerate(shards):
        mat = material_a if i % 2 == 0 else material_b
        # Main shard body
        ms.ellipsoid(
            pos=(cx + dx, cy + size * 0.3, cz + dz),
            radii=(size, size * 0.15, size * 0.7),
            rotate=(rx, ry, rz),
            material=mat,
        )
        # Secondary piece layered on top for thickness variation
        ms.ellipsoid(
            pos=(cx + dx + 0.01, cy + size * 0.4, cz + dz + 0.01),
            radii=(size * 0.6, size * 0.1, size * 0.5),
            rotate=(rx + 0.2, ry - 0.1, rz + 0.3),
            material=mat,
        )


# ── Scene Assembly ───────────────────────────────────────────────────

def build_intact_cup(ms, cx, cz):
    """Intact coffee cup built from decomposed primitives."""
    base_y = 0.01

    # Cup wall: 8 rings of 18 spheres each, slight outward taper at top
    cylinder_wall(
        ms, cx, cz,
        base_y=base_y + 0.04,
        height=0.72,
        radius=0.34,
        sphere_r=0.065,
        rings=8,
        per_ring=18,
        material=CERAMIC,
        taper_top=1.08,
        taper_bottom=0.95,
    )

    # Rim ring: tighter, shinier spheres at top
    ring_of_spheres(ms, cx, base_y + 0.78, cz, 0.37, 0.04, 22, CERAMIC_RIM)

    # Inner wall visible at top: slightly smaller ring just below rim
    ring_of_spheres(ms, cx, base_y + 0.70, cz, 0.28, 0.05, 14, CERAMIC_INNER)

    # Base disc
    disc(ms, cx, base_y, cz, 0.30, 3, CERAMIC_BASE)

    # Handle: arc of spheres on the right side
    handle_n = 10
    handle_width = 0.18
    handle_height = 0.40
    handle_cx = cx + 0.38
    handle_cy = base_y + 0.50
    for i in range(handle_n):
        t = i / max(1, handle_n - 1)
        angle = math.pi * t
        hx = handle_cx + handle_width * math.sin(angle)
        hy = handle_cy + handle_height * (0.5 - t)
        # Sphere slightly smaller in middle of arc
        r = 0.04 + 0.015 * math.sin(angle)
        ms.sphere(pos=(hx, hy, cz), radius=r, material=CERAMIC)

    # Coffee surface
    coffee_surface(ms, cx, base_y + 0.65, cz, 0.30, COFFEE_SURFACE)


def build_broken_cup(ms, cx, cz):
    """Broken cup: tipped over, spilling coffee."""
    base_y = 0.0
    tip_angle_z = math.radians(-80)  # nearly on its side

    # ── Remaining cup body (tipped) ──
    # Build a partial cylinder, tipped over
    # We'll build rings but rotated as a group
    cos_t, sin_t = math.cos(tip_angle_z), math.sin(tip_angle_z)

    rings = 6
    per_ring = 14
    cup_h = 0.72
    cup_r = 0.34
    sphere_r = 0.06

    # The cup's local Y axis is now nearly horizontal
    for ring_i in range(rings):
        t = ring_i / max(1, rings - 1)
        local_y = cup_h * t  # along cup's axis

        # Only render back half of the cup (front is "broken off")
        for j in range(per_ring):
            angle = 2 * math.pi * j / per_ring

            # Skip some front-facing spheres to create the broken mouth
            # "Front" in local coords is +Z direction
            if t > 0.6 and math.cos(angle) > 0.3:
                continue  # broken away at the front-top

            # Local position (before tipping)
            local_x = cup_r * math.cos(angle)
            local_z = cup_r * math.sin(angle)

            # Apply tip rotation (around Z axis)
            # Rotate the local Y into world space
            world_x = cx + local_x
            world_y = base_y + 0.28 + local_y * cos_t
            world_z = cz + local_z + local_y * (-sin_t) * 0.1  # slight forward lean

            # Adjust height so cup sits on floor
            world_y = max(sphere_r, world_y * 0.85 + 0.05)

            ms.sphere(pos=(world_x, world_y, world_z), radius=sphere_r, material=CERAMIC)

    # ── Scattered shards ──
    shard_cluster(ms, cx, base_y, cz, [
        (0.50, 0.22, 0.10, 0.3, 0.5, 0.8),     # large piece, flung right
        (0.35, -0.28, 0.08, -0.4, 0.2, 1.2),    # medium, forward-left
        (0.68, -0.08, 0.06, 0.6, -0.3, 0.4),    # small, far right
        (0.82, 0.12, 0.05, 1.0, 0.7, -0.2),     # tiny, very far right
        (-0.12, 0.32, 0.07, -0.8, 0.1, 2.0),    # piece behind cup
        (0.25, 0.40, 0.04, 0.2, -0.6, 1.5),     # small chip
    ], CERAMIC, CERAMIC_STAINED)

    # ── Broken handle ── separated from body
    for i in range(5):
        t = i / 4
        hx = cx - 0.25 + 0.08 * math.sin(math.pi * t)
        hy = 0.03 + 0.04 * math.sin(math.pi * t)
        hz = cz - 0.35 + 0.12 * t
        ms.sphere(pos=(hx, hy, hz), radius=0.035 + 0.01 * math.sin(math.pi * t),
                  material=CERAMIC)

    # ── Coffee spill ──
    spill_cx = cx + 0.45
    spill_cz = cz + 0.10
    spill_puddle(
        ms, spill_cx, 0.004, spill_cz,
        main_radius=0.55,
        tendrils=[
            (0.3, 0.22, 0.06, 0.40),      # tendril toward viewer
            (1.1, 0.18, 0.05, 0.35),       # tendril right
            (2.0, 0.25, 0.07, 0.30),       # tendril back-right
            (-0.5, 0.15, 0.04, 0.45),      # tendril left
            (0.8, 0.12, 0.04, 0.50),       # thin runner
            (1.8, 0.20, 0.05, 0.42),       # back runner
        ],
        material=COFFEE_WET,
        edge_mat=COFFEE_EDGE,
    )

    # Coffee stream still pouring from cup mouth
    stream_n = 8
    for i in range(stream_n):
        t = i / max(1, stream_n - 1)
        sx = cx + 0.15 + 0.25 * t
        sy = 0.22 * (1 - t) + 0.02  # arc downward
        sz = cz + 0.05 + 0.05 * t
        r = 0.035 * (1 - t * 0.6)  # thins as it falls
        ms.sphere(pos=(sx, sy, sz), radius=r, material=COFFEE_SURFACE)


def build_scene():
    ms = MatterShaper()
    ms.background(0.04, 0.04, 0.06)
    ms.ambient(0.07, 0.07, 0.09)

    # Steel floor
    ms.plane(y=0, material=STEEL_FLOOR)

    # Intact cup — left side
    build_intact_cup(ms, -1.1, -2.8)

    # Broken cup — right side
    build_broken_cup(ms, 1.0, -2.8)

    # Lighting — overhead studio
    ms.light(pos=(0, 6, 0), color=(1.0, 0.98, 0.95), intensity=0.85)
    ms.light(pos=(-4, 3, -1), color=(1.0, 0.92, 0.78), intensity=0.35)
    ms.light(pos=(3, 2.5, -5), color=(0.7, 0.78, 1.0), intensity=0.30)
    ms.light(pos=(0, 0.3, 1), color=(0.8, 0.8, 0.85), intensity=0.12)

    # Camera — eye level, looking at both cups
    ms.camera(
        pos=(0, 1.6, 1.0),
        look_at=(0, 0.25, -2.8),
        fov=48,
    )

    return ms


def main():
    print("MatterShaper — Coffee Cups v2 (Decomposition)")
    print("=" * 52)
    print("Every bump and wrinkle defined by packed primitives.\n")

    ms = build_scene()
    print(ms)

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'renders')
    os.makedirs(out_dir, exist_ok=True)

    # Render
    width, height = 400, 300
    print(f"\nRendering {width}×{height} ({width*height:,} rays)...")
    t0 = time.time()
    result = ms.render(
        os.path.join(out_dir, 'coffee_cups_v2.png'),
        width=width, height=height,
    )
    t1 = time.time()
    print(f"Done in {t1-t0:.2f}s")
    print(f"Objects: {result['objects']}, Lights: {result['lights']}")
    print(f"PNG: {result['filepath']}")
    print("Done.")


if __name__ == '__main__':
    main()

"""
MatterShaper — Coffee Cup Scene v3 (Coaxial Ellipsoid Method).

v2 used hundreds of spheres to build the cup wall — looked like marbles.
v3 uses the right primitive for each job:

  Cup wall:   Coaxial ring of ellipsoids — each ellipsoid's long axis
              follows the tangent of the circle. One ellipsoid replaces
              3-4 spheres. Stacked rings with overlap = smooth wall.
  Rim:        Single torus-ring of slightly flared ellipsoids.
  Base:       One flat ellipsoid (disc), not a field of spheres.
  Handle:     Chain of ellipsoids oriented along the arc, not spheres.
  Coffee:     One flat ellipsoid (liquid surface).
  Shards:     Oriented flat ellipsoids (they were already correct).
  Puddle:     Overlapping flat ellipsoids (already correct).

Principle: ellipsoids for surfaces, spheres only for joints and accents.
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


# ── Coaxial Ring Builder ─────────────────────────────────────────────

def coaxial_ring(ms, cx, cy, cz, ring_radius, n_segments,
                 cross_h, cross_w, material):
    """Build a torus-like ring from tangent-oriented ellipsoids.

    Each ellipsoid's long axis follows the tangent of the ring circle.
    The cross-section is defined by cross_h (height) and cross_w (wall thickness).

    Args:
        ring_radius: radius of the ring centerline
        n_segments: number of ellipsoids around the ring
        cross_h: height of each segment (vertical extent)
        cross_w: wall thickness (radial extent)
    """
    for i in range(n_segments):
        angle = 2 * math.pi * i / n_segments
        # Position on the ring
        px = cx + ring_radius * math.cos(angle)
        pz = cz + ring_radius * math.sin(angle)

        # Tangent direction = perpendicular to radial in XZ plane
        # Radial: (cos θ, 0, sin θ)
        # Tangent: (-sin θ, 0, cos θ)
        # The ellipsoid's long axis should align with this tangent.
        # We rotate around Y by -angle to align the X-axis with the tangent.

        # Arc length each segment covers
        arc_half = math.pi * ring_radius / n_segments  # half the arc per segment

        ms.ellipsoid(
            pos=(px, cy, pz),
            radii=(arc_half * 1.15, cross_h, cross_w),  # long axis = arc, then height, then thickness
            rotate=(0, -angle + math.pi/2, 0),  # align long axis with tangent
            material=material,
        )


def coaxial_wall(ms, cx, cz, base_y, height, ring_radius, wall_thickness,
                 n_rings, segments_per_ring, material,
                 taper_top=1.0, taper_bottom=1.0):
    """Build a cylindrical wall from stacked coaxial rings.

    Each ring is a set of tangent-aligned ellipsoids.
    Rings overlap vertically for a continuous surface.
    """
    ring_h = height / n_rings * 0.65  # vertical extent per segment (overlap)

    for ring_i in range(n_rings):
        t = ring_i / max(1, n_rings - 1)
        y = base_y + height * t
        taper = taper_bottom + (taper_top - taper_bottom) * t
        r = ring_radius * taper

        coaxial_ring(
            ms, cx, y, cz,
            ring_radius=r,
            n_segments=segments_per_ring,
            cross_h=ring_h,
            cross_w=wall_thickness,
            material=material,
        )


def handle_arc(ms, cx, cy, cz, width, height, n_segments, thickness, material):
    """Build a handle from arc-aligned ellipsoids.

    Each ellipsoid is oriented tangent to the arc curve.
    """
    for i in range(n_segments):
        t = i / max(1, n_segments - 1)
        t_next = min(1.0, (i + 1) / max(1, n_segments - 1))

        angle = math.pi * t
        angle_next = math.pi * t_next

        # Position on the arc (semicircle in XY plane, bulging outward in X)
        hx = cx + width * math.sin(angle)
        hy = cy + height * (0.5 - t)

        # Tangent direction (derivative of position)
        dx = width * math.cos(angle)
        dy = -height

        # Arc segment length (approximate)
        seg_len = math.sqrt(dx**2 + dy**2) * (math.pi / n_segments) * 0.6

        # Orientation: tilt the ellipsoid to follow the arc
        # The tangent angle in the XY plane
        tilt = math.atan2(dx, -dy)

        ms.ellipsoid(
            pos=(hx, hy, cz),
            radii=(thickness, seg_len, thickness * 0.85),
            rotate=(0, 0, tilt),
            material=material,
        )


# ── Scene Assembly ───────────────────────────────────────────────────

def build_intact_cup(ms, cx, cz):
    """Intact cup — coaxial ellipsoid construction."""
    base_y = 0.01

    # Cup wall: 7 stacked coaxial rings, 10 segments each
    coaxial_wall(
        ms, cx, cz,
        base_y=base_y + 0.06,
        height=0.68,
        ring_radius=0.34,
        wall_thickness=0.05,
        n_rings=7,
        segments_per_ring=10,
        material=CERAMIC,
        taper_top=1.06,
        taper_bottom=0.94,
    )

    # Rim: one coaxial ring, slightly wider, shinier
    coaxial_ring(ms, cx, base_y + 0.78, cz,
                 ring_radius=0.37, n_segments=12,
                 cross_h=0.03, cross_w=0.04,
                 material=CERAMIC_RIM)

    # Inner wall visible from above: smaller ring near top
    coaxial_ring(ms, cx, base_y + 0.68, cz,
                 ring_radius=0.27, n_segments=8,
                 cross_h=0.06, cross_w=0.04,
                 material=CERAMIC_INNER)

    # Base: single flat ellipsoid (disc)
    ms.ellipsoid(pos=(cx, base_y, cz),
                 radii=(0.30, 0.025, 0.30),
                 material=CERAMIC)

    # Handle: arc of tangent-aligned ellipsoids
    handle_arc(ms, cx + 0.40, base_y + 0.45, cz,
               width=0.17, height=0.40,
               n_segments=7, thickness=0.04,
               material=CERAMIC)

    # Coffee surface: single flat ellipsoid
    ms.ellipsoid(pos=(cx, base_y + 0.66, cz),
                 radii=(0.29, 0.012, 0.29),
                 material=COFFEE_SURFACE)

    # Coffee meniscus ring: subtle raised edge
    coaxial_ring(ms, cx, base_y + 0.665, cz,
                 ring_radius=0.26, n_segments=8,
                 cross_h=0.008, cross_w=0.025,
                 material=COFFEE_SURFACE)


def build_broken_cup(ms, cx, cz):
    """Broken cup tipped on its side, coffee spilling."""

    # ── Tipped cup body ──
    # Build coaxial rings but apply a global tip rotation
    tip_deg = -78
    tip_rad = math.radians(tip_deg)
    cos_t = math.cos(tip_rad)
    sin_t = math.sin(tip_rad)

    n_rings = 6
    segs = 8
    cup_h = 0.68
    cup_r = 0.34
    wall_t = 0.045
    ring_h_each = cup_h / n_rings * 0.65

    for ring_i in range(n_rings):
        t = ring_i / max(1, n_rings - 1)
        local_y = cup_h * t
        taper = 0.94 + 0.12 * t
        r = cup_r * taper

        for seg_i in range(segs):
            angle = 2 * math.pi * seg_i / segs

            # Skip segments at the broken mouth (top-front)
            if t > 0.55 and abs(angle - math.pi * 0.5) < 0.9:
                continue

            # Local ring position (before tip)
            local_x = r * math.cos(angle)
            local_z = r * math.sin(angle)

            # Tip rotation (rotate local_y into world XY)
            world_x = cx + local_x
            world_y = 0.30 + local_y * cos_t - 0 * sin_t
            world_z = cz + local_z

            # Clamp to floor
            world_y = max(0.04, world_y)

            # Arc length
            arc_half = math.pi * r / segs * 1.1

            # Combine ring tangent rotation with tip
            ms.ellipsoid(
                pos=(world_x, world_y, world_z),
                radii=(arc_half, ring_h_each, wall_t),
                rotate=(tip_rad * 0.3, -angle + math.pi/2, tip_rad * 0.7),
                material=CERAMIC,
            )

    # ── Shards ──
    shards = [
        (0.52, 0.20, 0.12, 0.025, 0.09, (0.3, 0.5, 0.8), CERAMIC),
        (0.38, -0.25, 0.10, 0.02, 0.07, (-0.4, 0.2, 1.2), CERAMIC_STAINED),
        (0.70, -0.08, 0.08, 0.018, 0.06, (0.6, -0.3, 0.4), CERAMIC),
        (0.85, 0.10, 0.06, 0.015, 0.04, (1.0, 0.7, -0.2), CERAMIC_STAINED),
        (-0.08, 0.30, 0.09, 0.02, 0.06, (-0.8, 0.1, 2.0), CERAMIC),
    ]
    for dx, dz, ra, rb, rc, rot, mat in shards:
        ms.ellipsoid(
            pos=(cx + dx, 0.015 + rb, cz + dz),
            radii=(ra, rb, rc),
            rotate=rot,
            material=mat,
        )

    # ── Broken handle ── chain of small ellipsoids
    for i in range(4):
        t = i / 3
        hx = cx - 0.28 + 0.06 * math.sin(math.pi * t)
        hy = 0.035
        hz = cz - 0.32 + 0.10 * t
        ms.ellipsoid(
            pos=(hx, hy, hz),
            radii=(0.035, 0.025, 0.03),
            rotate=(0.5 * t, 0.3, t * 0.8),
            material=CERAMIC,
        )

    # ── Coffee spill ──
    spill_cx = cx + 0.48
    spill_cz = cz + 0.08

    # Main puddle body
    ms.ellipsoid(pos=(spill_cx, 0.004, spill_cz),
                 radii=(0.50, 0.006, 0.40),
                 rotate=(0, 0.15, 0), material=COFFEE_WET)
    ms.ellipsoid(pos=(spill_cx + 0.08, 0.004, spill_cz - 0.05),
                 radii=(0.35, 0.005, 0.38),
                 rotate=(0, -0.25, 0), material=COFFEE_WET)

    # Tendrils
    tendrils = [
        (0.3, 0.20, 0.05, 0.38),
        (1.1, 0.16, 0.04, 0.35),
        (2.0, 0.22, 0.06, 0.28),
        (-0.5, 0.13, 0.035, 0.42),
        (0.7, 0.10, 0.03, 0.48),
    ]
    for angle, length, width, offset in tendrils:
        tx = spill_cx + offset * math.cos(angle)
        tz = spill_cz + offset * math.sin(angle)
        ms.ellipsoid(
            pos=(tx, 0.003, tz),
            radii=(length, 0.004, width),
            rotate=(0, angle, 0),
            material=COFFEE_EDGE,
        )

    # Droplets — spheres are correct here (small round drops)
    drops = [
        (0.95, 0.15, 0.012),
        (1.10, -0.20, 0.009),
        (0.70, 0.35, 0.010),
        (1.20, 0.05, 0.008),
        (0.55, -0.30, 0.011),
        (1.35, -0.10, 0.007),
    ]
    for ddx, ddz, dr in drops:
        ms.sphere(pos=(cx + ddx, dr * 0.7, cz + ddz), radius=dr,
                  material=COFFEE_WET)

    # Coffee stream from tipped mouth
    for i in range(6):
        t = i / 5
        sx = cx + 0.18 + 0.22 * t
        sy = 0.25 * (1 - t * t) + 0.015  # parabolic arc
        sz = cz + 0.05 * t
        r = 0.03 * (1 - t * 0.5)
        ms.ellipsoid(
            pos=(sx, sy, sz),
            radii=(r, r * 0.8, r * 0.9),
            rotate=(0.2 * t, 0, -0.5 * t),
            material=COFFEE_SURFACE,
        )


def build_scene():
    ms = MatterShaper()
    ms.background(0.04, 0.04, 0.06)
    ms.ambient(0.07, 0.07, 0.09)

    ms.plane(y=0, material=STEEL_FLOOR)

    build_intact_cup(ms, -1.1, -2.8)
    build_broken_cup(ms, 1.0, -2.8)

    # Lighting
    ms.light(pos=(0, 6, 0), color=(1.0, 0.98, 0.95), intensity=0.85)
    ms.light(pos=(-4, 3, -1), color=(1.0, 0.92, 0.78), intensity=0.35)
    ms.light(pos=(3, 2.5, -5), color=(0.7, 0.78, 1.0), intensity=0.30)
    ms.light(pos=(0, 0.3, 1), color=(0.8, 0.8, 0.85), intensity=0.12)

    ms.camera(
        pos=(0, 1.6, 1.0),
        look_at=(0, 0.25, -2.8),
        fov=48,
    )

    return ms


def main():
    print("MatterShaper — Coffee Cups v3 (Coaxial Ellipsoids)")
    print("=" * 55)
    print("Ellipsoids for surfaces, spheres only for drops/accents.\n")

    ms = build_scene()
    print(ms)

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'renders')
    os.makedirs(out_dir, exist_ok=True)

    width, height = 400, 300
    print(f"\nRendering {width}×{height} ({width*height:,} rays)...")
    t0 = time.time()
    result = ms.render(
        os.path.join(out_dir, 'coffee_cups_v3.png'),
        width=width, height=height,
    )
    t1 = time.time()
    print(f"Done in {t1-t0:.2f}s")
    print(f"Objects: {result['objects']}, Lights: {result['lights']}")
    print(f"PNG: {result['filepath']}")


if __name__ == '__main__':
    main()

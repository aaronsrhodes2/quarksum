"""
MatterShaper — Seated Person Scene.

A person wearing cotton clothing, sitting on a wooden chair.
Built entirely from spheres, ellipsoids, and planes.

Anatomy breakdown (all measurements in scene units ≈ decimeters):
  Head:       sphere
  Neck:       short ellipsoid
  Torso:      large ellipsoid (slightly wider at shoulders)
  Shoulders:  two spheres
  Upper arms: elongated ellipsoids, angled down
  Forearms:   elongated ellipsoids, resting on thighs
  Hands:      small ellipsoids
  Hips:       wide ellipsoid
  Upper legs: elongated ellipsoids, horizontal (sitting)
  Lower legs: elongated ellipsoids, vertical (hanging down)
  Feet:       flat ellipsoids

Chair:
  Seat:       flat ellipsoid
  Back:       tall ellipsoid, slightly reclined
  Four legs:  thin ellipsoids
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper import MatterShaper, Material, Vec3


# ── Materials ────────────────────────────────────────────────────────

SKIN = Material(
    name='Skin',
    color=Vec3(0.78, 0.60, 0.48),
    reflectance=0.08,
    roughness=0.55,
    density_kg_m3=1010,
    mean_Z=7, mean_A=14,
    composition='Organic tissue (C, H, O, N)',
)

HAIR_DARK = Material(
    name='Dark Hair',
    color=Vec3(0.12, 0.08, 0.06),
    reflectance=0.15,
    roughness=0.35,
    density_kg_m3=1300,
    mean_Z=6, mean_A=12,
    composition='Keratin (C, H, O, N, S)',
)

COTTON_BLUE = Material(
    name='Blue Cotton Shirt',
    color=Vec3(0.22, 0.35, 0.55),
    reflectance=0.04,
    roughness=0.80,
    density_kg_m3=1540,
    mean_Z=6, mean_A=12,
    composition='Cellulose (C₆H₁₀O₅)n',
)

COTTON_DARK = Material(
    name='Dark Cotton Pants',
    color=Vec3(0.15, 0.14, 0.18),
    reflectance=0.03,
    roughness=0.85,
    density_kg_m3=1540,
    mean_Z=6, mean_A=12,
    composition='Cellulose (C₆H₁₀O₅)n',
)

SHOE_BROWN = Material(
    name='Brown Leather Shoe',
    color=Vec3(0.30, 0.18, 0.10),
    reflectance=0.12,
    roughness=0.40,
    density_kg_m3=860,
    mean_Z=6, mean_A=12,
    composition='Tanned collagen',
)

WOOD_OAK = Material(
    name='Oak Wood',
    color=Vec3(0.55, 0.38, 0.22),
    reflectance=0.08,
    roughness=0.50,
    density_kg_m3=750,
    mean_Z=6, mean_A=12,
    composition='Cellulose + lignin',
)

WOOD_DARK = Material(
    name='Dark Stained Wood',
    color=Vec3(0.35, 0.22, 0.12),
    reflectance=0.10,
    roughness=0.45,
    density_kg_m3=750,
    mean_Z=6, mean_A=12,
    composition='Cellulose + lignin (stained)',
)

FLOOR_WOOD = Material(
    name='Wooden Floor',
    color=Vec3(0.48, 0.35, 0.22),
    reflectance=0.12,
    roughness=0.45,
    density_kg_m3=600,
    mean_Z=6, mean_A=12,
    composition='Pine planks',
)


def build_scene():
    ms = MatterShaper()
    ms.background(0.08, 0.08, 0.12)
    ms.ambient(0.10, 0.10, 0.13)

    # ── Floor ────────────────────────────────────────────────────
    ms.plane(y=0, material=FLOOR_WOOD)

    # ── Chair ────────────────────────────────────────────────────
    # All positions relative to chair center at (0, 0, -4)
    chair_x, chair_z = 0.0, -4.0
    seat_h = 0.45  # seat height

    # Seat — flat wide ellipsoid
    ms.ellipsoid(
        pos=(chair_x, seat_h, chair_z),
        radii=(0.45, 0.04, 0.40),
        material=WOOD_OAK,
    )

    # Chair back — tall ellipsoid, slightly reclined
    back_recline = math.radians(8)
    ms.ellipsoid(
        pos=(chair_x, seat_h + 0.48, chair_z - 0.35),
        radii=(0.40, 0.50, 0.035),
        rotate=(back_recline, 0, 0),
        material=WOOD_OAK,
    )

    # Chair back top rail
    ms.ellipsoid(
        pos=(chair_x, seat_h + 0.92, chair_z - 0.38),
        radii=(0.42, 0.04, 0.04),
        material=WOOD_DARK,
    )

    # Four legs
    leg_inset = 0.32
    leg_radius = (0.03, 0.23, 0.03)
    for dx, dz in [(-leg_inset, leg_inset), (leg_inset, leg_inset),
                    (-leg_inset, -leg_inset), (leg_inset, -leg_inset)]:
        ms.ellipsoid(
            pos=(chair_x + dx, 0.22, chair_z + dz),
            radii=leg_radius,
            material=WOOD_DARK,
        )

    # Leg cross-bar (front)
    ms.ellipsoid(
        pos=(chair_x, 0.12, chair_z + leg_inset),
        radii=(leg_inset + 0.03, 0.02, 0.02),
        material=WOOD_DARK,
    )

    # ── Person ───────────────────────────────────────────────────
    # Seated, centered on chair
    px, pz = chair_x, chair_z

    # --- Head ---
    head_y = seat_h + 1.10
    ms.sphere(pos=(px, head_y, pz + 0.02), radius=0.18, material=SKIN)

    # Hair — cap on top of head
    ms.ellipsoid(
        pos=(px, head_y + 0.08, pz - 0.01),
        radii=(0.19, 0.14, 0.20),
        material=HAIR_DARK,
    )

    # Ears — small spheres
    ms.sphere(pos=(px - 0.17, head_y - 0.02, pz + 0.02), radius=0.04, material=SKIN)
    ms.sphere(pos=(px + 0.17, head_y - 0.02, pz + 0.02), radius=0.04, material=SKIN)

    # --- Neck ---
    neck_y = seat_h + 0.88
    ms.ellipsoid(
        pos=(px, neck_y, pz),
        radii=(0.07, 0.08, 0.07),
        material=SKIN,
    )

    # --- Torso (shirt) ---
    torso_y = seat_h + 0.58
    # Upper torso — slightly wider at shoulders
    ms.ellipsoid(
        pos=(px, torso_y + 0.12, pz + 0.02),
        radii=(0.30, 0.22, 0.18),
        material=COTTON_BLUE,
    )
    # Lower torso / belly
    ms.ellipsoid(
        pos=(px, torso_y - 0.08, pz + 0.05),
        radii=(0.26, 0.18, 0.17),
        material=COTTON_BLUE,
    )

    # --- Shoulders ---
    shoulder_y = seat_h + 0.78
    ms.sphere(pos=(px - 0.30, shoulder_y, pz), radius=0.09, material=COTTON_BLUE)
    ms.sphere(pos=(px + 0.30, shoulder_y, pz), radius=0.09, material=COTTON_BLUE)

    # --- Upper Arms (shirt sleeves) ---
    # Arms hang from shoulders, slightly forward, elbows bent
    arm_angle = math.radians(60)  # angle down from horizontal
    for side in [-1, 1]:
        arm_x = px + side * 0.36
        ms.ellipsoid(
            pos=(arm_x, shoulder_y - 0.16, pz + 0.06),
            radii=(0.08, 0.18, 0.08),
            rotate=(0.2, 0, side * 0.15),
            material=COTTON_BLUE,
        )

    # --- Forearms (skin, resting on thighs) ---
    for side in [-1, 1]:
        forearm_x = px + side * 0.28
        ms.ellipsoid(
            pos=(forearm_x, seat_h + 0.12, pz + 0.25),
            radii=(0.06, 0.06, 0.17),
            rotate=(0.3, side * 0.2, 0),
            material=SKIN,
        )

    # --- Hands ---
    for side in [-1, 1]:
        hand_x = px + side * 0.22
        ms.ellipsoid(
            pos=(hand_x, seat_h + 0.10, pz + 0.42),
            radii=(0.05, 0.025, 0.06),
            material=SKIN,
        )

    # --- Hips / Seat area (pants) ---
    ms.ellipsoid(
        pos=(px, seat_h + 0.06, pz + 0.05),
        radii=(0.30, 0.10, 0.22),
        material=COTTON_DARK,
    )

    # --- Upper Legs / Thighs (pants, horizontal) ---
    for side in [-1, 1]:
        thigh_x = px + side * 0.15
        ms.ellipsoid(
            pos=(thigh_x, seat_h + 0.04, pz + 0.22),
            radii=(0.12, 0.10, 0.25),
            material=COTTON_DARK,
        )

    # --- Knees (pants, at edge of seat) ---
    for side in [-1, 1]:
        knee_x = px + side * 0.15
        ms.sphere(
            pos=(knee_x, seat_h - 0.02, pz + 0.42),
            radius=0.10,
            material=COTTON_DARK,
        )

    # --- Lower Legs / Shins (pants, hanging down) ---
    for side in [-1, 1]:
        shin_x = px + side * 0.15
        ms.ellipsoid(
            pos=(shin_x, seat_h - 0.26, pz + 0.45),
            radii=(0.08, 0.22, 0.08),
            material=COTTON_DARK,
        )

    # --- Feet / Shoes ---
    for side in [-1, 1]:
        foot_x = px + side * 0.15
        ms.ellipsoid(
            pos=(foot_x, 0.04, pz + 0.52),
            radii=(0.07, 0.04, 0.13),
            material=SHOE_BROWN,
        )

    # ── Lighting ─────────────────────────────────────────────────
    # Warm key light from upper right
    ms.light(pos=(3, 5, -1), color=(1.0, 0.95, 0.88), intensity=0.85)

    # Cool fill from upper left
    ms.light(pos=(-4, 4, -2), color=(0.65, 0.72, 0.95), intensity=0.40)

    # Gentle back/rim light
    ms.light(pos=(0, 3, -8), color=(0.8, 0.8, 0.9), intensity=0.30)

    # Low front fill to soften shadows under chair
    ms.light(pos=(0, 0.5, 0), color=(0.9, 0.85, 0.8), intensity=0.15)

    # ── Camera ───────────────────────────────────────────────────
    # 3/4 view from front-right, slightly above eye level
    ms.camera(
        pos=(1.8, 1.8, -1.5),
        look_at=(0, 0.7, -4),
        fov=42,
    )

    return ms


def main():
    print("MatterShaper — Seated Person")
    print("=" * 45)
    print("Person in cotton clothing on a wooden chair.")
    print("Spheres + ellipsoids + one plane. Pure math.\n")

    ms = build_scene()
    print(ms)

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'renders')
    os.makedirs(out_dir, exist_ok=True)

    import time

    # Full render
    width, height = 400, 500
    print(f"\nRendering {width}×{height} ({width*height:,} rays)...")
    t0 = time.time()
    result = ms.render(
        os.path.join(out_dir, 'seated_person.png'),
        width=width, height=height,
    )
    t1 = time.time()
    print(f"Done in {t1-t0:.2f}s")
    print(f"PNG: {result['filepath']}")

    # Also SVG
    ms.render(
        os.path.join(out_dir, 'seated_person.svg'),
        width=width, height=height, pixel_size=2,
    )

    print(f"\nScene: {result['objects']} objects, {result['lights']} lights")
    print(f"Rays: {result['rays']:,}")
    print("Done.")


if __name__ == '__main__':
    main()

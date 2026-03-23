"""
MatterShaper — Person with Coffee Cup Scene.

A person seated on a wooden chair, holding a coffee cup.
All body parts properly overlap — no disconnected ellipsoid gaps.

Built entirely from spheres, ellipsoids, cones, and planes.
No meshes. No textures. Pure math.
"""

import sys
import os
import math
import time

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
    color=Vec3(0.42, 0.30, 0.18),
    reflectance=0.10,
    roughness=0.50,
    density_kg_m3=600,
    mean_Z=6, mean_A=12,
    composition='Pine planks',
)

CERAMIC_WHITE = Material(
    name='White Ceramic',
    color=Vec3(0.92, 0.90, 0.85),
    reflectance=0.12,
    roughness=0.25,
    density_kg_m3=2400,
    mean_Z=11, mean_A=22,
    composition='Fired clay (SiO₂, Al₂O₃)',
)

CERAMIC_RIM = Material(
    name='Ceramic Rim',
    color=Vec3(0.95, 0.93, 0.88),
    reflectance=0.18,
    roughness=0.15,
)

COFFEE_LIQ = Material(
    name='Coffee',
    color=Vec3(0.25, 0.14, 0.07),
    reflectance=0.35,
    roughness=0.05,
)

HANDLE_MAT = Material(
    name='Cup Handle',
    color=Vec3(0.90, 0.87, 0.82),
    reflectance=0.10,
    roughness=0.30,
)

TABLE_TOP = Material(
    name='Table Top',
    color=Vec3(0.50, 0.35, 0.20),
    reflectance=0.10,
    roughness=0.45,
    density_kg_m3=750,
    mean_Z=6, mean_A=12,
    composition='Walnut wood',
)


def build_scene():
    ms = MatterShaper()
    ms.background(0.06, 0.06, 0.10)
    ms.ambient(0.10, 0.10, 0.14)

    # ── Floor ────────────────────────────────────────────────────
    ms.plane(y=0, material=FLOOR_WOOD)

    # ── Chair ────────────────────────────────────────────────────
    chair_x, chair_z = 0.0, -4.0
    seat_h = 0.45

    # Seat — flat wide ellipsoid
    ms.ellipsoid(
        pos=(chair_x, seat_h, chair_z),
        radii=(0.45, 0.05, 0.40),
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

    # Four legs — use cones (cylinders) for cleaner look
    leg_inset = 0.32
    for dx, dz in [(-leg_inset, leg_inset), (leg_inset, leg_inset),
                    (-leg_inset, -leg_inset), (leg_inset, -leg_inset)]:
        ms.cone(
            base_pos=(chair_x + dx, 0.0, chair_z + dz),
            height=seat_h,
            base_radius=0.035,
            top_radius=0.030,
            material=WOOD_DARK,
        )

    # Leg cross-bar (front)
    ms.ellipsoid(
        pos=(chair_x, 0.12, chair_z + leg_inset),
        radii=(leg_inset + 0.03, 0.02, 0.02),
        material=WOOD_DARK,
    )

    # ── Person ───────────────────────────────────────────────────
    # Key fix: OVERLAP all body segments generously so no gaps show.
    px, pz = chair_x, chair_z

    # --- Head ---
    head_y = seat_h + 1.05
    ms.sphere(pos=(px, head_y, pz + 0.02), radius=0.18, material=SKIN)

    # Hair — cap on top of head
    ms.ellipsoid(
        pos=(px, head_y + 0.08, pz - 0.01),
        radii=(0.19, 0.14, 0.20),
        material=HAIR_DARK,
    )

    # Ears
    ms.sphere(pos=(px - 0.17, head_y - 0.02, pz + 0.02), radius=0.04, material=SKIN)
    ms.sphere(pos=(px + 0.17, head_y - 0.02, pz + 0.02), radius=0.04, material=SKIN)

    # --- Neck --- (larger, overlaps head and torso)
    neck_y = seat_h + 0.88
    ms.ellipsoid(
        pos=(px, neck_y, pz + 0.01),
        radii=(0.09, 0.12, 0.09),  # bigger to overlap head bottom and torso top
        material=SKIN,
    )

    # --- Torso (shirt) --- single larger piece to avoid mid-torso gap
    torso_y = seat_h + 0.58
    # Main torso — one big overlapping ellipsoid
    ms.ellipsoid(
        pos=(px, torso_y + 0.06, pz + 0.03),
        radii=(0.30, 0.30, 0.19),
        material=COTTON_BLUE,
    )
    # Belly roundness
    ms.ellipsoid(
        pos=(px, torso_y - 0.06, pz + 0.06),
        radii=(0.27, 0.16, 0.18),
        material=COTTON_BLUE,
    )

    # --- Shoulders --- (overlap torso edges)
    shoulder_y = seat_h + 0.76
    ms.sphere(pos=(px - 0.28, shoulder_y, pz + 0.01), radius=0.11, material=COTTON_BLUE)
    ms.sphere(pos=(px + 0.28, shoulder_y, pz + 0.01), radius=0.11, material=COTTON_BLUE)

    # --- Upper Arms --- (overlapping into shoulders)
    for side in [-1, 1]:
        arm_x = px + side * 0.34
        ms.ellipsoid(
            pos=(arm_x, shoulder_y - 0.14, pz + 0.07),
            radii=(0.09, 0.20, 0.09),
            rotate=(0.2, 0, side * 0.12),
            material=COTTON_BLUE,
        )
        # Bridge sphere between shoulder and upper arm
        ms.sphere(
            pos=(arm_x - side * 0.02, shoulder_y - 0.04, pz + 0.04),
            radius=0.09,
            material=COTTON_BLUE,
        )

    # --- Elbows --- bridge between upper and lower arms
    for side in [-1, 1]:
        elbow_x = px + side * 0.32
        ms.sphere(
            pos=(elbow_x, seat_h + 0.36, pz + 0.18),
            radius=0.07,
            material=COTTON_BLUE,
        )

    # --- Forearms (skin, resting on thighs) --- longer to reach hands
    # Right arm reaches toward coffee cup on the right
    # Left arm rests on thigh
    for side in [-1, 1]:
        forearm_x = px + side * 0.26
        if side == 1:
            # Right forearm — reaching forward/right toward cup
            ms.ellipsoid(
                pos=(forearm_x + 0.04, seat_h + 0.16, pz + 0.28),
                radii=(0.065, 0.065, 0.19),
                rotate=(0.25, 0.15, 0),
                material=SKIN,
            )
        else:
            # Left forearm — resting on thigh
            ms.ellipsoid(
                pos=(forearm_x, seat_h + 0.14, pz + 0.26),
                radii=(0.065, 0.065, 0.19),
                rotate=(0.3, -0.15, 0),
                material=SKIN,
            )

    # --- Left hand (resting on thigh) ---
    ms.ellipsoid(
        pos=(px - 0.22, seat_h + 0.12, pz + 0.44),
        radii=(0.055, 0.028, 0.065),
        material=SKIN,
    )
    # Wrist bridge
    ms.sphere(pos=(px - 0.23, seat_h + 0.13, pz + 0.40), radius=0.045, material=SKIN)

    # --- Right hand (holding cup) ---
    # Hand wraps around cup — positioned at the cup handle
    cup_x = px + 0.55
    cup_z = pz + 0.52
    cup_base_y = seat_h + 0.18  # table height will be here
    ms.ellipsoid(
        pos=(cup_x - 0.18, cup_base_y + 0.22, cup_z - 0.02),
        radii=(0.055, 0.04, 0.065),
        rotate=(0.2, 0.4, 0),
        material=SKIN,
    )
    # Wrist bridge
    ms.sphere(
        pos=(px + 0.32, seat_h + 0.17, pz + 0.44),
        radius=0.05,
        material=SKIN,
    )

    # --- Hips / Seat area (pants) ---
    ms.ellipsoid(
        pos=(px, seat_h + 0.08, pz + 0.05),
        radii=(0.30, 0.12, 0.22),
        material=COTTON_DARK,
    )

    # --- Thighs (horizontal, sitting) --- overlap hips and knees
    for side in [-1, 1]:
        thigh_x = px + side * 0.14
        ms.ellipsoid(
            pos=(thigh_x, seat_h + 0.05, pz + 0.22),
            radii=(0.13, 0.11, 0.27),
            material=COTTON_DARK,
        )

    # --- Knees (at edge of seat) --- overlap thighs and shins
    for side in [-1, 1]:
        knee_x = px + side * 0.14
        ms.sphere(
            pos=(knee_x, seat_h - 0.01, pz + 0.44),
            radius=0.11,
            material=COTTON_DARK,
        )

    # --- Shins (hanging down) --- overlap knees
    for side in [-1, 1]:
        shin_x = px + side * 0.14
        ms.ellipsoid(
            pos=(shin_x, seat_h - 0.24, pz + 0.46),
            radii=(0.085, 0.24, 0.085),
            material=COTTON_DARK,
        )

    # --- Feet / Shoes --- overlap shins
    for side in [-1, 1]:
        foot_x = px + side * 0.14
        ms.ellipsoid(
            pos=(foot_x, 0.05, pz + 0.52),
            radii=(0.075, 0.05, 0.14),
            material=SHOE_BROWN,
        )
        # Ankle bridge
        ms.sphere(
            pos=(foot_x, 0.10, pz + 0.48),
            radius=0.06,
            material=COTTON_DARK,
        )

    # ── Small Side Table ─────────────────────────────────────────
    table_x = px + 0.55
    table_z = pz + 0.50
    table_h = seat_h + 0.15  # just above thigh level

    # Table top — flat ellipsoid
    ms.ellipsoid(
        pos=(table_x, table_h, table_z),
        radii=(0.30, 0.025, 0.25),
        material=TABLE_TOP,
    )

    # Table legs — 4 thin cylinders
    for dx, dz in [(-0.20, 0.16), (0.20, 0.16), (-0.20, -0.16), (0.20, -0.16)]:
        ms.cone(
            base_pos=(table_x + dx, 0.0, table_z + dz),
            height=table_h,
            base_radius=0.025,
            top_radius=0.022,
            material=WOOD_DARK,
        )

    # ── Coffee Cup (on table) ────────────────────────────────────
    cup_base = table_h + 0.025

    # Cup body — frustum (wider at top than bottom)
    ms.cone(
        base_pos=(cup_x, cup_base, cup_z),
        height=0.42,
        base_radius=0.14,
        top_radius=0.17,
        material=CERAMIC_WHITE,
    )

    # Rim — thin torus approximated by ellipsoid
    ms.ellipsoid(
        pos=(cup_x, cup_base + 0.42, cup_z),
        radii=(0.18, 0.025, 0.18),
        material=CERAMIC_RIM,
    )

    # Coffee surface — dark flat disc inside cup
    ms.ellipsoid(
        pos=(cup_x, cup_base + 0.34, cup_z),
        radii=(0.14, 0.015, 0.14),
        material=COFFEE_LIQ,
    )

    # Cup base — flat disc
    ms.ellipsoid(
        pos=(cup_x, cup_base + 0.01, cup_z),
        radii=(0.13, 0.015, 0.13),
        material=CERAMIC_WHITE,
    )

    # Handle — three overlapping spheres on the right side of cup
    handle_x = cup_x + 0.22
    ms.sphere(pos=(handle_x, cup_base + 0.30, cup_z), radius=0.05, material=HANDLE_MAT)
    ms.sphere(pos=(handle_x + 0.03, cup_base + 0.22, cup_z), radius=0.045, material=HANDLE_MAT)
    ms.sphere(pos=(handle_x, cup_base + 0.14, cup_z), radius=0.04, material=HANDLE_MAT)

    # ── Lighting ─────────────────────────────────────────────────
    # Warm key light from upper right
    ms.light(pos=(3, 5, -1), color=(1.0, 0.95, 0.88), intensity=0.85)

    # Cool fill from upper left
    ms.light(pos=(-4, 4, -2), color=(0.65, 0.72, 0.95), intensity=0.40)

    # Gentle back/rim light
    ms.light(pos=(0, 3, -8), color=(0.8, 0.8, 0.9), intensity=0.30)

    # Low front fill to soften shadows under chair
    ms.light(pos=(0, 0.5, 0), color=(0.9, 0.85, 0.8), intensity=0.15)

    # Extra light to illuminate the cup area
    ms.light(pos=(2, 2, -2.5), color=(1.0, 0.95, 0.90), intensity=0.25)

    # ── Camera ───────────────────────────────────────────────────
    # 3/4 view from front-right, slightly above eye level
    # Pulled back a bit to show the table + cup
    ms.camera(
        pos=(2.2, 1.9, -1.2),
        look_at=(0.2, 0.65, -3.8),
        fov=46,
    )

    return ms


def main():
    print("MatterShaper — Person with Coffee Cup")
    print("=" * 50)
    print("Seated person, wooden chair, side table, ceramic cup.")
    print("All joints overlap — no disconnected ellipsoid gaps.")
    print("Spheres + ellipsoids + cones + plane. Pure math.\n")

    ms = build_scene()
    print(ms)

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'renders')
    os.makedirs(out_dir, exist_ok=True)

    # Render PNG
    width, height = 480, 600
    print(f"\nRendering {width}×{height} ({width*height:,} rays)...")
    t0 = time.time()
    result = ms.render(
        os.path.join(out_dir, 'person_coffee.png'),
        width=width, height=height,
    )
    t1 = time.time()
    print(f"Done in {t1-t0:.2f}s")
    print(f"PNG: {result['filepath']}")

    print(f"\nScene: {result['objects']} objects, {result['lights']} lights")
    print(f"Rays: {result['rays']:,}")
    print("Done.")


if __name__ == '__main__':
    main()

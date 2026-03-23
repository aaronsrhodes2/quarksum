"""
MatterShaper — Coffee Cup Scene.

Two cups on a steel floor:
  Left: intact ceramic cup with coffee visible inside
  Right: broken, tipped over, coffee spilling out

Built entirely from spheres, ellipsoids, and planes.
No meshes. No textures. Pure math.
"""

import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.geometry import Vec3, Sphere, Ellipsoid, Plane, rotation_matrix
from mattershaper.materials import Material
from mattershaper.camera import Camera
from mattershaper.render.raytracer import Light, Scene, render_scene, render_to_svg


# ── Materials ────────────────────────────────────────

CERAMIC_WHITE = Material(
    name="White Ceramic",
    color=Vec3(0.92, 0.90, 0.85),
    reflectance=0.12,
    roughness=0.25,
)

CERAMIC_RIM = Material(
    name="Ceramic Rim",
    color=Vec3(0.95, 0.93, 0.88),
    reflectance=0.18,
    roughness=0.15,
)

COFFEE = Material(
    name="Coffee",
    color=Vec3(0.25, 0.14, 0.07),
    reflectance=0.35,
    roughness=0.05,  # liquid — very smooth, reflective
)

COFFEE_SPILL = Material(
    name="Coffee Spill",
    color=Vec3(0.22, 0.12, 0.06),
    reflectance=0.40,
    roughness=0.02,  # wet puddle — very reflective
)

STEEL_FLOOR = Material(
    name="Brushed Steel",
    color=Vec3(0.55, 0.56, 0.58),
    reflectance=0.45,
    roughness=0.20,
)

SHARD_LIGHT = Material(
    name="Ceramic Shard (outer)",
    color=Vec3(0.90, 0.88, 0.83),
    reflectance=0.10,
    roughness=0.30,
)

SHARD_DARK = Material(
    name="Ceramic Shard (inner/stained)",
    color=Vec3(0.70, 0.60, 0.48),
    reflectance=0.08,
    roughness=0.45,
)

HANDLE = Material(
    name="Cup Handle",
    color=Vec3(0.90, 0.87, 0.82),
    reflectance=0.10,
    roughness=0.30,
)


def build_intact_cup(scene, base_pos):
    """Build an intact coffee cup at base_pos.

    Constructed from:
    - Main body: tall ellipsoid (ceramic)
    - Coffee surface: flat ellipsoid inside, slightly below rim
    - Rim highlight: thin ellipsoid at top
    - Handle: two small spheres on the side
    """
    cx, cy, cz = base_pos.x, base_pos.y, base_pos.z

    # Cup body — tall ellipsoid
    # A coffee cup is roughly 8cm tall, 4cm radius
    scene.add(Ellipsoid(
        center=Vec3(cx, cy + 0.42, cz),
        radii=Vec3(0.38, 0.45, 0.38),
        material=CERAMIC_WHITE,
    ))

    # Rim — slightly wider ellipsoid at top, thin
    scene.add(Ellipsoid(
        center=Vec3(cx, cy + 0.82, cz),
        radii=Vec3(0.40, 0.06, 0.40),
        material=CERAMIC_RIM,
    ))

    # Coffee surface — dark flat ellipsoid inside the cup
    scene.add(Ellipsoid(
        center=Vec3(cx, cy + 0.72, cz),
        radii=Vec3(0.32, 0.03, 0.32),
        material=COFFEE,
    ))

    # Handle — two overlapping spheres on the right side
    scene.add(Sphere(
        center=Vec3(cx + 0.48, cy + 0.55, cz),
        radius=0.10,
        material=HANDLE,
    ))
    scene.add(Sphere(
        center=Vec3(cx + 0.52, cy + 0.40, cz),
        radius=0.09,
        material=HANDLE,
    ))
    scene.add(Sphere(
        center=Vec3(cx + 0.48, cy + 0.25, cz),
        radius=0.08,
        material=HANDLE,
    ))

    # Base — flat ellipsoid at bottom
    scene.add(Ellipsoid(
        center=Vec3(cx, cy + 0.01, cz),
        radii=Vec3(0.32, 0.03, 0.32),
        material=CERAMIC_WHITE,
    ))


def build_broken_cup(scene, base_pos):
    """Build a broken cup tipped on its side, spilling coffee.

    Constructed from:
    - Tipped main body: rotated ellipsoid (the remaining shell)
    - Several scattered shards: small rotated ellipsoids
    - Coffee puddle: very flat ellipsoid spreading on the floor
    - Coffee stream: thin ellipsoid connecting cup to puddle
    - Broken handle: small sphere separated from body
    """
    cx, cy, cz = base_pos.x, base_pos.y, base_pos.z

    # ── Tipped cup body ──
    # Rotated ~80° around Z axis (lying on its side, mouth facing right)
    tip_angle = math.radians(-75)
    rot = rotation_matrix(rx=0, ry=0, rz=tip_angle)

    scene.add(Ellipsoid(
        center=Vec3(cx, cy + 0.30, cz),
        radii=Vec3(0.36, 0.44, 0.36),
        rotation=rot,
        material=CERAMIC_WHITE,
    ))

    # Rim of tipped cup
    rim_rot = rotation_matrix(rx=0, ry=0, rz=tip_angle)
    # The rim is at the "top" of the cup, which is now pointing rightward
    rim_offset_x = 0.78 * math.cos(tip_angle + math.pi/2)
    rim_offset_y = 0.78 * math.sin(tip_angle + math.pi/2)
    scene.add(Ellipsoid(
        center=Vec3(cx + rim_offset_x * 0.5, cy + 0.30 + rim_offset_y * 0.5, cz),
        radii=Vec3(0.10, 0.38, 0.38),
        rotation=rim_rot,
        material=CERAMIC_RIM,
    ))

    # ── Shards ── scattered around the impact point
    # Shard 1: large flat piece, tilted
    scene.add(Ellipsoid(
        center=Vec3(cx + 0.55, cy + 0.04, cz + 0.20),
        radii=Vec3(0.14, 0.025, 0.10),
        rotation=rotation_matrix(rx=0.3, ry=0.5, rz=0.8),
        material=SHARD_LIGHT,
    ))

    # Shard 2: medium chunk
    scene.add(Ellipsoid(
        center=Vec3(cx + 0.35, cy + 0.06, cz - 0.25),
        radii=Vec3(0.11, 0.03, 0.08),
        rotation=rotation_matrix(rx=-0.4, ry=0.2, rz=1.2),
        material=SHARD_DARK,
    ))

    # Shard 3: small fragment
    scene.add(Ellipsoid(
        center=Vec3(cx + 0.65, cy + 0.02, cz - 0.10),
        radii=Vec3(0.07, 0.02, 0.05),
        rotation=rotation_matrix(rx=0.6, ry=-0.3, rz=0.4),
        material=SHARD_LIGHT,
    ))

    # Shard 4: tiny chip near puddle
    scene.add(Ellipsoid(
        center=Vec3(cx + 0.80, cy + 0.015, cz + 0.05),
        radii=Vec3(0.05, 0.015, 0.04),
        rotation=rotation_matrix(rx=1.0, ry=0.7, rz=-0.2),
        material=SHARD_DARK,
    ))

    # Shard 5: another piece behind
    scene.add(Ellipsoid(
        center=Vec3(cx - 0.10, cy + 0.03, cz + 0.30),
        radii=Vec3(0.09, 0.02, 0.07),
        rotation=rotation_matrix(rx=-0.8, ry=0.1, rz=2.0),
        material=SHARD_LIGHT,
    ))

    # ── Broken handle ── separated from body
    scene.add(Sphere(
        center=Vec3(cx - 0.30, cy + 0.06, cz - 0.35),
        radius=0.08,
        material=HANDLE,
    ))
    scene.add(Sphere(
        center=Vec3(cx - 0.22, cy + 0.05, cz - 0.30),
        radius=0.06,
        material=HANDLE,
    ))

    # ── Coffee spill ──
    # Main puddle — very flat ellipsoid on the floor, spreading
    scene.add(Ellipsoid(
        center=Vec3(cx + 0.50, cy + 0.005, cz + 0.05),
        radii=Vec3(0.60, 0.008, 0.45),
        rotation=rotation_matrix(ry=0.2),
        material=COFFEE_SPILL,
    ))

    # Secondary puddle tendril — extending further
    scene.add(Ellipsoid(
        center=Vec3(cx + 1.05, cy + 0.004, cz - 0.10),
        radii=Vec3(0.30, 0.006, 0.18),
        rotation=rotation_matrix(ry=-0.3),
        material=COFFEE_SPILL,
    ))

    # Coffee stream from cup mouth — a tilted thin ellipsoid
    scene.add(Ellipsoid(
        center=Vec3(cx + 0.35, cy + 0.10, cz),
        radii=Vec3(0.20, 0.04, 0.08),
        rotation=rotation_matrix(rz=-0.5),
        material=COFFEE,
    ))

    # Drip / droplet on the floor
    scene.add(Sphere(
        center=Vec3(cx + 1.25, cy + 0.025, cz + 0.15),
        radius=0.025,
        material=COFFEE_SPILL,
    ))
    scene.add(Sphere(
        center=Vec3(cx + 0.90, cy + 0.02, cz - 0.25),
        radius=0.018,
        material=COFFEE_SPILL,
    ))


def build_scene():
    scene = Scene()
    scene.background = Vec3(0.03, 0.03, 0.05)
    scene.ambient = Vec3(0.06, 0.06, 0.08)

    # Steel floor
    scene.add(Plane(
        point=Vec3(0, 0, 0),
        normal=Vec3(0, 1, 0),
        material=STEEL_FLOOR,
    ))

    # Intact cup — left side
    build_intact_cup(scene, Vec3(-1.0, 0, -2.5))

    # Broken cup — right side
    build_broken_cup(scene, Vec3(1.0, 0, -2.5))

    # ── Lighting ──
    # Overhead fluorescent feel (cool white, strong)
    scene.add_light(Light(
        pos=Vec3(0, 5, -1),
        color=Vec3(1.0, 0.98, 0.95),
        intensity=0.9,
    ))

    # Side fill (warm, from left)
    scene.add_light(Light(
        pos=Vec3(-4, 3, 0),
        color=Vec3(1.0, 0.90, 0.75),
        intensity=0.4,
    ))

    # Accent from behind-right (cool)
    scene.add_light(Light(
        pos=Vec3(3, 2, -5),
        color=Vec3(0.7, 0.8, 1.0),
        intensity=0.3,
    ))

    return scene


def build_camera():
    return Camera(
        pos=Vec3(0, 2.0, 1.5),
        look_at=Vec3(0, 0.2, -2.5),
        up=Vec3(0, 1, 0),
        fov=48,
    )


def main():
    print("MatterShaper — Coffee Cup Scene")
    print("=" * 45)
    print("One intact. One broken. Steel floor. Pure math.")
    print()

    scene = build_scene()
    camera = build_camera()

    obj_count = len(scene.objects)
    print(f"Scene: {obj_count} objects, {len(scene.lights)} lights")

    # Render at good resolution
    width, height = 400, 300
    print(f"Rendering {width}×{height} ({width*height:,} rays)...")

    t0 = time.time()
    pixels = render_scene(scene, camera, width, height)
    t1 = time.time()
    print(f"Ray-traced in {t1 - t0:.2f}s")

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'renders')
    os.makedirs(out_dir, exist_ok=True)

    svg_path = os.path.join(out_dir, 'coffee_cups.svg')
    render_to_svg(pixels, svg_path, pixel_size=3)
    print(f"SVG: {svg_path}")

    # Also generate PNG via our pure-Python converter
    png_path = os.path.join(out_dir, 'coffee_cups.png')
    _svg_to_png(pixels, width, height, png_path)
    print(f"PNG: {png_path}")

    print(f"\nTotal: {time.time() - t0:.2f}s")
    print("Done.")


def _svg_to_png(pixels, width, height, filepath):
    """Write pixel array directly to PNG. Zero dependencies."""
    import struct, zlib

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter byte
        for x in range(width):
            c = pixels[y][x].clamp(0, 1)
            raw.append(int(c.x * 255))
            raw.append(int(c.y * 255))
            raw.append(int(c.z * 255))

    compressed = zlib.compress(bytes(raw), 9)

    def chunk(chunk_type, data):
        c = chunk_type + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    with open(filepath, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)))
        f.write(chunk(b'IDAT', compressed))
        f.write(chunk(b'IEND', b''))


if __name__ == '__main__':
    main()

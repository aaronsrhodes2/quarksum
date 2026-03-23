"""
MatterShaper — Proof of Concept Render.

Renders a simple scene: a ceramic sphere on a basalt plane,
lit by two lights. Demonstrates the full pipeline:
    geometry → materials → camera → ray-trace → SVG

Zero dependencies beyond Python stdlib + our own code.
"""

import sys
import os

# Add MatterShaper to path
sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.geometry import Vec3, Ray, Sphere, Ellipsoid, Plane
from mattershaper.materials import CERAMIC, STEEL, BASALT, GLASS, IRON, ICE, Material
from mattershaper.camera import Camera
from mattershaper.render.raytracer import Light, Scene, render_scene, render_to_svg


def build_scene():
    """Build the proof-of-concept scene."""
    scene = Scene()
    scene.background = Vec3(0.01, 0.01, 0.03)  # deep space

    # Ground plane — basalt
    ground = Plane(
        point=Vec3(0, -1, 0),
        normal=Vec3(0, 1, 0),
        material=Material(
            name="Ground",
            color=Vec3(0.15, 0.12, 0.10),
            reflectance=0.05,
            roughness=0.9,
        ),
    )
    scene.add(ground)

    # Central sphere — ceramic (our "atom")
    center_sphere = Sphere(
        center=Vec3(0, 0.2, -3),
        radius=1.2,
        material=Material(
            name="Ceramic Body",
            color=Vec3(0.85, 0.75, 0.65),
            reflectance=0.15,
            roughness=0.3,
        ),
    )
    scene.add(center_sphere)

    # Left sphere — steel (reflective)
    left_sphere = Sphere(
        center=Vec3(-2.2, -0.3, -4),
        radius=0.7,
        material=Material(
            name="Steel Sphere",
            color=Vec3(0.7, 0.7, 0.75),
            reflectance=0.6,
            roughness=0.1,
        ),
    )
    scene.add(left_sphere)

    # Right sphere — glass-like (transparent look via high reflectance)
    right_sphere = Sphere(
        center=Vec3(2.0, -0.5, -3.5),
        radius=0.5,
        material=Material(
            name="Glass Sphere",
            color=Vec3(0.4, 0.6, 0.9),
            reflectance=0.5,
            roughness=0.05,
        ),
    )
    scene.add(right_sphere)

    # Background sphere — iron, far back
    back_sphere = Sphere(
        center=Vec3(0.5, 1.5, -8),
        radius=2.0,
        material=Material(
            name="Iron Mass",
            color=Vec3(0.5, 0.35, 0.25),
            reflectance=0.3,
            roughness=0.5,
        ),
    )
    scene.add(back_sphere)

    # -- Lights --
    # Key light (warm, upper right)
    scene.add_light(Light(
        pos=Vec3(5, 8, 2),
        color=Vec3(1.0, 0.95, 0.85),
        intensity=1.0,
    ))

    # Fill light (cool, upper left)
    scene.add_light(Light(
        pos=Vec3(-4, 6, 0),
        color=Vec3(0.6, 0.7, 1.0),
        intensity=0.5,
    ))

    # Rim light (behind, slight)
    scene.add_light(Light(
        pos=Vec3(0, 3, -10),
        color=Vec3(0.8, 0.8, 1.0),
        intensity=0.3,
    ))

    return scene


def build_camera():
    """Camera positioned to see all objects."""
    return Camera(
        pos=Vec3(0, 1.5, 3),
        look_at=Vec3(0, 0, -3),
        up=Vec3(0, 1, 0),
        fov=55,
    )


def main():
    print("MatterShaper — Proof of Concept")
    print("=" * 40)

    scene = build_scene()
    camera = build_camera()

    width, height = 320, 240
    print(f"Rendering {width}×{height} ({width*height} rays)...")

    import time
    t0 = time.time()
    pixels = render_scene(scene, camera, width, height)
    t1 = time.time()

    print(f"Ray-traced in {t1 - t0:.2f}s")

    # Output directory
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'renders')
    os.makedirs(out_dir, exist_ok=True)

    svg_path = os.path.join(out_dir, 'mattershaper_poc.svg')
    render_to_svg(pixels, svg_path, pixel_size=3)
    print(f"SVG saved: {svg_path}")

    # Also render a smaller version for quick preview
    width2, height2 = 160, 120
    print(f"\nRendering preview {width2}×{height2}...")
    t2 = time.time()
    pixels2 = render_scene(scene, camera, width2, height2)
    t3 = time.time()
    print(f"Preview traced in {t3 - t2:.2f}s")

    svg_preview = os.path.join(out_dir, 'mattershaper_poc_preview.svg')
    render_to_svg(pixels2, svg_preview, pixel_size=5)
    print(f"Preview SVG saved: {svg_preview}")

    print(f"\nTotal time: {t3 - t0:.2f}s")
    print("Done.")


if __name__ == '__main__':
    main()

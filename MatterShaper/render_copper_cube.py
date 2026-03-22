"""
Copper Cube in Hydrogen Gas — the first matter-based render.

This is the proof of concept:
  - A copper cube built from FCC lattice sites
  - Surface detected by broken entanglement bonds
  - Surface nodes push-render themselves
  - No mesh. No Fibonacci sampling. Real atomic positions.

The geometry IS the physics. The physics IS the rendering.
Entanglement is reality's TV.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.projection import PushCamera
from mattershaper.render.entangler.illumination import PushLight
from mattershaper.render.entangler.matter_render import (
    entangle_matter, entangle_matter_to_file,
)
from mattershaper.materials.material import Material


def main():
    print("=" * 60)
    print("  MATTER RENDER: Copper Cube in Hydrogen Gas")
    print("  Entangler v2 — lattice-based push rendering")
    print("=" * 60)

    # ── Materials ──────────────────────────────────────────────
    copper = Material(
        name='Copper',
        color=Vec3(0.72, 0.45, 0.20),
        reflectance=0.90,
        roughness=0.15,
        density_kg_m3=8960,
        mean_Z=29, mean_A=64,
        composition='Cu (FCC)',
    )

    # ── Scene: copper cube ────────────────────────────────────
    # Using exaggerated lattice parameter for visible rendering.
    # Real copper: a = 3.615 Å = 3.615e-10 m
    # For rendering at human scale: a = 0.08 (visible node spacing)
    lattice_param = 0.08  # render-scale

    scene = [{
        'type': 'cube',
        'center': Vec3(0, 0, 0),
        'size': 2.0,           # 2m edge cube
        'crystal_structure': 'fcc',
        'lattice_param_m': lattice_param,
        'material': copper,
    }]

    # ── Camera ────────────────────────────────────────────────
    camera = PushCamera(
        pos=Vec3(2.5, 2.5, -4.5),
        look_at=Vec3(0, 0, 0),
        width=512, height=512, fov=60,
    )

    # ── Light ─────────────────────────────────────────────────
    light = PushLight(
        pos=Vec3(5, 8, -5),
        intensity=1.0,
        color=Vec3(1.0, 0.98, 0.95),  # slightly warm
    )

    # ── Background: hydrogen gas atmosphere ───────────────────
    bg = Vec3(0.02, 0.02, 0.04)  # near-black with slight blue (H₂ scattering)

    # ── Render ────────────────────────────────────────────────
    print(f"\n  Lattice: FCC (copper)")
    print(f"  Lattice parameter: {lattice_param} (render-scale)")
    print(f"  Cube edge: 2.0")
    print(f"  Resolution: {camera.width}×{camera.height}")
    print(f"\n  Building matter and rendering...")

    t0 = time.time()
    pixels, stats = entangle_matter(scene, camera, light, bg_color=bg)
    dt = time.time() - t0

    print(f"\n  ── Results ──")
    print(f"  Total atoms:      {stats['total_atoms']:,}")
    print(f"  Surface atoms:    {stats['surface_atoms']:,}")
    print(f"  Surface fraction: {stats['surface_fraction']:.1%}")
    print(f"  Rendered nodes:   {stats['rendered_nodes']:,}")
    print(f"  Render time:      {dt:.2f}s")
    print(f"  Atoms/sec:        {stats['total_atoms']/dt:,.0f}")

    # ── Save ──────────────────────────────────────────────────
    out_dir = os.path.dirname(__file__)
    ppm_path = os.path.join(out_dir, 'copper_cube_matter.ppm')

    from mattershaper.render.entangler.matter_render import _write_ppm
    _write_ppm(pixels, ppm_path)
    print(f"\n  Saved: {ppm_path}")

    # Try PNG conversion
    try:
        import subprocess
        png_path = os.path.join(out_dir, 'copper_cube_matter.png')
        subprocess.run(['convert', ppm_path, png_path],
                      capture_output=True, timeout=10)
        if os.path.exists(png_path):
            print(f"  Saved: {png_path}")
            os.remove(ppm_path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  (ImageMagick not found — PPM only)")

    print(f"\n{'=' * 60}")
    print(f"  Matter broadcasts. Entanglement is reality's TV.")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()

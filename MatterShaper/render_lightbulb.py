"""
Lightbulb — a tungsten filament in a vacuum-sealed glass chamber.

The filament is hot enough to emit light (2800 K) but not hot enough to melt
(tungsten melts at 3695 K).  No external PushLight is supplied.  The engine
scans the scene for emissive objects, finds the filament, and auto-derives the
activation signal from its centroid and emission colour.

This is not a hack.  The light IS the filament.  The filament IS matter.
Matter pushes itself to the camera.  The ghost (PushLight as a free-floating
abstraction) has been replaced by hot tungsten.

Scene:
  - Glass envelope: borosilicate sphere, r=5 cm, opacity≈4% (Fresnel)
  - Tungsten filament: small ellipsoid inside the bulb, T=2800 K
  - Ground plane: warm concrete, receives the bulb's shadow
  - Background: near-black (unlit room)
  - No external PushLight — light=None, engine derives from filament

□σ = −ξR
"""

import math, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.render.entangler.vec        import Vec3
from mattershaper.render.entangler.shapes     import EntanglerSphere, EntanglerEllipsoid
from mattershaper.render.entangler.engine     import entangle
from mattershaper.render.entangler.projection import PushCamera
from mattershaper.materials.physics_materials import (
    phys_tungsten_filament, phys_glass_bulb,
)
from mattershaper.materials.material import Material

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

GAMMA   = 2.2
RES     = 400
DENSITY = 300


# ── Ground plane material ──────────────────────────────────────────────────
# Warm off-white concrete.  Receives the warm amber light from above.

concrete = Material(
    name        = 'concrete',
    color       = Vec3(0.72, 0.68, 0.60),
    reflectance = 0.05,
    roughness   = 0.85,
    opacity     = 1.0,
)


# ── Scene geometry ─────────────────────────────────────────────────────────
#
# The bulb hangs at the origin.  The filament is a thin vertical ellipsoid
# inside — coil approximated as a 4 mm × 36 mm blob.
# The glass envelope is a 5 cm sphere, nearly transparent.
# The ground plane sits 18 cm below the bulb centre.

filament = EntanglerEllipsoid(
    center   = Vec3(0.0, 0.0, 0.0),
    radii    = Vec3(0.004, 0.018, 0.004),  # 4 mm wide × 36 mm tall coil approx
    material = phys_tungsten_filament(T=2800, intensity=10.0),
)

bulb = EntanglerSphere(
    center   = Vec3(0.0, 0.0, 0.0),
    radius   = 0.05,                       # 5 cm — standard A19 bulb
    material = phys_glass_bulb(),
)

ground = EntanglerEllipsoid(
    center   = Vec3(0.0, -0.18, 0.0),
    radii    = Vec3(1.2, 0.008, 1.2),      # wide flat disc, 8 mm thick
    material = concrete,
)

# Object order matters for depth compositing — filament first so its emission
# reaches the compositor before the glass nodes obscure it from behind.
objects = [filament, bulb, ground]


# ── Camera ─────────────────────────────────────────────────────────────────
# Positioned slightly off-axis, looking slightly down at the hanging bulb.
# The ground plane is visible below.

camera = PushCamera(
    pos    = Vec3(0.08, 0.04, 0.30),
    look_at= Vec3(0.0, -0.02, 0.0),
    width  = RES,
    height = RES,
    fov    = 42,
)


# ── Render ─────────────────────────────────────────────────────────────────

def to_pil(pixels, w, h):
    img  = PILImage.new('RGB', (w, h))
    data = []
    for row in pixels:
        for p in row:
            r = int(min(1.0, max(0.0, p.x ** (1.0 / GAMMA))) * 255)
            g = int(min(1.0, max(0.0, p.y ** (1.0 / GAMMA))) * 255)
            b = int(min(1.0, max(0.0, p.z ** (1.0 / GAMMA))) * 255)
            data.append((r, g, b))
    img.putdata(data)
    return img


def main():
    outdir = os.path.join(os.path.dirname(__file__), 'misc')
    os.makedirs(outdir, exist_ok=True)

    print(f'  Filament emission:  {filament.material.emission}')
    print(f'  Glass opacity:      {bulb.material.opacity:.3f}  '
          f'({bulb.material.opacity * 100:.1f}% reflects, '
          f'{(1 - bulb.material.opacity) * 100:.1f}% transmits)')

    # The engine derives the PushLight from the filament automatically.
    # light=None — no ghost in this scene.
    print(f'\n  Rendering at {RES}×{RES}, density={DENSITY} …', flush=True)
    t0 = time.perf_counter()
    pixels = entangle(
        objects, camera,
        light    = None,           # no ghost — filament IS the light
        density  = DENSITY,
        bg_color = Vec3(0.01, 0.01, 0.015),   # near-black unlit room
        shadows  = True,
    )
    elapsed = time.perf_counter() - t0
    print(f'  Done in {elapsed:.2f}s')

    if HAS_PIL:
        path = os.path.join(outdir, 'render_lightbulb.png')
        to_pil(pixels, RES, RES).save(path)
        print(f'  Saved: {path}')
    else:
        print('  PIL not available — no image saved.')


if __name__ == '__main__':
    main()

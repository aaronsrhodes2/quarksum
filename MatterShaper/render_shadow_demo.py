"""
Shadow Demo — inter-object shadow casting.

A chrome sphere suspended above a white ground plane.
A light source from upper-left. The sphere blocks the light
and casts a shadow onto the ground — something the renderer
could NOT do before the shadow map.

Before: Lambert gives the sphere a dark back side (self-shading only).
        The ground plane is fully lit everywhere — no shadow cast.

After:  The light's depth buffer records what it sees. Any ground-plane
        node deeper than the light's recorded depth at that direction
        was behind the sphere — it never received those photons.
        Two pushes. No rays.

□σ = −ξR
"""

import math, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.render.entangler.vec        import Vec3
from mattershaper.render.entangler.shapes     import EntanglerSphere, EntanglerEllipsoid
from mattershaper.render.entangler.engine     import entangle
from mattershaper.render.entangler.projection import PushCamera
from mattershaper.render.entangler.illumination import PushLight
from mattershaper.materials.material          import Material

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Resolution ────────────────────────────────────────────────────────────────

RES     = 400
DENSITY = 300
GAMMA   = 2.2

# ── Materials ─────────────────────────────────────────────────────────────────

chrome = Material(
    name        = 'chrome',
    color       = Vec3(0.85, 0.87, 0.90),
    reflectance = 0.9,
    roughness   = 0.05,
    opacity     = 1.0,
)

ground_mat = Material(
    name        = 'ground',
    color       = Vec3(0.90, 0.88, 0.82),   # warm off-white
    reflectance = 0.2,
    roughness   = 0.8,
    opacity     = 1.0,
)

# ── Scene ─────────────────────────────────────────────────────────────────────

# Sphere floating above origin
sphere = EntanglerSphere(
    center    = Vec3(0.0, 1.2, 0.0),
    radius    = 1.0,
    material  = chrome,
)

# Ground plane: very flat ellipsoid, wide and shallow
# radii = (8, 0.08, 8) → a disc 16 units across, 0.16 units thick
ground = EntanglerEllipsoid(
    center   = Vec3(0.0, -0.04, 0.0),   # sits at y=0, top surface just above y=0
    radii    = Vec3(8.0, 0.08, 8.0),
    material = ground_mat,
)

objects = [sphere, ground]

# ── Camera: slightly elevated, looking down at the scene ──────────────────────

camera = PushCamera(
    pos    = Vec3(0.0, 3.5, 10.0),
    look_at= Vec3(0.0, 0.5, 0.0),
    width  = RES,
    height = RES,
    fov    = 45,
)

# ── Light: upper-left, strong ─────────────────────────────────────────────────

light = PushLight(
    pos       = Vec3(-5.0, 8.0, 6.0),
    intensity = 1.4,
    color     = Vec3(1.0, 0.97, 0.92),  # slightly warm
)

# ── Render ────────────────────────────────────────────────────────────────────

def to_pil(pixels, w, h):
    img = PILImage.new('RGB', (w, h))
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

    bg = Vec3(0.15, 0.16, 0.20)

    # Render WITHOUT shadows first (baseline — shows Lambert self-shading only)
    import time
    print("  Rendering WITHOUT shadows (Lambert only) …", flush=True)
    t0 = time.perf_counter()
    pix_no_shadow = entangle(objects, camera, light,
                             density=DENSITY, bg_color=bg, shadows=False)
    print(f"  Done in {time.perf_counter()-t0:.2f}s")

    if HAS_PIL:
        img = to_pil(pix_no_shadow, RES, RES)
        path = os.path.join(outdir, 'render_shadow_none.png')
        img.save(path)
        print(f"  Saved: {path}")

    # Render WITH shadows — shadow map, reverse-splat terminator
    print("\n  Rendering WITH shadows (two-push shadow map) …", flush=True)
    t0 = time.perf_counter()
    pix_shadow = entangle(objects, camera, light,
                          density=DENSITY, bg_color=bg, shadows=True)
    print(f"  Done in {time.perf_counter()-t0:.2f}s")

    if HAS_PIL:
        img = to_pil(pix_shadow, RES, RES)
        path = os.path.join(outdir, 'render_shadow_cast.png')
        img.save(path)
        print(f"  Saved: {path}")

    print("\n  Two renders complete.")
    print("  Compare render_shadow_none.png (no shadow cast on ground)")
    print("      vs render_shadow_cast.png  (sphere shadow falls on ground)\n")


if __name__ == '__main__':
    main()

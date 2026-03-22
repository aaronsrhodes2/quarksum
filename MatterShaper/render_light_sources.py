"""
Light Sources — Sun, candle flame, and the Moon (honestly).

Three panels rendered side by side:
  LEFT:   The Sun — G-type photosphere at 5778K. Blindingly over-exposed.
          No external PushLight. The sphere IS the source.

  CENTRE: Candle flame — hot soot at 1800K. Deep red-orange.
          Barely any blue photons. The flame IS the source.
          Animated GIF with ±25% flicker (convective instability).

  RIGHT:  The Moon — lunar regolith, albedo 0.12.
          NO emission field. Illuminated by an explicit Sun-derived
          PushLight. The moon reflects; it does not radiate.
          Label included in the render itself.

Physics sources:
  Sun:    Neckel & Labs (1984) Solar Phys. 90:205 — T_eff = 5778K
  Candle: Charalampopoulos & Chang (1987) Appl.Opt. 26:3499
          soot ε≈0.95, luminous zone T≈1400–1800K
  Moon:   Pieters (1999) table 1 — R=0.135, G=0.115, B=0.090
          Lane & Irvine (1973) Astron.J. 78:267 — geometric albedo 0.12

□σ = −ξR
"""

import math, os, sys, time, random
sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.render.entangler.vec        import Vec3
from mattershaper.render.entangler.shapes     import EntanglerSphere, EntanglerEllipsoid
from mattershaper.render.entangler.engine     import entangle
from mattershaper.render.entangler.projection import PushCamera
from mattershaper.render.entangler.illumination import PushLight
from mattershaper.materials.physics_materials import (
    phys_sun, phys_candle_flame, phys_moon_surface,
)
from mattershaper.materials.material import Material

try:
    from PIL import Image as PILImage, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    raise SystemExit("PIL required for this render.")

GAMMA   = 2.2
RES     = 300          # each panel
DENSITY = 500
CANDLE_FRAMES = 18

random.seed(42)        # repeatable flicker


# ── Shared geometry helpers ───────────────────────────────────────────────

def _ground(color, y=-1.8, rx=3.0):
    return EntanglerEllipsoid(
        center=Vec3(0, y, 0), radii=Vec3(rx, 0.06, rx),
        material=Material(
            name='ground', color=color,
            reflectance=0.04, roughness=0.90, opacity=1.0,
        ),
    )

def _camera(pos, look_at=None):
    return PushCamera(
        pos=pos,
        look_at=look_at or Vec3(0, 0, 0),
        width=RES, height=RES, fov=44,
    )

def _to_pil(pixels):
    img  = PILImage.new('RGB', (RES, RES))
    data = []
    for row in pixels:
        for p in row:
            r = int(min(1, max(0, p.x ** (1/GAMMA))) * 255)
            g = int(min(1, max(0, p.y ** (1/GAMMA))) * 255)
            b = int(min(1, max(0, p.z ** (1/GAMMA))) * 255)
            data.append((r, g, b))
    img.putdata(data)
    return img


# ── Panel A: Sun ──────────────────────────────────────────────────────────

def render_sun():
    sun_sphere = EntanglerSphere(
        center=Vec3(0, 0.3, 0), radius=0.5,
        material=phys_sun(intensity=500.0),
    )
    ground = _ground(Vec3(0.55, 0.50, 0.42), y=-1.8)  # sun-baked earth
    camera = _camera(Vec3(0.6, 0.5, 4.5), Vec3(0, -0.3, 0))

    print("  [Sun]    rendering …", flush=True)
    t0 = time.perf_counter()
    pix = entangle([sun_sphere, ground], camera,
                   light=None, density=DENSITY,
                   bg_color=Vec3(0.0, 0.0, 0.02),
                   shadows=True)
    print(f"  [Sun]    {time.perf_counter()-t0:.2f}s")
    return _to_pil(pix)


# ── Panel B: Candle — animated GIF ───────────────────────────────────────

def render_candle_frames():
    # Flame: small vertical ellipsoid, teardrop-ish
    base_intensity = 3.0
    camera = _camera(Vec3(0.4, 0.3, 3.5), Vec3(0, -0.5, 0))
    ground = _ground(Vec3(0.40, 0.35, 0.28), y=-1.8)  # warm wood

    frames = []
    for i in range(CANDLE_FRAMES):
        # Convective flicker: ±25% amplitude, slight T variation
        flicker = random.uniform(0.75, 1.00)
        T       = int(random.uniform(1650, 1850))
        mat     = phys_candle_flame(T=T, intensity=base_intensity * flicker)
        # Flame shape wobbles slightly in x
        wobble  = random.uniform(-0.015, 0.015)
        flame   = EntanglerEllipsoid(
            center=Vec3(wobble, 0.2, 0),
            radii=Vec3(0.06, 0.22, 0.06),
            material=mat,
        )
        print(f"  [Candle] frame {i+1}/{CANDLE_FRAMES} T={T}K flicker={flicker:.2f}", flush=True)
        t0 = time.perf_counter()
        pix = entangle([flame, ground], camera,
                       light=None, density=DENSITY,
                       bg_color=Vec3(0.005, 0.003, 0.002),
                       shadows=False)
        print(f"           {time.perf_counter()-t0:.2f}s")
        frames.append(_to_pil(pix))
    return frames


# ── Panel C: Moon (honest reflector) ─────────────────────────────────────

def render_moon():
    moon = EntanglerSphere(
        center=Vec3(0, 0.3, 0), radius=0.5,
        material=phys_moon_surface(),   # emission=None — does NOT emit
    )
    ground = _ground(Vec3(0.45, 0.44, 0.42), y=-1.8)  # grey stone
    camera = _camera(Vec3(0.6, 0.5, 4.5), Vec3(0, -0.3, 0))

    # The Moon has no emission — we must supply the Sun's light explicitly.
    # This is the honest architecture: the light comes from the Sun, not
    # from the Moon. We represent it as a PushLight at solar direction.
    # Intensity reduced by Moon geometric albedo (0.12) relative to direct sun.
    sun_light = PushLight(
        pos       = Vec3(8.0, 10.0, 6.0),   # sun direction, off-scene
        intensity = 1.2,                     # solar irradiance × Moon albedo
        color     = Vec3(1.0, 0.97, 0.90),   # slightly warm solar spectrum
    )

    print("  [Moon]   rendering …", flush=True)
    t0 = time.perf_counter()
    pix = entangle([moon, ground], camera,
                   light=sun_light, density=DENSITY,
                   bg_color=Vec3(0.0, 0.0, 0.02),
                   shadows=True)
    print(f"  [Moon]   {time.perf_counter()-t0:.2f}s")
    return _to_pil(pix)


# ── Composite ─────────────────────────────────────────────────────────────

def label(img, text, y=8):
    """Burn a simple label onto an image (no font file needed)."""
    draw = ImageDraw.Draw(img)
    # White text with dark shadow for legibility on any background
    draw.text((11, y+1), text, fill=(0, 0, 0))
    draw.text((10, y),   text, fill=(255, 255, 255))
    return img


def main():
    outdir = os.path.join(os.path.dirname(__file__), 'misc')
    os.makedirs(outdir, exist_ok=True)

    sun_img    = render_sun()
    moon_img   = render_moon()
    candle_frames = render_candle_frames()

    # ── Static comparison: sun | candle[0] | moon ─────────────────────────
    label(sun_img,    "Sun  5778 K  (emits)")
    label(candle_frames[0], "Candle  ~1800 K  (emits)")
    label(moon_img,   "Moon  (REFLECTS — no emission)")

    wide = PILImage.new('RGB', (RES * 3 + 4, RES))
    wide.paste(sun_img,         (0,         0))
    wide.paste(candle_frames[0],(RES + 2,   0))
    wide.paste(moon_img,        (RES * 2 + 4, 0))

    static_path = os.path.join(outdir, 'render_light_sources.png')
    wide.save(static_path)
    print(f"\n  Saved: {static_path}")

    # ── Animated candle GIF ───────────────────────────────────────────────
    gif_path = os.path.join(outdir, 'render_candle_flicker.gif')
    [label(f, "Candle  ~1800 K  (emits)") for f in candle_frames]
    candle_frames[0].save(
        gif_path, save_all=True,
        append_images=candle_frames[1:],
        loop=0, duration=80,
    )
    print(f"  Saved: {gif_path}")


if __name__ == '__main__':
    main()

"""
Gemstone Showcase — spinning gems under strong backlight.

Four asymmetric oblate ellipsoids (ruby, sapphire, emerald, amethyst)
rotate around their Y axes under a strong white backlight.
Beer-Lambert volume absorption filters the transmitted light — each gem
becomes a stained-glass window, passing only its characteristic wavelengths.

□σ = −ξR
"""

import math, time, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.shapes import EntanglerEllipsoid, rotation_matrix
from mattershaper.render.entangler.engine import entangle
from mattershaper.materials.material import Material

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    raise RuntimeError("PIL required: pip install pillow --break-system-packages")

# ── Parameters ────────────────────────────────────────────────────────────────

RES     = 160      # pixels per gem (square)
FRAMES  = 24       # full rotation in FRAMES steps
DENSITY = 300      # surface nodes / unit²
FPS     = 10
GAMMA   = 2.2

# ── Gem materials (Beer-Lambert alpha in /scene-unit ≈ /inch) ─────────────────
#
# Transmission through 1.3 in of gem (2 × ry = 2 × 0.65):
#   T = exp(−α × 1.3)
#
# Ruby    (Waychunas 1988, Am. Mineral. 73:916):
#   T_r = exp(−0.254×1.3) = 0.72  T_g = exp(−7.62×1.3) = 5e-5  T_b = exp(−3.05×1.3) = 0.019
#
# Sapphire (Fe²⁺/Ti⁴⁺ charge transfer, Mattson & Rossman 1988, approximate):
#   T_r = exp(−4.0×1.3)  = 0.005  T_g = exp(−3.0×1.3)  = 0.020  T_b = exp(−0.15×1.3) = 0.82
#
# Emerald  (Cr³⁺, approximate, Taran et al. 2003):
#   T_r = exp(−3.5×1.3)  = 0.011  T_g = exp(−0.12×1.3) = 0.856  T_b = exp(−3.0×1.3)  = 0.020
#
# Amethyst (Fe³⁺, approximate, Lehmann & Moore 1966):
#   T_r = exp(−0.3×1.3)  = 0.677  T_g = exp(−4.0×1.3)  = 0.005  T_b = exp(−0.3×1.3)  = 0.677

GEMS = [
    dict(
        name     = 'Ruby',
        color    = Vec3(0.85, 0.05, 0.05),
        alpha_r  = 0.10 * 2.54,   # Waychunas (1988)
        alpha_g  = 3.00 * 2.54,
        alpha_b  = 1.20 * 2.54,
        radii    = Vec3(1.10, 0.65, 0.80),   # asymmetric → visible spin
    ),
    dict(
        name     = 'Sapphire',
        color    = Vec3(0.05, 0.10, 0.90),
        alpha_r  = 4.00,           # approximate, Mattson & Rossman (1988)
        alpha_g  = 3.00,
        alpha_b  = 0.15,
        radii    = Vec3(0.85, 0.65, 1.10),
    ),
    dict(
        name     = 'Emerald',
        color    = Vec3(0.05, 0.85, 0.10),
        alpha_r  = 3.50,           # approximate, Taran et al. (2003)
        alpha_g  = 0.12,
        alpha_b  = 3.00,
        radii    = Vec3(0.75, 0.90, 1.00),   # slightly taller (beryl prism habit)
    ),
    dict(
        name     = 'Amethyst',
        color    = Vec3(0.65, 0.10, 0.85),
        alpha_r  = 0.30,           # approximate, Lehmann & Moore (1966)
        alpha_g  = 4.00,
        alpha_b  = 0.30,
        radii    = Vec3(1.00, 0.60, 0.85),
    ),
]

# ── Build material and shape for a gem at a given Y-rotation angle ────────────

def make_gem(spec, ry_angle):
    mat = Material(
        name        = spec['name'],
        color       = spec['color'],
        reflectance = 0.13,
        roughness   = 0.10,
        opacity     = 0.02,        # near-transparent surface — backlight shines through
        alpha_r     = spec['alpha_r'],
        alpha_g     = spec['alpha_g'],
        alpha_b     = spec['alpha_b'],
    )
    return EntanglerEllipsoid(
        center     = Vec3(0, 0, 0),
        radii      = spec['radii'],
        rotation   = rotation_matrix(ry=ry_angle),
        material   = mat,
        fill_volume= True,
    )

# ── Camera: fixed, slightly elevated ─────────────────────────────────────────

def make_cam():
    class Cam:
        width        = RES
        height       = RES
        pos          = Vec3(0.0, 1.2, 8.0)
        forward      = Vec3(0.0, -0.15, -1.0)   # tilt down slightly toward gem
        up           = Vec3(0.0,  1.0,  0.0)
        right        = Vec3(1.0,  0.0,  0.0)
        tan_half_fov = math.tan(math.radians(22.5))
        aspect       = 1.0
    return Cam()

# ── Light: strong, behind the gems ───────────────────────────────────────────
#
# Fixed at (1, 3, −12) — behind and above. Stays fixed throughout the
# animation so as the gems spin, both the silhouette AND the lighting angle
# change simultaneously. At frame 0 the back face is fully illuminated;
# as the gem rotates the light rakes across it.

class BackLight:
    pos       = Vec3(1.0, 3.0, -12.0)
    color     = Vec3(1.00, 0.98, 0.95)
    intensity = 3.0                        # strong

# ── Background: white (the light source plane behind the gems) ────────────────

BG = Vec3(1.0, 1.0, 1.0)

# ── Render one gem panel ──────────────────────────────────────────────────────

def render_panel(spec, ry_angle):
    gem = make_gem(spec, ry_angle)
    cam = make_cam()
    return entangle([gem], cam, BackLight, density=DENSITY,
                    bg_color=BG, volume_n_nodes=6000)

# ── PIL helpers ───────────────────────────────────────────────────────────────

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

def stitch_row(panels):
    total_w = sum(p.width for p in panels)
    h = panels[0].height
    out = PILImage.new('RGB', (total_w, h), (255, 255, 255))
    x = 0
    for p in panels:
        out.paste(p, (x, 0))
        x += p.width
    return out

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    outdir = os.path.join(os.path.dirname(__file__), 'misc')
    os.makedirs(outdir, exist_ok=True)

    n = len(GEMS)
    print(f"\n  GEMSTONE SHOWCASE")
    print(f"  {n} gems × {FRAMES} frames × {RES}×{RES}px  ({n * FRAMES} renders)")
    print(f"  Backlit: intensity=3.0, pos=(1,3,−12), bg=white")
    print(f"  Beer-Lambert volume fill, opacity=0.02 surface\n")

    gif_frames  = []
    angle_step  = 2 * math.pi / FRAMES
    t_total     = time.perf_counter()

    for f in range(FRAMES):
        ry = f * angle_step
        deg = math.degrees(ry)
        panels = []

        for spec in GEMS:
            t0 = time.perf_counter()
            pixels = render_panel(spec, ry)
            img = to_pil(pixels, RES, RES)
            panels.append(img)
            elapsed = time.perf_counter() - t0
            print(f"  frame {f+1:2d}/{FRAMES}  {spec['name']:<10}  "
                  f"ry={deg:5.1f}°  {elapsed:.2f}s", flush=True)

        row = stitch_row(panels)
        gif_frames.append(row)

        # Save still at frame 0 (backlit, no rotation) and frame 6 (quarter turn)
        if f in (0, 6):
            tag = 'backlit' if f == 0 else 'quarter'
            row.save(os.path.join(outdir, f'gemstone_showcase_{tag}.png'))
            for spec, panel in zip(GEMS, panels):
                panel.save(os.path.join(outdir,
                    f'gem_{spec["name"].lower()}_{tag}.png'))

    # Animated GIF
    gif_path = os.path.join(outdir, 'gemstone_showcase.gif')
    gif_frames[0].save(
        gif_path,
        save_all      = True,
        append_images = gif_frames[1:],
        loop          = 0,
        duration      = int(1000 / FPS),
        optimize      = False,
    )

    total = time.perf_counter() - t_total
    fw, fh = gif_frames[0].width, gif_frames[0].height
    print(f"\n  Done in {total:.1f}s")
    print(f"  GIF:    {gif_path}  ({fw}×{fh}, {FRAMES} frames @ {FPS}fps)")
    print(f"  Stills: misc/gemstone_showcase_backlit.png")
    print(f"          misc/gemstone_showcase_quarter.png\n")

if __name__ == '__main__':
    main()

"""
Render the photometric ground truth scene: aluminum sphere, copper ellipsoid,
ruby oblate crystal (corundum tablet habit). Output stats + PNG + HTML report.

□σ = −ξR
"""

import math
import sys
import os
import base64
import io

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.shapes import EntanglerSphere, EntanglerEllipsoid
from mattershaper.render.entangler.engine import entangle
from mattershaper.materials.material import Material
from mattershaper.materials.physics_materials import aluminum as phys_aluminum
from mattershaper.materials.physics_materials import copper as phys_copper

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Scene parameters ──────────────────────────────────────────────────────────

WIDTH   = 512
HEIGHT  = 512
DENSITY = 300
# No supersampling. The renderer is resolution-independent:
# focal_px and splat_r both scale linearly with width, so node coverage
# is correct at any resolution. The pixel-grid edge is below visual
# threshold at sufficient resolution — no averaging required or wanted.

def make_camera(w, h):
    class Camera:
        width        = w
        height       = h
        pos          = Vec3(0, 0, 8.0)
        forward      = Vec3(0, 0, -1)
        up           = Vec3(0, 1, 0)
        right        = Vec3(1, 0, 0)
        fov_deg      = 45.0
        tan_half_fov = math.tan(math.radians(22.5))
        aspect       = 1.0
    return Camera()

class KeyLight:
    pos       = Vec3(4, 7, 9)
    color     = Vec3(1.0, 0.98, 0.95)
    intensity = 1.0

class AxialLight:
    """Co-axial: illuminates center-facing surface for Beer-Lambert column test."""
    pos       = Vec3(0, 0, 10)
    color     = Vec3(1.0, 1.0, 1.0)
    intensity = 1.0

BG = Vec3(0.10, 0.10, 0.12)

# ── Materials ─────────────────────────────────────────────────────────────────

def make_aluminum():
    # Use physics material — Drude model, Palik (1985) / Rakić (1998)
    return phys_aluminum()

def make_copper():
    # Use physics material — d-band edge 2.1 eV, Johnson & Christy (1972)
    # color Vec3(0.94, 0.64, 0.55): salmon-copper, not the brass-yellow (0.72,0.45,0.20)
    return phys_copper()

def make_ruby():
    # Waychunas (1988) Am. Mineralogist 73:916-934
    return Material(
        name='Ruby',
        color=Vec3(0.70, 0.05, 0.05),
        reflectance=0.12, roughness=0.25, opacity=0.04,
        alpha_r=0.10 * 2.54,   # 0.254 /inch — transparent red
        alpha_g=3.0  * 2.54,   # 7.62  /inch — ν₁ band eats green
        alpha_b=1.2  * 2.54,   # 3.048 /inch — ν₂ band
    )

# ── Render ────────────────────────────────────────────────────────────────────

def render_object(shapes, light, label, volume_n_nodes=8000):
    cam = make_camera(WIDTH, HEIGHT)
    print(f"  Rendering {label} at {WIDTH}×{HEIGHT}, density={DENSITY}...", flush=True)
    return entangle(shapes, cam, light, density=DENSITY,
                    volume_n_nodes=volume_n_nodes)

def pixels_to_pil(pixels, gamma=2.2):
    """Convert Vec3 pixel array to PIL Image with gamma correction."""
    img = PILImage.new('RGB', (WIDTH, HEIGHT))
    data = []
    for row in pixels:
        for p in row:
            r = int(min(1.0, max(0.0, p.x ** (1.0/gamma))) * 255)
            g = int(min(1.0, max(0.0, p.y ** (1.0/gamma))) * 255)
            b = int(min(1.0, max(0.0, p.z ** (1.0/gamma))) * 255)
            data.append((r, g, b))
    img.putdata(data)
    return img

def img_to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')

# ── Stats ─────────────────────────────────────────────────────────────────────

def compute_stats(pixels, label):
    bg = BG
    object_pixels = []
    all_pixels = []

    for row in pixels:
        for p in row:
            lum = 0.2126*p.x + 0.7152*p.y + 0.0722*p.z
            all_pixels.append((p, lum))
            diff = abs(p.x - bg.x) + abs(p.y - bg.y) + abs(p.z - bg.z)
            if diff > 0.02:
                object_pixels.append((p, lum))

    if not object_pixels:
        return {}

    # Highlight pixel (max luminance)
    highlight, hl_lum = max(object_pixels, key=lambda x: x[1])

    # Center pixel
    cx, cy = WIDTH // 2, HEIGHT // 2
    center = pixels[cy][cx]

    # Mean of object pixels
    mean_r = sum(p.x for p,_ in object_pixels) / len(object_pixels)
    mean_g = sum(p.y for p,_ in object_pixels) / len(object_pixels)
    mean_b = sum(p.z for p,_ in object_pixels) / len(object_pixels)

    # Max luminance
    max_lum = max(l for _,l in object_pixels)
    mean_lum = sum(l for _,l in object_pixels) / len(object_pixels)

    stats = {
        'label':          label,
        'n_object_pixels': len(object_pixels),
        'n_total_pixels':  WIDTH * HEIGHT,
        'coverage_pct':   100.0 * len(object_pixels) / (WIDTH * HEIGHT),
        'highlight_rgb':  (highlight.x, highlight.y, highlight.z),
        'highlight_lum':  hl_lum,
        'highlight_r_over_g': highlight.x / max(highlight.y, 1e-6),
        'highlight_r_over_b': highlight.x / max(highlight.z, 1e-6),
        'center_rgb':     (center.x, center.y, center.z),
        'center_r_over_g': center.x / max(center.y, 1e-6),
        'mean_rgb':       (mean_r, mean_g, mean_b),
        'mean_lum':       mean_lum,
        'max_lum':        max_lum,
    }
    return stats

def print_stats(s):
    print(f"\n  ┌─ {s['label']} ───────────────────────────────────────")
    print(f"  │  Coverage:        {s['n_object_pixels']:>5} / {s['n_total_pixels']} pixels  ({s['coverage_pct']:.1f}%)")
    print(f"  │  Highlight RGB:   ({s['highlight_rgb'][0]:.4f}, {s['highlight_rgb'][1]:.4f}, {s['highlight_rgb'][2]:.4f})")
    print(f"  │  Highlight lum:   {s['highlight_lum']:.4f}")
    print(f"  │  Highlight R/G:   {s['highlight_r_over_g']:.3f}")
    print(f"  │  Highlight R/B:   {s['highlight_r_over_b']:.3f}")
    print(f"  │  Center RGB:      ({s['center_rgb'][0]:.4f}, {s['center_rgb'][1]:.4f}, {s['center_rgb'][2]:.4f})")
    print(f"  │  Center R/G:      {s['center_r_over_g']:.3f}")
    print(f"  │  Mean RGB:        ({s['mean_rgb'][0]:.4f}, {s['mean_rgb'][1]:.4f}, {s['mean_rgb'][2]:.4f})")
    print(f"  │  Mean luminance:  {s['mean_lum']:.4f}")
    print(f"  └───────────────────────────────────────────────────────")

# ── Ground truth annotations ──────────────────────────────────────────────────

GROUND_TRUTH = {
    'Aluminum sphere': {
        'source': 'Palik (1985) Shiles et al. / Rakić (1998)',
        'claim':  'Spectrally flat Drude. Spread |R-G| < 0.08 at highlight.',
        'check':  lambda s: abs(s['highlight_rgb'][0]-s['highlight_rgb'][1]) < 0.08,
        'detail': lambda s: f"|R−G| = {abs(s['highlight_rgb'][0]-s['highlight_rgb'][1]):.4f}  |G−B| = {abs(s['highlight_rgb'][1]-s['highlight_rgb'][2]):.4f}",
    },
    'Copper ellipsoid': {
        'source': 'Palik (1985) / Johnson & Christy (1972)',
        'claim':  'd-band edge at 2.1 eV. R > G > B at highlight. R/B ≥ 1.5.',
        'check':  lambda s: (s['highlight_rgb'][0] > s['highlight_rgb'][1]
                             and s['highlight_rgb'][1] > s['highlight_rgb'][2]
                             and s['highlight_r_over_b'] >= 1.5),
        'detail': lambda s: f"R/G = {s['highlight_r_over_g']:.3f}  R/B = {s['highlight_r_over_b']:.3f}",
    },
    'Ruby crystal (corundum tablet)': {
        'source': 'Waychunas (1988) Am. Mineralogist 73:916',
        'claim':  'ν₁ band at 18200 cm⁻¹. Center pixel R/G ≥ 10.',
        'check':  lambda s: s['center_r_over_g'] >= 10,
        'detail': lambda s: f"Center R/G = {s['center_r_over_g']:.2f}  (Beer-Lambert: T_red/T_green ≈ 1583×/inch)",
    },
}

# ── HTML report ───────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Photometric Ground Truth — Apollonian σ-Foam</title>
<style>
  body {{ background: #0a0a0c; color: #d0d0d8; font-family: 'Courier New', monospace;
         margin: 0; padding: 24px; }}
  h1   {{ color: #c8c8d8; font-size: 1.1em; letter-spacing: 0.12em;
          border-bottom: 1px solid #333; padding-bottom: 8px; margin-bottom: 24px; }}
  h2   {{ color: #9898b8; font-size: 0.85em; letter-spacing: 0.08em; margin: 0 0 4px 0; }}
  .grid {{ display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 32px; }}
  .card {{ background: #13131a; border: 1px solid #252535;
           border-radius: 4px; padding: 16px; flex: 1; min-width: 280px; }}
  .card img {{ width: 256px; height: 256px; display: block; image-rendering: pixelated;
               border: 1px solid #252535; margin-bottom: 12px; }}
  .stat  {{ font-size: 0.78em; color: #8888a8; margin: 3px 0; }}
  .stat span {{ color: #c0c8e0; }}
  .pass  {{ color: #6cbb6c; font-size: 0.82em; margin-top: 8px; }}
  .fail  {{ color: #cc5555; font-size: 0.82em; margin-top: 8px; }}
  .src   {{ color: #5a6080; font-size: 0.72em; margin-top: 6px; }}
  .eq    {{ color: #7090c0; font-size: 0.82em; margin-top: 16px;
            border-top: 1px solid #252535; padding-top: 10px; }}
  .title {{ color: #707090; font-size: 0.70em; letter-spacing: 0.15em;
            text-transform: uppercase; margin-bottom: 2px; }}
</style>
</head>
<body>
<h1>PHOTOMETRIC GROUND TRUTH — APOLLONIAN σ-FOAM</h1>
<div class="grid">
{cards}
</div>
<div class="eq">□σ = −ξR &nbsp;·&nbsp; Beer-Lambert: op_i = 1 − exp(−α_i × dl) &nbsp;·&nbsp;
Porter-Duff per channel &nbsp;·&nbsp; Matter requires fuel. The gem is a filter.</div>
</body>
</html>"""

CARD_TEMPLATE = """  <div class="card">
    <div class="title">{label}</div>
    <h2>{name}</h2>
    <img src="data:image/png;base64,{b64}" alt="{name}">
    <div class="stat">Coverage: <span>{coverage:.1f}%</span> of frame ({n_obj} px)</div>
    <div class="stat">Highlight RGB: <span>({hr:.4f}, {hg:.4f}, {hb:.4f})</span></div>
    <div class="stat">Highlight lum: <span>{hlum:.4f}</span></div>
    <div class="stat">Highlight R/G: <span>{h_rg:.3f}</span> &nbsp; R/B: <span>{h_rb:.3f}</span></div>
    <div class="stat">Center RGB: <span>({cr:.4f}, {cg:.4f}, {cb:.4f})</span></div>
    <div class="stat">Center R/G: <span>{c_rg:.3f}</span></div>
    <div class="stat">Mean RGB: <span>({mr:.4f}, {mg:.4f}, {mb:.4f})</span></div>
    <div class="{pass_cls}">{pass_mark}  {claim}</div>
    <div class="stat">{detail}</div>
    <div class="src">{source}</div>
  </div>"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    outdir = os.path.join(os.path.dirname(__file__), 'misc')
    os.makedirs(outdir, exist_ok=True)

    print("\n  PHOTOMETRIC GROUND TRUTH RENDER")
    print("  ================================\n")

    renders = []

    # ── 1. Aluminum sphere ────────────────────────────────────────────────────
    print("  [1/3] Aluminum sphere")
    al_mat = make_aluminum()
    al_sphere = EntanglerSphere(center=Vec3(0,0,0), radius=1.0, material=al_mat)
    al_pixels = render_object([al_sphere], KeyLight(), 'Aluminum sphere')
    al_stats  = compute_stats(al_pixels, 'Aluminum sphere')
    print_stats(al_stats)
    al_img = pixels_to_pil(al_pixels)
    al_img.save(os.path.join(outdir, 'render_aluminum_sphere.png'))

    # ── 2. Copper prolate ellipsoid ───────────────────────────────────────────
    print("\n  [2/3] Copper prolate ellipsoid")
    cu_mat = make_copper()
    cu_ell  = EntanglerEllipsoid(center=Vec3(0,0,0), radii=Vec3(0.8,1.0,0.8),
                                  material=cu_mat)
    cu_pixels = render_object([cu_ell], KeyLight(), 'Copper ellipsoid')
    cu_stats  = compute_stats(cu_pixels, 'Copper ellipsoid')
    print_stats(cu_stats)
    cu_img = pixels_to_pil(cu_pixels)
    cu_img.save(os.path.join(outdir, 'render_copper_ellipsoid.png'))

    # ── 3. Ruby oblate ellipsoid (corundum tablet, c/a=0.65) ──────────────────
    print("\n  [3/3] Ruby crystal (corundum tablet, c/a=0.65)")
    rb_mat = make_ruby()
    rb_ell  = EntanglerEllipsoid(center=Vec3(0,0,0), radii=Vec3(1.0,1.0,0.65),
                                  material=rb_mat, fill_volume=True)
    rb_pixels = render_object([rb_ell], AxialLight(), 'Ruby crystal (corundum tablet)',
                               volume_n_nodes=10000)
    rb_stats  = compute_stats(rb_pixels, 'Ruby crystal (corundum tablet)')
    print_stats(rb_stats)
    rb_img = pixels_to_pil(rb_pixels)
    rb_img.save(os.path.join(outdir, 'render_ruby_crystal.png'))

    # ── Ground truth verification summary ─────────────────────────────────────
    print("\n  GROUND TRUTH VERIFICATION")
    print("  ─────────────────────────")
    for stats, gt_key in [
        (al_stats, 'Aluminum sphere'),
        (cu_stats, 'Copper ellipsoid'),
        (rb_stats, 'Ruby crystal (corundum tablet)'),
    ]:
        gt = GROUND_TRUTH[gt_key]
        passed = gt['check'](stats)
        mark = "✓ PASS" if passed else "✗ FAIL"
        detail = gt['detail'](stats)
        print(f"\n  {mark}  {gt_key}")
        print(f"         {gt['claim']}")
        print(f"         {detail}")
        print(f"         Source: {gt['source']}")

    # ── HTML report ───────────────────────────────────────────────────────────
    renders = [
        (al_stats,  al_img,  'OBJECT I',  'Aluminum sphere',
         GROUND_TRUTH['Aluminum sphere']),
        (cu_stats,  cu_img,  'OBJECT II', 'Copper ellipsoid',
         GROUND_TRUTH['Copper ellipsoid']),
        (rb_stats,  rb_img,  'OBJECT III','Ruby crystal (corundum tablet)',
         GROUND_TRUTH['Ruby crystal (corundum tablet)']),
    ]

    cards = []
    for stats, img, label, name, gt in renders:
        passed = gt['check'](stats)
        hr, hg, hb = stats['highlight_rgb']
        cr, cg, cb = stats['center_rgb']
        mr, mg, mb = stats['mean_rgb']
        cards.append(CARD_TEMPLATE.format(
            label=label,
            name=name,
            b64=img_to_b64(img),
            coverage=stats['coverage_pct'],
            n_obj=stats['n_object_pixels'],
            hr=hr, hg=hg, hb=hb,
            hlum=stats['highlight_lum'],
            h_rg=stats['highlight_r_over_g'],
            h_rb=stats['highlight_r_over_b'],
            cr=cr, cg=cg, cb=cb,
            c_rg=stats['center_r_over_g'],
            mr=mr, mg=mg, mb=mb,
            pass_cls='pass' if passed else 'fail',
            pass_mark='✓ PASS' if passed else '✗ FAIL',
            claim=gt['claim'],
            detail=gt['detail'](stats),
            source=gt['source'],
        ))

    html_path = os.path.join(outdir, 'photometric_ground_truth.html')
    with open(html_path, 'w') as f:
        f.write(HTML_TEMPLATE.format(cards='\n'.join(cards)))

    print(f"\n  HTML report → misc/photometric_ground_truth.html")
    print(f"  PNGs        → misc/render_aluminum_sphere.png")
    print(f"               misc/render_copper_ellipsoid.png")
    print(f"               misc/render_ruby_crystal.png\n")

if __name__ == '__main__':
    main()

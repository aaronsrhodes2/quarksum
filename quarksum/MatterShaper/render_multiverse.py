"""
MatterShaper — Multiverse Comparison.

What does matter look like in universes with different ξ values?

ξ determines how gravity couples to QCD. Different ξ → different:
- Nucleon masses (proton heavier or lighter)
- Bond strengths (matter more or less rigid)
- Conversion threshold (how deep into a gravity well before matter fails)
- Nesting levels (how many chiral layers from Hubble to Planck)

We render the same scene with three different ξ values:
- ξ = 0.05  → "Resilient Universe" (matter barely notices gravity)
- ξ = 0.1582 → "Our Universe" (the one we live in)
- ξ = 0.40  → "Heavy Universe" (matter strongly coupled to gravity)
"""

import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.geometry import Vec3, Sphere, Plane
from mattershaper.materials import Material
from mattershaper.camera import Camera
from mattershaper.render.raytracer import Light, Scene, render_scene, render_to_svg


def universe_properties(xi):
    """Compute key properties of a universe with coupling constant ξ."""
    LAMBDA_QCD = 217.0  # MeV, same across universes (it's the base scale)
    PROTON_BARE = 8.99   # MeV, Higgs contribution (σ-invariant)
    PROTON_QCD = 929.282 # MeV at σ=0

    # Conversion threshold: where matter dissolves
    sigma_conv = -math.log(xi) if xi > 0 else float('inf')

    # Number of nesting levels (Hubble to Planck)
    M_hubble = 8.8e52  # kg
    M_planck = 2.176e-8  # kg
    n_levels = math.log(M_hubble / M_planck) / math.log(1/xi) if xi < 1 else float('inf')

    # At Earth's surface (σ ≈ 7e-10 for our universe, scales with ξ)
    # σ_earth = ξ × GM/(Rc²)
    G = 6.674e-11
    C = 2.998e8
    M_earth = 5.972e24
    R_earth = 6.371e6
    sigma_earth = xi * G * M_earth / (R_earth * C**2)

    # Proton mass at Earth's surface in this universe
    proton_surface = PROTON_BARE + PROTON_QCD * math.exp(sigma_earth)
    proton_shift_ppm = (proton_surface / (PROTON_BARE + PROTON_QCD) - 1) * 1e6

    # At a neutron star surface (M=2M_sun, R=10km)
    M_ns = 2 * 1.989e30
    R_ns = 10000
    sigma_ns = xi * G * M_ns / (R_ns * C**2)
    proton_ns = PROTON_BARE + PROTON_QCD * math.exp(sigma_ns)

    return {
        'xi': xi,
        'sigma_conv': sigma_conv,
        'n_levels': n_levels,
        'sigma_earth': sigma_earth,
        'proton_shift_earth_ppm': proton_shift_ppm,
        'sigma_ns': sigma_ns,
        'proton_ns_mev': proton_ns,
        'ns_shift_pct': (proton_ns / (PROTON_BARE + PROTON_QCD) - 1) * 100,
    }


def build_scene_for_universe(xi, label):
    """Build a scene where material properties reflect the universe's ξ.

    In a heavy-ξ universe, the same gravitational environment produces
    larger σ shifts. We visualize this by tinting the scene:
    - Low ξ (resilient): materials look "normal", cool blue tint
    - Our ξ: standard appearance
    - High ξ (heavy): materials are warmer, denser-looking, reddish cast
    """
    scene = Scene()

    # Background tint reflects the universe's character
    if xi < 0.1:
        bg = Vec3(0.01, 0.02, 0.05)  # cool blue — stable universe
        ambient = Vec3(0.05, 0.07, 0.12)
    elif xi > 0.3:
        bg = Vec3(0.05, 0.02, 0.01)  # warm red — heavy universe
        ambient = Vec3(0.12, 0.07, 0.05)
    else:
        bg = Vec3(0.01, 0.01, 0.03)  # our universe — neutral
        ambient = Vec3(0.08, 0.08, 0.10)

    scene.background = bg
    scene.ambient = ambient

    # The "matter sensitivity" factor — how much σ shifts appearance
    # At Earth surface, σ is tiny so we exaggerate for visualization
    sensitivity = xi / 0.1582  # normalized to our universe

    # Ground — density shifts with ξ (darker = denser in heavy universe)
    ground_brightness = max(0.05, 0.15 / sensitivity)
    ground = Plane(
        point=Vec3(0, -1, 0),
        normal=Vec3(0, 1, 0),
        material=Material(
            name="Ground",
            color=Vec3(ground_brightness, ground_brightness * 0.85, ground_brightness * 0.7),
            reflectance=0.05 * sensitivity,  # denser = slightly more reflective
            roughness=0.9,
        ),
    )
    scene.add(ground)

    # Central sphere — "proton analog"
    # In a heavy universe, matter is denser, more massive, slightly shifted
    proton_color_r = min(1.0, 0.85 * sensitivity)
    proton_color_g = max(0.3, 0.75 / sensitivity)
    proton_color_b = max(0.2, 0.65 / sensitivity)

    center = Sphere(
        center=Vec3(0, 0.2, -3),
        radius=1.2,
        material=Material(
            name="Proton Analog",
            color=Vec3(proton_color_r, proton_color_g, proton_color_b),
            reflectance=0.15,
            roughness=0.3,
        ),
    )
    scene.add(center)

    # Orbiting smaller sphere — "neutron"
    neutron_r = min(1.0, 0.5 + 0.3 * sensitivity)
    left = Sphere(
        center=Vec3(-2.0, -0.2, -4),
        radius=0.7,
        material=Material(
            name="Neutron Analog",
            color=Vec3(neutron_r, 0.55, 0.45),
            reflectance=0.4,
            roughness=0.15,
        ),
    )
    scene.add(left)

    # "Electron" — small, blue (EM properties unchanged across ξ!)
    # THIS is the key insight: the electron looks the SAME in every universe
    # because its mass is Higgs-only, not QCD
    right = Sphere(
        center=Vec3(1.8, -0.5, -3.5),
        radius=0.4,
        material=Material(
            name="Electron Analog",
            color=Vec3(0.3, 0.5, 0.9),  # SAME in all universes
            reflectance=0.5,
            roughness=0.05,
        ),
    )
    scene.add(right)

    # Lights
    scene.add_light(Light(
        pos=Vec3(5, 8, 2),
        color=Vec3(1.0, 0.95, 0.85),
        intensity=1.0,
    ))
    scene.add_light(Light(
        pos=Vec3(-4, 6, 0),
        color=Vec3(0.6, 0.7, 1.0),
        intensity=0.4,
    ))

    return scene


def render_universe(xi, label, out_dir, width=200, height=150):
    """Render one universe."""
    scene = build_scene_for_universe(xi, label)
    camera = Camera(
        pos=Vec3(0, 1.5, 3),
        look_at=Vec3(0, 0, -3),
        up=Vec3(0, 1, 0),
        fov=55,
    )

    print(f"\n  Rendering ξ={xi} ({label})...")
    t0 = time.time()
    pixels = render_scene(scene, camera, width, height)
    t1 = time.time()
    print(f"  {width}×{height} in {t1-t0:.2f}s")

    svg_path = os.path.join(out_dir, f'universe_xi_{xi:.4f}.svg')
    render_to_svg(pixels, svg_path, pixel_size=4)
    return svg_path, pixels


def compose_comparison_svg(universes, out_dir, pixel_size=4):
    """Create a single SVG comparing all three universes side by side."""
    width_each = 200
    height_each = 150
    gap = 20
    header_h = 80
    footer_h = 120
    panel_w = width_each * pixel_size
    total_w = len(universes) * panel_w + (len(universes) - 1) * gap + 60
    total_h = height_each * pixel_size + header_h + footer_h + 40

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" '
             f'width="{total_w}" height="{total_h}">\n']
    parts.append(f'<rect width="{total_w}" height="{total_h}" fill="#0a0a1a"/>\n')

    # Title
    parts.append(f'<text x="{total_w//2}" y="30" text-anchor="middle" fill="#ffffff" '
                 f'font-family="Helvetica,Arial,sans-serif" font-size="20" font-weight="bold">'
                 f'THE MULTIVERSE: MATTER UNDER DIFFERENT ξ VALUES</text>\n')
    parts.append(f'<text x="{total_w//2}" y="52" text-anchor="middle" fill="#888888" '
                 f'font-family="Helvetica,Arial,sans-serif" font-size="11">'
                 f'Same atoms, same EM, different gravity-QCD coupling · MatterShaper / SSBM</text>\n')

    for idx, (xi, label, props, svg_path, pixels) in enumerate(universes):
        x_off = 30 + idx * (panel_w + gap)
        y_off = header_h

        # Frame
        parts.append(f'<rect x="{x_off-2}" y="{y_off-2}" width="{panel_w+4}" '
                     f'height="{height_each * pixel_size + 4}" fill="none" '
                     f'stroke="#444" stroke-width="1" rx="3"/>\n')

        # Render pixels
        for y, row in enumerate(pixels):
            x = 0
            while x < len(row):
                color = row[x]
                hex_color = color.to_hex()
                run_end = x + 1
                while run_end < len(row) and row[run_end].to_hex() == hex_color:
                    run_end += 1
                run_len = run_end - x
                parts.append(
                    f'<rect x="{x_off + x*pixel_size}" y="{y_off + y*pixel_size}" '
                    f'width="{run_len*pixel_size}" height="{pixel_size}" '
                    f'fill="{hex_color}"/>\n'
                )
                x = run_end

        # Label below each panel
        label_y = y_off + height_each * pixel_size + 18
        parts.append(f'<text x="{x_off + panel_w//2}" y="{label_y}" text-anchor="middle" '
                     f'fill="#ffffff" font-family="Helvetica,Arial,sans-serif" '
                     f'font-size="13" font-weight="bold">{label}</text>\n')
        parts.append(f'<text x="{x_off + panel_w//2}" y="{label_y + 16}" text-anchor="middle" '
                     f'fill="#aaaaaa" font-family="monospace" font-size="10">'
                     f'ξ = {xi}</text>\n')

        # Properties
        prop_y = label_y + 32
        prop_lines = [
            f"σ_conv = {props['sigma_conv']:.3f}",
            f"Nesting: {props['n_levels']:.0f} levels",
            f"Proton shift (Earth): {props['proton_shift_earth_ppm']:.4f} ppm",
            f"Proton shift (NS): {props['ns_shift_pct']:.3f}%",
        ]
        for i, line in enumerate(prop_lines):
            parts.append(f'<text x="{x_off + panel_w//2}" y="{prop_y + i*14}" '
                         f'text-anchor="middle" fill="#888888" '
                         f'font-family="monospace" font-size="9">{line}</text>\n')

    # Footer insight
    fy = total_h - 20
    parts.append(f'<text x="{total_w//2}" y="{fy}" text-anchor="middle" fill="#555555" '
                 f'font-family="Helvetica,Arial,sans-serif" font-size="9">'
                 f'Note: Electron (blue sphere) is identical in all universes — '
                 f'its mass is Higgs-only, σ-invariant</text>\n')

    parts.append('</svg>')

    out_path = os.path.join(out_dir, 'multiverse_comparison.svg')
    with open(out_path, 'w') as f:
        f.writelines(parts)
    return out_path


def main():
    print("=" * 50)
    print("MULTIVERSE COMPARISON — Three ξ Values")
    print("=" * 50)

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'renders')
    os.makedirs(out_dir, exist_ok=True)

    configs = [
        (0.05, "Resilient Universe"),
        (0.1582, "Our Universe"),
        (0.40, "Heavy Universe"),
    ]

    results = []
    t_total = time.time()

    for xi, label in configs:
        props = universe_properties(xi)
        print(f"\n{'─'*40}")
        print(f"  {label}: ξ = {xi}")
        print(f"  σ_conv = {props['sigma_conv']:.4f}")
        print(f"  Nesting levels = {props['n_levels']:.1f}")
        print(f"  Proton shift at Earth surface = {props['proton_shift_earth_ppm']:.6f} ppm")
        print(f"  Proton mass at neutron star = {props['proton_ns_mev']:.3f} MeV ({props['ns_shift_pct']:.4f}%)")

        svg_path, pixels = render_universe(xi, label, out_dir)
        results.append((xi, label, props, svg_path, pixels))

    # Compose side-by-side
    print(f"\n{'─'*40}")
    print("Composing comparison panel...")
    comp_path = compose_comparison_svg(results, out_dir)
    print(f"Comparison saved: {comp_path}")

    print(f"\nTotal time: {time.time() - t_total:.2f}s")
    print("Done.")


if __name__ == '__main__':
    main()
